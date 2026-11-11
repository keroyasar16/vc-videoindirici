# Akış — X ve YouTube Video İndirici

Flask tabanlı uygulama, herkese açık X gönderileri ve YouTube videoları için ayrı arayüzler sunar. Üretimde `x.vcchats.com` X sayfasını, `yt.vcchats.com` YouTube sayfasını açar.

## Kurulum

Python 3.10 veya üzeri gerekir.
YouTube indirme desteği için sunucuda Node.js 22+ (veya Deno 2.3+) kurulu olmalıdır. Node.js kullanıldığında yt-dlp, YouTube'un JavaScript doğrulaması için gereken çözümleyici bileşenini GitHub'dan indirir; sunucunun GitHub erişimi olmalıdır.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Siteyi `http://127.0.0.1:5000` adresinde açın. X indirme sayfası `/`, YouTube sayfası `/youtube` adresindedir.
Python/yt-dlp'yi güncelledikten veya Node.js kurduktan sonra çalışan Flask sürecini yeniden başlatın.
Video indirmeden önce mevcut kalite seçeneklerinden birini seçebilir, MP3 düğmesiyle yalnızca ses parçasını kaydedebilirsiniz. FFmpeg dönüştürücüsü `imageio-ffmpeg` bağımlılığıyla kurulur.
Parçalara bölünmüş video akışları için indirme eşzamanlılığı 8 parçaya çıkarılmıştır. Bu ayar DASH/HLS akışlarında indirmeyi hızlandırabilir; doğrudan tek dosya olarak sunulan videolarda hız, bağlantı ve kaynak sunucunun kapasitesiyle sınırlıdır.

## `x.vcchats.com` ve `yt.vcchats.com` alan adları

İki alan adının DNS kayıtlarını sunucunuzun IP adresine yönlendirin ve ters proxy'de (ör. Nginx) her iki ana makine adını aynı Flask uygulamasına iletin. Uygulama ana makine adına göre doğru sayfayı sunar. Alan adı/DNS ve sunucu yapılandırması bu proje dosyalarıyla otomatik olarak yapılandırılmaz.

İçerik üreticilerinin haklarına ve platform koşullarına uyun; yalnızca indirme izniniz olan videoları kullanın. X sürümü `x.com` ve `twitter.com`; YouTube sürümü `youtube.com`, `youtu.be` ve `youtube-nocookie.com` video bağlantılarını kabul eder. Özel veya oturum açma gerektiren videolar desteklenmez.

## Railway dağıtımı

Bu klasörü GitHub deposunun köküne koyup Railway üzerinde **Deploy from GitHub repo** ile dağıtın. Dockerfile otomatik algılanır. Railway servisinin Settings > Networking > Custom Domain bölümüne `x.vcchats.com` ve `yt.vcchats.com` alan adlarını ayrı ayrı ekleyin. Railway'in her biri için verdiği DNS hedeflerini domain DNS sağlayıcınızda CNAME olarak tanımlayın. DNS hedeflerini tahmin etmeyin; Railway panelinden kopyalayın. Railway sertifika doğrulaması ve HTTPS etkinleşince iki adrese de erişebilirsiniz.

Dockerfile Node.js 22, FFmpeg, Python ve Gunicorn kurar. `yt-dlp` YouTube doğrulaması için ek bileşen indirmek zorunda kalabilir; ağ engelleri, bot doğrulaması ve platform kısıtlamaları nedeniyle her videonun indirileceği garanti değildir. Video indirmeleri uzun sürebilir ve Railway kaynak sınırlarına takılabilir.


## YouTube Railway doğrulama güncellemesi

Bu sürüm yt-dlp varsayılan EJS bağımlılıklarını kurar, Node.js 22 kullanır ve YouTube isteklerinde sınırlı yeniden deneme uygular. X indirme seçenekleri değiştirilmemiştir.

**Önemli:** YouTube `Sign in to confirm you’re not a bot` yanıtı verirse bu sunucunun IP'si / oturum doğrulaması kaynaklı olabilir. Bu güncelleme böyle bir engeli kaldırmayı garanti etmez. Herkese açık hizmette kişisel hesap çerezlerini dağıtmayın. PO Token sağlayıcısı bu pakette kurulmamıştır.

Railway'de GitHub'a dosyaları yükleyip yeniden deploy edin. Deploy Logs'da bağımlılık kurulumunu, çalışma günlüklerinde bot doğrulama mesajını kontrol edin.
