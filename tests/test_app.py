import unittest
from pathlib import Path
from unittest.mock import patch

from app import (
    _extract_video,
    _quality_options,
    _video_format_selector,
    app,
    validate_post_url,
    validate_youtube_url,
)
from yt_dlp.utils import DownloadError


class ValidatePostUrlTests(unittest.TestCase):
    def test_accepts_x_and_twitter_post_links(self):
        self.assertEqual(
            validate_post_url("https://x.com/example/status/123456"),
            "https://x.com/example/status/123456",
        )
        self.assertEqual(
            validate_post_url("https://twitter.com/i/status/123456?ref=share"),
            "https://twitter.com/i/status/123456?ref=share",
        )

    def test_rejects_non_post_and_untrusted_urls(self):
        invalid_urls = (
            "http://x.com/example/status/123456",
            "https://example.com/example/status/123456",
            "https://x.com:444/example/status/123456",
            "https://user@x.com/example/status/123456",
            "https://x.com/example",
            None,
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_post_url(url)


class ValidateYoutubeUrlTests(unittest.TestCase):
    def test_accepts_watch_short_and_share_links(self):
        youtube_urls = (
            "https://www.youtube.com/watch?v=abcdefghijk",
            "https://youtube.com/shorts/abcdefghijk",
            "https://www.youtube.com/live/abcdefghijk",
            "https://youtu.be/abcdefghijk?t=42",
            "https://www.youtube-nocookie.com/embed/abcdefghijk",
        )
        for url in youtube_urls:
            with self.subTest(url=url):
                self.assertEqual(validate_youtube_url(url), url)

    def test_rejects_non_video_and_untrusted_urls(self):
        invalid_urls = (
            "http://youtube.com/watch?v=abcdefghijk",
            "https://youtube.com/",
            "https://youtube.com/watch",
            "https://youtube.com/watch?v=short",
            "https://youtube.com.evil.example/watch?v=abcdefghijk",
            "https://youtu.be:444/abcdefghijk",
            "https://user@youtube.com/watch?v=abcdefghijk",
            "https://www.youtube-nocookie.com/watch?v=abcdefghijk",
            None,
        )
        for url in invalid_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_youtube_url(url)


class AppRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_homepage_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X VİDEO İNDİRİCİ".encode(), response.data)

    def test_video_info_returns_extracted_metadata(self):
        with patch(
            "app._extract_video",
            return_value={
                "title": "Test video",
                "uploader": "test-user",
                "thumbnail": "https://example.com/thumb.jpg",
                "duration": 12,
                "formats": [
                    {"height": 720, "vcodec": "avc1"},
                    {"height": 1080, "vcodec": "avc1"},
                    {"height": 360, "vcodec": "avc1"},
                    {"height": None, "vcodec": "none"},
                ],
            },
        ):
            response = self.client.post(
                "/api/video",
                json={"url": "https://x.com/test_user/status/123456"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["title"], "Test video")
        self.assertEqual(
            response.get_json()["qualities"],
            [
                {"value": "best", "label": "En yüksek kalite (1080p)"},
                {"value": "720", "label": "720p"},
                {"value": "360", "label": "360p"},
            ],
        )

    def test_video_info_rejects_untrusted_url_before_extraction(self):
        with patch("app._extract_video") as extract:
            response = self.client.post(
                "/api/video",
                json={"url": "https://example.com/test-user/status/123456"},
            )

        self.assertEqual(response.status_code, 400)
        extract.assert_not_called()

    def test_youtube_page_renders_on_local_route(self):
        response = self.client.get("/youtube")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"YouTube", response.data)
        self.assertIn(b'data-api-prefix="/youtube/api"', response.data)

    def test_youtube_subdomain_renders_youtube_homepage(self):
        response = self.client.get("/", base_url="https://yt.akis.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"YouTube V", response.data)
        self.assertIn(b'data-api-prefix="/api"', response.data)

    def test_youtube_api_returns_video_metadata(self):
        with patch(
            "app._extract_video",
            return_value={
                "title": "Test YouTube video",
                "channel": "test-channel",
                "thumbnail": "https://example.com/thumb.jpg",
                "duration": 12,
            },
        ):
            response = self.client.post(
                "/youtube/api/video",
                json={"url": "https://youtube.com/watch?v=abcdefghijk"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["title"], "Test YouTube video")

    def test_youtube_subdomain_api_accepts_youtube_links(self):
        with patch(
            "app._extract_video",
            return_value={"title": "Test YouTube video"},
        ):
            response = self.client.post(
                "/api/video",
                base_url="https://yt.akis.com",
                json={"url": "https://youtu.be/abcdefghijk"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["title"], "Test YouTube video")

    def test_youtube_api_rejects_x_links_before_extraction(self):
        with patch("app._extract_video") as extract:
            response = self.client.post(
                "/youtube/api/video",
                json={"url": "https://x.com/test-user/status/123456"},
            )

        self.assertEqual(response.status_code, 400)
        extract.assert_not_called()

    def test_youtube_extraction_enables_installed_node_and_ejs(self):
        with patch("app.shutil.which", return_value=r"C:\Program Files\nodejs\node.exe"):
            with patch("app.yt_dlp.YoutubeDL") as youtube_dl:
                youtube_dl.return_value.__enter__.return_value.extract_info.return_value = {
                    "title": "Test"
                }

                _extract_video(
                    "https://youtube.com/watch?v=abcdefghijk",
                    platform="youtube",
                )

        options = youtube_dl.call_args.args[0]
        self.assertEqual(
            options["js_runtimes"],
            {"node": {"path": r"C:\Program Files\nodejs\node.exe"}},
        )
        self.assertEqual(options["remote_components"], [])

    def test_youtube_api_explains_javascript_runtime_errors(self):
        with patch(
            "app._extract_video",
            side_effect=DownloadError(
                "ERROR: [youtube] n challenge solving failed: No supported JavaScript runtime"
            ),
        ):
            response = self.client.post(
                "/youtube/api/video",
                json={"url": "https://youtube.com/watch?v=abcdefghijk"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Node.js 22+", response.get_json()["error"])

    def test_quality_options_handle_missing_video_resolutions(self):
        self.assertEqual(
            _quality_options({"formats": [{"vcodec": "none", "height": None}]}),
            [{"value": "best", "label": "En yüksek kalite"}],
        )

    def test_video_download_uses_selected_quality(self):
        def fake_extract(url, *, download, output_dir, platform, quality, audio_only):
            self.assertTrue(download)
            self.assertEqual(platform, "x")
            self.assertEqual(quality, "720")
            self.assertFalse(audio_only)
            Path(output_dir, "video.mp4").write_bytes(b"video")

        with patch("app._extract_video", side_effect=fake_extract):
            response = self.client.post(
                "/api/download",
                json={
                    "url": "https://x.com/test_user/status/123456",
                    "quality": "720",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"video")
        self.assertIn("x-video.mp4", response.headers["Content-Disposition"])
        response.close()

    def test_youtube_download_uses_selected_quality(self):
        def fake_extract(url, *, download, output_dir, platform, quality, audio_only):
            self.assertTrue(download)
            self.assertEqual(platform, "youtube")
            self.assertEqual(quality, "720")
            self.assertFalse(audio_only)
            Path(output_dir, "video.mp4").write_bytes(b"video")

        with patch("app._extract_video", side_effect=fake_extract):
            response = self.client.post(
                "/youtube/api/download",
                json={
                    "url": "https://youtube.com/watch?v=abcdefghijk",
                    "quality": "720",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"video")
        self.assertIn("yt-video.mp4", response.headers["Content-Disposition"])
        response.close()

    def test_mp3_download_returns_audio_file_for_youtube(self):
        def fake_extract(url, *, download, output_dir, platform, quality, audio_only):
            self.assertTrue(download)
            self.assertEqual(platform, "youtube")
            self.assertTrue(audio_only)
            Path(output_dir, "audio.mp3").write_bytes(b"mp3-audio")

        with patch("app._extract_video", side_effect=fake_extract):
            response = self.client.post(
                "/youtube/api/download",
                json={
                    "url": "https://youtube.com/watch?v=abcdefghijk",
                    "audio_only": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")
        self.assertEqual(response.data, b"mp3-audio")
        self.assertIn("yt-audio.mp3", response.headers["Content-Disposition"])
        response.close()

    def test_mp3_download_returns_audio_file_for_x(self):
        def fake_extract(url, *, download, output_dir, platform, quality, audio_only):
            self.assertTrue(download)
            self.assertEqual(platform, "x")
            self.assertTrue(audio_only)
            Path(output_dir, "audio.mp3").write_bytes(b"mp3-audio")

        with patch("app._extract_video", side_effect=fake_extract):
            response = self.client.post(
                "/api/download",
                json={
                    "url": "https://x.com/test_user/status/123456",
                    "audio_only": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "audio/mpeg")
        self.assertEqual(response.data, b"mp3-audio")
        self.assertIn("x-audio.mp3", response.headers["Content-Disposition"])
        response.close()

    def test_download_rejects_malformed_quality(self):
        response = self.client.post(
            "/api/download",
            json={
                "url": "https://x.com/test_user/status/123456",
                "quality": "best+malicious",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Geçerli bir video kalitesi seçin.")

    def test_youtube_download_configures_ffmpeg_mp3_postprocessor(self):
        with patch("app.imageio_ffmpeg.get_ffmpeg_exe", return_value="ffmpeg.exe"):
            with patch("app.yt_dlp.YoutubeDL") as youtube_dl:
                _extract_video(
                    "https://youtube.com/watch?v=abcdefghijk",
                    download=True,
                    output_dir="C:\\temp",
                    platform="youtube",
                    audio_only=True,
                )

        options = youtube_dl.call_args.args[0]
        self.assertEqual(options["format"], "bestaudio/best")
        self.assertEqual(options["ffmpeg_location"], "ffmpeg.exe")
        self.assertEqual(
            options["postprocessors"],
            [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }
            ],
        )

    def test_video_download_configures_selected_resolution_and_ffmpeg(self):
        with patch("app.imageio_ffmpeg.get_ffmpeg_exe", return_value="ffmpeg.exe"):
            with patch("app.yt_dlp.YoutubeDL") as youtube_dl:
                _extract_video(
                    "https://x.com/test_user/status/123456",
                    download=True,
                    output_dir="C:\\temp",
                    quality="720",
                )

        options = youtube_dl.call_args.args[0]
        self.assertEqual(
            options["format"],
            "bestvideo[height=720]+bestaudio/best[height=720]/"
            "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        )
        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertEqual(options["ffmpeg_location"], "ffmpeg.exe")
        self.assertEqual(options["concurrent_fragment_downloads"], 8)

    def test_quality_format_selector_supports_best_and_selected_resolution(self):
        self.assertEqual(_video_format_selector("best"), "bestvideo+bestaudio/best")
        self.assertEqual(
            _video_format_selector("720"),
            "bestvideo[height=720]+bestaudio/best[height=720]/"
            "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        )


if __name__ == "__main__":
    unittest.main()
