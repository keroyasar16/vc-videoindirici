from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import imageio_ffmpeg
import yt_dlp
from flask import Flask, jsonify, render_template, request, send_file
from yt_dlp.utils import DownloadError, PostProcessingError

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

_POST_PATH = re.compile(r"^/(?:[A-Za-z0-9_]{1,15}/)?status/\d+/?$")
_ALLOWED_HOSTS = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_YDL_OPTIONS = {
    "format": "best[ext=mp4]/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "socket_timeout": 30,
    "max_filesize": 500 * 1024 * 1024,
    "concurrent_fragment_downloads": 8,
}


def validate_post_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Geçerli bir X gönderi bağlantısı girin.")

    url = value.strip()
    try:
        parsed = urlsplit(url)
        safe_authority = (
            parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        safe_authority = False
        parsed = None

    if (
        parsed is None
        or not safe_authority
        or parsed.scheme != "https"
        or parsed.hostname not in _ALLOWED_HOSTS
        or not _POST_PATH.fullmatch(parsed.path)
    ):
        raise ValueError("Yalnızca herkese açık x.com veya twitter.com gönderi bağlantıları desteklenir.")
    return url


def validate_youtube_url(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Geçerli bir YouTube video bağlantısı girin.")

    url = value.strip()
    try:
        parsed = urlsplit(url)
        safe_authority = (
            parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
        )
    except ValueError:
        safe_authority = False
        parsed = None

    valid_video_path = False
    if parsed is not None:
        if parsed.hostname in {"youtu.be", "www.youtu.be"}:
            valid_video_path = bool(re.fullmatch(r"/[A-Za-z0-9_-]{11}/?", parsed.path))
        elif parsed.hostname in _YOUTUBE_HOSTS:
            if parsed.hostname in {"youtube-nocookie.com", "www.youtube-nocookie.com"}:
                valid_video_path = bool(
                    re.fullmatch(r"/embed/[A-Za-z0-9_-]{11}/?", parsed.path)
                )
            else:
                video_id = parse_qs(parsed.query).get("v", [""])[0]
                if parsed.path.rstrip("/") == "/watch":
                    valid_video_path = bool(
                        re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id)
                    )
                else:
                    valid_video_path = bool(
                        re.fullmatch(
                            r"/(?:shorts|live|embed)/[A-Za-z0-9_-]{11}/?",
                            parsed.path,
                        )
                    )

    if (
        parsed is None
        or not safe_authority
        or parsed.scheme != "https"
        or parsed.hostname not in _YOUTUBE_HOSTS
        or not valid_video_path
    ):
        raise ValueError("Yalnızca YouTube video bağlantıları desteklenir.")
    return url


def _host_platform() -> str:
    hostname = request.host.rsplit(":", 1)[0].lower()
    return "youtube" if hostname == "yt.vcchats.com" else "x"


def _is_local_host() -> bool:
    return request.host.rsplit(":", 1)[0].lower() in _LOCAL_HOSTS


def _video_format_selector(quality: str) -> str:
    if quality == "best":
        return "bestvideo+bestaudio/best"
    return (
        f"bestvideo[height={quality}]+bestaudio/best[height={quality}]/"
        f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]/best"
    )


def _extract_video(
    url: str,
    *,
    download: bool = False,
    output_dir: str | None = None,
    platform: str = "x",
    quality: str = "best",
    audio_only: bool = False,
) -> dict:
    options = dict(_YDL_OPTIONS)
    if platform == "youtube":
        options["remote_components"] = ["ejs:github"]
        node_path = shutil.which("node")
        if node_path:
            options["js_runtimes"] = {"node": {"path": node_path}}
    if download and output_dir:
        if audio_only:
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }
            ]
        else:
            options["format"] = _video_format_selector(quality)
        options.update(
            {
                "outtmpl": str(Path(output_dir) / "%(id)s.%(ext)s"),
                "merge_output_format": "mp4",
                "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
            }
        )
    with yt_dlp.YoutubeDL(options) as downloader:
        return downloader.extract_info(url, download=download)


def _quality_options(info: dict) -> list[dict[str, str]]:
    heights = sorted(
        {
            form.get("height")
            for form in (info.get("formats") or [])
            if form.get("vcodec") not in (None, "none")
            and isinstance(form.get("height"), int)
        },
        reverse=True,
    )
    best_label = f"En yüksek kalite ({heights[0]}p)" if heights else "En yüksek kalite"
    return [
        {"value": "best", "label": best_label},
        *({"value": str(height), "label": f"{height}p"} for height in heights if height != heights[0]),
    ]


def _extraction_error_message(platform: str, error: DownloadError, operation: str) -> str:
    app.logger.warning("Video %s failed for %s: %s", operation, platform, error)
    if platform != "youtube":
        if operation == "metadata":
            return "Video alınamadı. Gönderi herkese açık olmayabilir veya video içermiyor olabilir."
        return "Video indirilemedi. Bağlantıyı ve gönderinin erişilebilir olduğunu kontrol edin."

    details = str(error).removeprefix("ERROR: ").strip()
    lowered_details = details.lower()
    if "javascript runtime" in lowered_details or "challenge solving failed" in lowered_details:
        return (
            "YouTube doğrulaması tamamlanamadı. Sunucuya Node.js 22+ veya Deno 2.3+ "
            "kurup uygulamayı yeniden başlatın."
        )
    if "sign in to confirm" in lowered_details or "not a bot" in lowered_details:
        return (
            "YouTube bu isteği engelledi. Videonun herkese açık olduğunu kontrol edin "
            "ve daha sonra yeniden deneyin."
        )
    if "video unavailable" in lowered_details:
        return "Bu YouTube videosu kullanılamıyor; silinmiş, gizli veya erişim kısıtlamalı olabilir."
    if not details:
        return "YouTube videosu alınamadı. Sunucu günlüklerinde yt-dlp hata ayrıntısını kontrol edin."
    return f"YouTube videosu alınamadı: {details}"


@app.get("/")
def index():
    platform = _host_platform()
    if platform == "youtube" and request.host.rsplit(":", 1)[0].lower() == "yt.vcchats.com":
        alternate_url = "https://x.vcchats.com/"
    elif request.host.rsplit(":", 1)[0].lower() == "x.vcchats.com":
        alternate_url = "https://yt.vcchats.com/"
    else:
        alternate_url = "/youtube" if platform == "x" else "/"
    return render_template(
        "index.html",
        platform=platform,
        api_prefix="/api",
        alternate_url=alternate_url,
    )


@app.get("/youtube")
def youtube_index():
    return render_template(
        "index.html",
        platform="youtube",
        api_prefix="/youtube/api",
        alternate_url="/",
    )


def _video_info(platform: str):
    payload = request.get_json()
    validator = validate_youtube_url if platform == "youtube" else validate_post_url
    try:
        url = validator(payload.get("url") if isinstance(payload, dict) else None)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    try:
        info = _extract_video(url, platform=platform)
    except DownloadError as error:
        return jsonify(error=_extraction_error_message(platform, error, "metadata")), 422

    return jsonify(
        title=info.get("title") or ("YouTube videosu" if platform == "youtube" else "X videosu"),
        uploader=info.get("uploader") or info.get("channel") or ("YouTube kanalı" if platform == "youtube" else "X kullanıcısı"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        qualities=_quality_options(info),
    )


def _download_video(platform: str):
    payload = request.get_json()
    validator = validate_youtube_url if platform == "youtube" else validate_post_url
    try:
        url = validator(payload.get("url") if isinstance(payload, dict) else None)
    except ValueError as error:
        return jsonify(error=str(error)), 400

    audio_only = payload.get("audio_only") is True
    quality = payload.get("quality", "best")
    if not audio_only and (
        not isinstance(quality, str)
        or (quality != "best" and not re.fullmatch(r"(?:[1-9]\d{1,3})", quality))
        or (quality != "best" and int(quality) > 4320)
    ):
        return jsonify(error="Geçerli bir video kalitesi seçin."), 400

    prefix = "yt" if platform == "youtube" else "x"
    temp_dir = tempfile.mkdtemp(prefix=f"{prefix}-video-")
    try:
        _extract_video(
            url,
            download=True,
            output_dir=temp_dir,
            platform=platform,
            quality=quality,
            audio_only=audio_only,
        )
        files = [
            path
            for path in Path(temp_dir).iterdir()
            if path.is_file() and path.suffix.lower() not in {".part", ".ytdl"}
        ]
        if audio_only:
            files = [path for path in files if path.suffix.lower() == ".mp3"]
        if not files:
            raise DownloadError(
                "İndirilen MP3 dosyası bulunamadı."
                if audio_only
                else "İndirilen video dosyası bulunamadı."
            )
        video_path = max(files, key=lambda path: path.stat().st_size)
        extension = ".mp3" if audio_only else video_path.suffix
        response = send_file(
            video_path,
            as_attachment=True,
            download_name=f"{prefix}-{'audio' if audio_only else 'video'}{extension}",
            mimetype=(
                "audio/mpeg"
                if audio_only
                else "video/mp4"
                if video_path.suffix.lower() == ".mp4"
                else "application/octet-stream"
            ),
        )
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except (DownloadError, PostProcessingError) as error:
        shutil.rmtree(temp_dir, ignore_errors=True)
        if isinstance(error, PostProcessingError):
            app.logger.exception("Video post-processing failed for %s", platform)
            return jsonify(
                error="Video dönüştürülemedi. FFmpeg bileşeninin kullanılabilir olduğundan emin olun."
            ), 422
        return jsonify(error=_extraction_error_message(platform, error, "download")), 422
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


@app.post("/api/video")
def video_info():
    return _video_info(_host_platform())


@app.post("/api/download")
def download_video():
    return _download_video(_host_platform())


@app.post("/youtube/api/video")
def local_youtube_video_info():
    if not _is_local_host() and _host_platform() != "youtube":
        return jsonify(error="Bu bağlantı bu site sürümünde kullanılamıyor."), 404
    return _video_info("youtube")


@app.post("/youtube/api/download")
def local_youtube_download_video():
    if not _is_local_host() and _host_platform() != "youtube":
        return jsonify(error="Bu bağlantı bu site sürümünde kullanılamıyor."), 404
    return _download_video("youtube")


if __name__ == "__main__":
    app.run(debug=False)
