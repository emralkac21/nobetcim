# 🗓️ Nöbetmatik - Okul Nöbet Dağıtım ve Yönetim Sistemi

Nöbetmatik, okullardaki öğretmen nöbet programlarını düzenlemek, yönetmek ve raporlamak için geliştirilmiş, kullanıcı dostu ve modern arayüzlü bir masaüstü uygulamasıdır. Python ve Tkinter kullanılarak tasarlanmış olup, verileri yerel SQLite veritabanında güvenle saklar.

## ✨ Temel Özellikler

* **👨‍🏫 Kapsamlı Öğretmen Yönetimi:** Öğretmenlerin ad, soyad, branş, iletişim bilgileri ve nöbet tutabilecekleri müsait günleri sisteme kaydedebilirsiniz.
* **🤖 Akıllı Otomatik Nöbet Dağıtımı:** Belirlenen hafta için öğretmenlerin müsaitlik durumlarına, mevcut nöbet sayılarına ve önceki haftalardaki çift nöbet durumlarına göre adil ve otomatik nöbet ataması yapar.
* **📍 Nöbet Yeri Yönetimi:** Okulun dinamiklerine göre nöbet yerlerini (Katlar, Bahçe, Kantin vb.) ekleyebilir, silebilir veya güncelleyebilirsiniz.
* **📄 Gelişmiş Raporlama:** * Haftalık, aylık ve yıllık bazda **PDF** formatında şık nöbet çizelgeleri oluşturma.
    * Tüm nöbet geçmişini **Excel (.xlsx)** formatında dışa aktarma yeteneği.
* **🎨 Modern Kullanıcı Arayüzü:** Renklendirilmiş tablolar, çift nöbet tutanları vurgulayan sistem ve sekme tabanlı kolay gezinme.
* **🔍 Gelişmiş Arama:** Tarih, öğretmen adı veya nöbet yerine göre geçmiş nöbet kayıtlarını hızlıca filtreleme.

## 🚀 Kurulum ve Çalıştırma

Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları izleyin:

### Ön Koşullar
* Bilgisayarınızda [Python 3.8+](https://www.python.org/downloads/) yüklü olmalıdır.

### Adımlar

1.  **Projeyi Klonlayın:**
    ```bash
    git clone [https://github.com/KULLANICI_ADINIZ/nobetmatik.git](https://github.com/KULLANICI_ADINIZ/nobetmatik.git)
    cd nobetmatik
    ```

2.  **Gerekli Kütüphaneleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Uygulamayı Başlatın:**
    ```bash
    python nöbetmatik.py
    ```

## 🛠️ Kullanılan Teknolojiler
* **Dil:** Python 3
* **Arayüz (GUI):** Tkinter (Modernize edilmiş 'clam' teması ile)
* **Veritabanı:** SQLite3
* **Raporlama:** ReportLab (PDF) & OpenPyXL (Excel)

## 👨‍💻 Geliştirici
Bu uygulama **Emrullah ALKAÇ** tarafından geliştirilmiştir.
İletişim ve geri bildirimleriniz için: kimyoremr@gmail.com

## 📄 Lisans
Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.
