# Telegram Media Hub

[![CI Tests](https://github.com/oguztasdemir/Telegram-Kanal-Medya-Yonetim-Paneli/actions/workflows/ci.yml/badge.svg)](https://github.com/oguztasdemir/Telegram-Kanal-Medya-Yonetim-Paneli/actions/workflows/ci.yml)


Modern, hızlı ve kullanıcı dostu arayüze sahip yerel bir Telegram medya ve belge yönetim paneli. Bu araçla, üye olduğunuz tüm Telegram kanal, grup ve sohbetlerindeki PDF, görsel, ses ve video gibi dosyaları listeleyebilir, arayabilir, önizleyebilir ve toplu olarak indirebilirsiniz.

![Arayüz Önizlemesi](https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?q=80&w=1000&auto=format&fit=crop)

## ✨ Özellikler

- **Gelişmiş Arayüz ve Temalar**: Dark Mode (varsayılan), Light Mode, Cyberpunk, Forest ve Ocean temaları ile premium tasarım.
- **Kanallar Arası Küresel Arama**: Tüm sohbetlerinizin içindeki metinleri veya dosya adlarını tek seferde arayın.
- **Gelişmiş Toplu İndirme (Batch Download)**:
  - Sohbetler arası gezinirken seçimleriniz kaybolmaz. Farklı kanallardan seçtiğiniz dosyaları tek seferde indirebilirsiniz.
  - Seçilen dosyaları otomatik olarak gruplayıp ortak bir **ZIP** arşivi olarak indirebilme.
  - Klasör seçimi ekranında bilgisayarınızdaki herhangi bir dizini (Örn: `C:\Klasör`) hedef göstererek doğrudan oraya indirme yapabilme.
- **Dosya Önizleme Sistemi**:
  - PDF dosyalarını tarayıcı üzerinden doğrudan okuma ve PDF içeriklerinde kelime arama.
  - Videoları (`.mp4`, `.webm` vb.) ve ses kayıtlarını uygulama içinden oynatma (Ses kayıtları için oynatma hızı desteği: 1.0x, 1.25x, 1.5x, 2.0x).
  - Görselleri ve fotoğrafları tam ekran görüntüleme.
- **Akıllı Etiketleme ve Filtreleme (NLP Tagging)**:
  - Belgelerin içerik analizini yaparak otomatik olarak "Sağlık", "Fen", "Sosyal" gibi etiketler atar.
  - Türkçe dil kurallarına (çekim ekleri, fiiller) uygun gelişmiş temizleme algoritması ile gereksiz etiketleri eler.
  - Dosya uzantılarına ve etiket kelimelerine göre anında filtreleme.
- **Çoklu Hesap Desteği**: Uygulamadan çıkış yapmadan farklı Telegram telefon numaraları ve hesapları arasında hızlı geçiş yapabilme.

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
- Python 3.10 veya üzeri
- Aktif bir Telegram Hesabı
- [my.telegram.org](https://my.telegram.org) adresinden alacağınız `API_ID` ve `API_HASH` kodları.

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/kullanici-adiniz/telegram-media-hub.git
cd telegram-media-hub
```

### 2. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```
*(Eğer `requirements.txt` yoksa şu paketleri kurun: `pip install fastapi uvicorn telethon pypdf`)*

### 3. Bilgilerinizi Girin
Giriş bilgilerini ister uygulama açıldığında arayüzdeki **Ayarlar** kısmından ekleyebilir, isterseniz projedeki `kullanici.py` dosyasına yazabilirsiniz:
```python
API_ID = "TELEGRAM_API_ID"
API_HASH = "TELEGRAM_API_HASH"
PHONE = "+90XXXXXXXXXX"
```

### 4. Uygulamayı Başlatın
```bash
python main.py
```
Uygulama başladığında tarayıcınızda otomatik olarak `http://127.0.0.1:8000` adresi açılacaktır. Telegram uygulamanıza gelen doğrulama kodunu girerek kullanmaya başlayabilirsiniz.

## 🔒 Güvenlik Notu

Bu proje tamamen yerel bilgisayarınızda çalışır. Telegram API kimlik bilgileriniz (`kullanici.py` veya `kullanicilar.json`), oturum dosyalarınız (`*.session`) ve indirdiğiniz dosyalar hiçbir üçüncü taraf sunucuyla paylaşılmaz. `.gitignore` dosyası kişisel verilerinizin yanlışlıkla GitHub'a yüklenmesini önlemek üzere yapılandırılmıştır.

## 📄 Lisans
Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.


---

## Yerel Testler

Projenin temel çalışma ve sözdizimi doğrulama testlerini çalıştırmak için:

```bash
pip install pytest
pytest tests -v
```
