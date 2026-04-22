# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import datetime
import sqlite3
import random # Nöbet atamalarında rastgeleliği kullanmak için
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import locale
from collections import defaultdict

# YENİ: Excel dışa aktarma için kütüphane
try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


# PDF'te Türkçe karakterler için lokal ayarı artık kritik değil ama kalabilir
try:
    locale.setlocale(locale.LC_TIME, 'tr_TR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'tr_TR')
    except locale.Error:
        print("Uyarı: Türkçe lokal ayarı yapılamadı. Gün isimleri manuel olarak ayarlanacaktır.")
        

# --- Veritabanı Yönetim Sınıfı ---
class DatabaseManager:
    def __init__(self, db_name="nbt_yeni.db"):
        self.db_name = db_name
        self.conn = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Veritabanına bağlanır ve UTF-8 desteğini zorunlu kılar."""
        try:
            self.conn = sqlite3.connect(self.db_name)
            # DÜZELTME: Veritabanından gelen ve veritabanına giden tüm metinlerin
            # UTF-8 olarak işlenmesini garanti altına al.
            self.conn.text_factory = str
            self.conn.row_factory = sqlite3.Row # Kolon isimleriyle verilere erişmek için
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Veritabanına bağlanılamadı: {e}")
            self.conn = None

    def close(self):
        """Veritabanı bağlantısını kapatır."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def create_tables(self):
        """Gerekli tabloları oluşturur."""
        if not self.conn:
            return

        cursor = self.conn.cursor()
        try:
            # Öğretmenler Tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ogretmenler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad TEXT NOT NULL,
                    soyad TEXT NOT NULL,
                    brans TEXT NOT NULL,
                    tc_kimlik_no TEXT UNIQUE NOT NULL,
                    telefon_no TEXT,
                    available_days TEXT DEFAULT 'Pazartesi,Salı,Çarşamba,Perşembe,Cuma'
                )
            """)
            # Nöbetler Tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nobetler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ogretmen_id INTEGER NOT NULL,
                    nobet_yeri TEXT NOT NULL,
                    nobet_tarihi TEXT NOT NULL, -- YYYY-MM-DD formatında saklanacak
                    FOREIGN KEY (ogretmen_id) REFERENCES ogretmenler(id) ON DELETE CASCADE,
                    UNIQUE(ogretmen_id, nobet_yeri, nobet_tarihi)
                )
            """)
            # Nöbet Yerleri Tablosu
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nobet_yerleri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    yer_adi TEXT NOT NULL UNIQUE
                )
            """)
            self.conn.commit()

            # Mevcut ogretmenler tablosuna available_days sütunu eklemek için ALTER TABLE (sadece yoksa)
            cursor.execute("PRAGMA table_info(ogretmenler)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'available_days' not in columns:
                cursor.execute("ALTER TABLE ogretmenler ADD COLUMN available_days TEXT DEFAULT 'Pazartesi,Salı,Çarşamba,Perşembe,Cuma'")
                self.conn.commit()
            
            self.initialize_default_locations()

        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Tablolar oluşturulamadı/güncellenemedi: {e}")

    def initialize_default_locations(self):
        if not self.conn: return
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nobet_yerleri")
        if cursor.fetchone()[0] == 0:
            default_locations = ["1. Kat", "2. Kat", "Kantin", "Bahçe", "Giriş", "Kütüphane", "Spor Salonu"]
            try:
                for loc in default_locations:
                    cursor.execute("INSERT INTO nobet_yerleri (yer_adi) VALUES (?)", (loc,))
                self.conn.commit()
            except sqlite3.Error as e:
                messagebox.showwarning("Veritabanı Uyarısı", f"Varsayılan nöbet yerleri eklenirken hata: {e}")

    # --- Öğretmen İşlemleri ---
    def add_teacher(self, ad, soyad, brans, tc, tel, available_days):
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO ogretmenler (ad, soyad, brans, tc_kimlik_no, telefon_no, available_days)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ad, soyad, brans, tc, tel, available_days))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            messagebox.showwarning("Uyarı", "Bu TC Kimlik Numarasına sahip bir öğretmen zaten mevcut.")
            return False
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Öğretmen eklenirken bir hata oluştu: {e}")
            return False

    def get_teachers(self):
        if not self.conn: return []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ogretmenler ORDER BY ad, soyad")
        return [dict(row) for row in cursor.fetchall()]

    def get_teacher_by_id(self, teacher_id):
        if not self.conn: return None
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ogretmenler WHERE id = ?", (teacher_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_teacher(self, teacher_id, ad, soyad, brans, tc, tel, available_days):
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE ogretmenler
                SET ad = ?, soyad = ?, brans = ?, tc_kimlik_no = ?, telefon_no = ?, available_days = ?
                WHERE id = ?
            """, (ad, soyad, brans, tc, tel, available_days, teacher_id))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            messagebox.showwarning("Uyarı", "Bu TC Kimlik Numarası başka bir öğretmene ait.")
            return False
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Öğretmen güncellenirken bir hata oluştu: {e}")
            return False

    def delete_teacher(self, teacher_id):
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM ogretmenler WHERE id = ?", (teacher_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Öğretmen silinirken bir hata oluştu: {e}")
            return False

    # --- Nöbet İşlemleri ---
    def assign_duty(self, teacher_id, duty_location, duty_date):
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            date_str = duty_date.strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO nobetler (ogretmen_id, nobet_yeri, nobet_tarihi)
                VALUES (?, ?, ?)
            """, (teacher_id, duty_location, date_str))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Nöbet atanırken bir hata oluştu: {e}")
            return False

    def get_duties(self):
        if not self.conn: return []
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nobetler ORDER BY nobet_tarihi DESC, nobet_yeri")
        duties_list = []
        for row in cursor.fetchall():
            duty = dict(row)
            duty['nobet_tarihi'] = datetime.datetime.strptime(duty['nobet_tarihi'], '%Y-%m-%d').date()
            duties_list.append(duty)
        return duties_list

    def get_duty_by_id(self, duty_id):
        if not self.conn: return None
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM nobetler WHERE id = ?", (duty_id,))
        row = cursor.fetchone()
        if row:
            duty = dict(row)
            duty['nobet_tarihi'] = datetime.datetime.strptime(duty['nobet_tarihi'], '%Y-%m-%d').date()
            return duty
        return None

    def update_duty(self, duty_id, teacher_id, duty_location, duty_date):
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            date_str = duty_date.strftime('%Y-%m-%d')
            cursor.execute("""
                UPDATE nobetler
                SET ogretmen_id = ?, nobet_yeri = ?, nobet_tarihi = ?
                WHERE id = ?
            """, (teacher_id, duty_location, date_str, duty_id))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.IntegrityError:
            messagebox.showwarning("Uyarı", "Bu öğretmen aynı yerde aynı gün nöbet tutamaz.")
            return False
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Nöbet güncellenirken bir hata oluştu: {e}")
            return False

    def delete_duty(self, duty_id):
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM nobetler WHERE id = ?", (duty_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Nöbet silinirken bir hata oluştu: {e}")
            return False

    def get_teacher_duty_counts(self):
        """Tüm öğretmenlerin toplam nöbet sayılarını döner."""
        if not self.conn: return {}
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT ogretmen_id, COUNT(id) as duty_count
            FROM nobetler
            GROUP BY ogretmen_id
        """)
        return {row['ogretmen_id']: row['duty_count'] for row in cursor.fetchall()}

    def get_teacher_duty_counts_for_period(self, start_date, end_date):
        """Verilen tarih aralığında her öğretmenin nöbet sayısını döndürür."""
        if not self.conn: return {}
        cursor = self.conn.cursor()
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT ogretmen_id, COUNT(id) as duty_count
            FROM nobetler
            WHERE nobet_tarihi BETWEEN ? AND ?
            GROUP BY ogretmen_id
        """, (start_date_str, end_date_str))
        return {row['ogretmen_id']: row['duty_count'] for row in cursor.fetchall()}

    def get_duties_for_teacher(self, teacher_id):
        """Belirli bir öğretmenin tüm nöbetlerini tarihe göre sıralı olarak döner."""
        if not self.conn: return []
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT nobet_yeri, nobet_tarihi
            FROM nobetler
            WHERE ogretmen_id = ?
            ORDER BY nobet_tarihi DESC
        """, (teacher_id,))
        duties_list = []
        for row in cursor.fetchall():
            duty = dict(row)
            duty['nobet_tarihi'] = datetime.datetime.strptime(duty['nobet_tarihi'], '%Y-%m-%d').date()
            duties_list.append(duty)
        return duties_list
        
    def get_last_duty_location_for_teacher(self, teacher_id):
        if not self.conn: return None
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT nobet_yeri
            FROM nobetler
            WHERE ogretmen_id = ?
            ORDER BY nobet_tarihi DESC, id DESC
            LIMIT 1
        """, (teacher_id,))
        row = cursor.fetchone()
        return row['nobet_yeri'] if row else None

    # --- Nöbet Yeri İşlemleri ---
    def get_locations(self):
        """Veritabanındaki tüm nöbet yerlerini alfabetik olarak döner."""
        if not self.conn: return []
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT yer_adi FROM nobet_yerleri ORDER BY yer_adi")
            return [row['yer_adi'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Nöbet yerleri alınırken hata oluştu: {e}")
            return []

    def add_location(self, location_name):
        """Veritabanına yeni bir nöbet yeri ekler."""
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO nobet_yerleri (yer_adi) VALUES (?)", (location_name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            messagebox.showwarning("Uyarı", "Bu nöbet yeri zaten mevcut.")
            return False
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Nöbet yeri eklenirken bir hata oluştu: {e}")
            return False
            
    def update_location(self, old_name, new_name):
        """Bir nöbet yerinin adını günceller ve bu değişikliği tüm nöbet kayıtlarına yansıtır."""
        if not self.conn: return False
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE nobetler SET nobet_yeri = ? WHERE nobet_yeri = ?", (new_name, old_name))
            updated_duties_count = cursor.rowcount
            cursor.execute("UPDATE nobet_yerleri SET yer_adi = ? WHERE yer_adi = ?", (new_name, old_name))
            self.conn.commit()
            return True, updated_duties_count
        except sqlite3.IntegrityError:
            messagebox.showwarning("Uyarı", f"'{new_name}' adında bir nöbet yeri zaten mevcut.")
            self.conn.rollback() 
            return False, 0
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Nöbet yeri güncellenirken bir hata oluştu: {e}")
            self.conn.rollback() 
            return False, 0
            
    def delete_location(self, location_name):
        """Bir nöbet yerini siler. Eğer o yerde nöbet varsa silmez."""
        if not self.conn: return "error"
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1 FROM nobetler WHERE nobet_yeri = ? LIMIT 1", (location_name,))
            if cursor.fetchone():
                return "in_use" 

            cursor.execute("DELETE FROM nobet_yerleri WHERE yer_adi = ?", (location_name,))
            self.conn.commit()
            return "deleted" if cursor.rowcount > 0 else "not_found"
        except sqlite3.Error as e:
            messagebox.showerror("Veritabanı Hatası", f"Nöbet yeri silinirken bir hata oluştu: {e}")
            return "error"

# --- Sabitler ---
# DÜZELTME: Sistem dilinden bağımsız Türkçe gün isimleri listesi
week_days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# DejaVuSans yazı tipini yükle
try:
    # Fontun tam yolunu belirtmek daha güvenilir olabilir
    font_path = 'DejaVuSans.ttf' 
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    else:
        # Alternatif olarak sık kullanılan bir sistem fontu denenebilir
        # Bu kısım işletim sistemine göre değişebilir
        try:
            pdfmetrics.registerFont(TTFont('Arial', 'arial.ttf'))
            messagebox.showwarning("Yazı Tipi Uyarısı", "DejaVuSans.ttf bulunamadı. Alternatif olarak Arial kullanılacak.")
        except:
             messagebox.showwarning("Yazı Tipi Hatası", "DejaVuSans.ttf veya Arial fontu yüklenemedi. PDF raporları Türkçe karakterleri düzgün göstermeyebilir.")
except Exception as e:
    messagebox.showwarning("Yazı Tipi Hatası", f"Font yüklenemedi: {e}")
    

# --- YARDIMCI FONKSİYON ---
def create_weekly_grid_table(db_manager, duties, start_date):
    """Haftalık nöbetler için günleri sütun olarak gösteren bir tablo oluşturur."""
    duties_by_day = {i: [] for i in range(5)}
    for duty in duties:
        teacher = db_manager.get_teacher_by_id(duty['ogretmen_id'])
        if teacher:
            day_index = duty['nobet_tarihi'].weekday()
            if 0 <= day_index < 5:
                duty_text = f"{teacher['ad']} {teacher['soyad']}\n({duty['nobet_yeri']})"
                duties_by_day[day_index].append(duty_text)

    header_row = []
    for i in range(5):
        current_date = start_date + datetime.timedelta(days=i)
        # DÜZELTME: Gün ismini sistemden değil, kendi listemizden al
        day_name = week_days[current_date.weekday()]
        header_row.append(current_date.strftime(f'%d.%m.%Y\n{day_name}'))

    data_for_table = [header_row]
    max_duties_per_day = max(len(d) for d in duties_by_day.values()) if duties_by_day else 0

    for i in range(max_duties_per_day):
        row = []
        for day_index in range(5):
            row.append(duties_by_day[day_index][i] if i < len(duties_by_day[day_index]) else "")
        data_for_table.append(row)

    if max_duties_per_day == 0:
        data_for_table.append(["Bu hafta için nöbet bulunamadı.", "", "", "", ""])

    table = Table(data_for_table, colWidths=[1.5*inch] * 5)
    
    font_name = 'DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Arial'

    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#05244C")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), font_name), 
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#FFFFFF")),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1, colors.orange),
    ]
    
    if max_duties_per_day == 0:
        style_commands.append(('SPAN', (0, 1), (-1, 1)))

    table.setStyle(TableStyle(style_commands))
    return table

# --- PDF Raporlama Fonksiyonu ---
def generate_pdf_report(db_manager, report_type, start_date=None, end_date=None):
    doc_title = ""
    styles = getSampleStyleSheet()
    h1_style = styles['h1']
    normal_style = styles['Normal']
    
    font_name = 'DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Arial'
    h1_style.fontName = font_name
    normal_style.fontName = font_name
    
    if report_type == "weekly":
        doc_title = "Haftalık Nöbet Programı"
        if not start_date:
            today = datetime.date.today()
            start_date = today - datetime.timedelta(days=today.weekday())
        end_date = start_date + datetime.timedelta(days=4)
    elif report_type == "monthly":
        doc_title = "Aylık Nöbet Programı"
        if not start_date:
            today = datetime.date.today()
            start_date = datetime.date(today.year, today.month, 1)
        # DÜZELTME: Ay sonunu hesaplama hatası giderildi.
        # Güvenilir yöntem: Bir sonraki ayın ilk gününü bul ve 1 gün çıkar.
        if start_date.month == 12:
            first_day_of_next_month = datetime.date(start_date.year + 1, 1, 1)
        else:
            first_day_of_next_month = datetime.date(start_date.year, start_date.month + 1, 1)
        end_date = first_day_of_next_month - datetime.timedelta(days=1)
    elif report_type == "yearly":
        doc_title = "Yıllık Nöbet Programı"
        if not start_date:
            start_date = datetime.date(datetime.date.today().year, 1, 1)
        end_date = datetime.date(start_date.year, 12, 31)
    elif report_type == "all" or report_type == "custom":
        if not (start_date and end_date):
            all_dates = [d['nobet_tarihi'] for d in db_manager.get_duties()]
            if not all_dates:
                messagebox.showinfo("Bilgi", "PDF oluşturmak için nöbet bulunamadı.")
                return
            start_date, end_date = min(all_dates), max(all_dates)
        doc_title = "Tüm Nöbet Programı" if report_type == "all" else "Özel Tarih Aralığı Nöbet Programı"

    filtered_duties = [d for d in db_manager.get_duties() if start_date <= d['nobet_tarihi'] <= end_date]

    # DÜZELTME: Haftalık rapor dahil, eğer belirtilen aralıkta hiç nöbet yoksa
    # PDF oluşturmak yerine kullanıcıya bilgi ver. Bu, "boş rapor" sorununu çözer.
    if not filtered_duties:
        messagebox.showinfo("Bilgi", "Belirtilen tarih aralığında nöbet bulunamadı.")
        return

    filtered_duties.sort(key=lambda x: (x['nobet_tarihi'], x['nobet_yeri']))

    story = [
        Paragraph(doc_title, h1_style),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Rapor Tarihi Aralığı: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}", normal_style),
        Spacer(1, 0.2 * inch)
    ]

    if report_type == "weekly":
        table = create_weekly_grid_table(db_manager, filtered_duties, start_date)
    else:
        data_for_table = [['Tarih', 'Nöbet Yeri', 'Öğretmen Adı Soyadı', 'Branşı']]
        for duty in filtered_duties:
            teacher = db_manager.get_teacher_by_id(duty['ogretmen_id'])
            if teacher:
                # DÜZELTME: Gün ismini sistemden değil, kendi listemizden al
                day_name = week_days[duty['nobet_tarihi'].weekday()]
                date_with_day = duty['nobet_tarihi'].strftime(f'%d.%m.%Y {day_name}')
                data_for_table.append([
                    date_with_day, duty['nobet_yeri'],
                    f"{teacher['ad']} {teacher['soyad']}", teacher['brans']
                ])
        table = Table(data_for_table)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0E0F6E")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#B8BBED")),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
    
    story.append(table)
    try:
        file_name = f"{doc_title.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        doc = SimpleDocTemplate(file_name, pagesize=letter)
        doc.build(story)
        messagebox.showinfo("Başarılı", f"PDF raporu '{file_name}' olarak oluşturuldu.")
    except Exception as e:
        messagebox.showerror("Hata", f"PDF oluşturulurken bir hata oluştu: {e}")

# --- Ana Uygulama Sınıfı ---
class SchoolDutySchedulerApp:
    def __init__(self, master):
        self.master = master
        master.title("🗓️ Okul Nöbet Programı")
        master.geometry("1200x700")

        # --- YENİ: Stil Ayarları ---
        self.setup_styles()

        self.db_manager = DatabaseManager()
        if not self.db_manager.conn:
            master.destroy()
            return
            
        self.duty_locations = self.db_manager.get_locations()
        
        # YENİ: Çift nöbet tutanları renklendirmek için bir önceki hafta bilgisini tutacak değişken
        self._last_week_double_duty_teachers = set()

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.teacher_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.teacher_frame, text="👨‍🏫 Öğretmenler")
        self.create_teacher_tab(self.teacher_frame)

        self.duty_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.duty_frame, text="📅 Nöbet Programı")
        self.create_duty_tab(self.duty_frame)

        self.auto_schedule_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.auto_schedule_frame, text="🤖 Otomatik Nöbet")
        self.create_auto_schedule_tab(self.auto_schedule_frame)

        self.report_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.report_frame, text="📄 Raporlar")
        self.create_report_tab(self.report_frame)

        master.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.display_todays_duties()

    # --- YENİ: Modern bir görünüm için stil yapılandırma metodu ---
    def setup_styles(self):
        # Renk Paleti
        BG_COLOR = "#F0F2F5"          # Açık Gri (Ana Arka Plan)
        PRIMARY_COLOR = "#FF8800"      # Koyu Lacivert (Başlıklar, Butonlar)
        SECONDARY_COLOR = "#131650"    # Canlı Turkuaz (Vurgu, Seçim)
        TEXT_COLOR = "#333333"         # Koyu Gri (Genel Yazı)
        LIGHT_TEXT_COLOR = "#FFFFFF"   # Beyaz (Buton ve Başlık Yazıları)
        ENTRY_BG_COLOR = "#FFFFFF"     # Beyaz (Giriş Kutuları Arka Planı)
        
        self.master.configure(bg=BG_COLOR)
        style = ttk.Style(self.master)
        style.theme_use('clam')

        # Genel stil ayarları
        style.configure('.',
                        background=BG_COLOR,
                        foreground=TEXT_COLOR,
                        font=('Helvetica', 10))

        # Çerçeve Stilleri
        style.configure('TFrame', background=BG_COLOR)
        style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, padding=2)
        style.configure('TLabelFrame', background=BG_COLOR, bordercolor=PRIMARY_COLOR)
        style.configure('TLabelFrame.Label',
                        background=BG_COLOR,
                        foreground=PRIMARY_COLOR,
                        font=('Helvetica', 11, 'bold'),
                        padding=(10, 5))

        # Sekme (Notebook) Stilleri
        style.configure('TNotebook', background=BG_COLOR, borderwidth=0)
        style.configure('TNotebook.Tab',
                        background=PRIMARY_COLOR,
                        foreground=LIGHT_TEXT_COLOR,
                        font=('Helvetica', 10, 'bold'),
                        padding=[12, 6],
                        borderwidth=0)
        style.map('TNotebook.Tab',
                  background=[('selected', SECONDARY_COLOR), ('active', BG_COLOR)],
                  foreground=[('selected', LIGHT_TEXT_COLOR), ('active', PRIMARY_COLOR)])

        # Buton Stilleri
        style.configure('TButton',
                        background=PRIMARY_COLOR,
                        foreground=LIGHT_TEXT_COLOR,
                        font=('Helvetica', 10, 'bold'),
                        padding=8,
                        borderwidth=0,
                        relief='flat')
        style.map('TButton',
                  background=[('active', SECONDARY_COLOR), ('pressed', SECONDARY_COLOR)],
                  relief=[('pressed', 'flat')])
        
        # Giriş ve ComboBox Stilleri
        style.configure('TEntry',
                        fieldbackground=ENTRY_BG_COLOR,
                        borderwidth=1,
                        relief='solid',
                        padding=5)
        style.map('TCombobox',
                  fieldbackground=[('readonly', ENTRY_BG_COLOR)],
                  selectbackground=[('readonly', SECONDARY_COLOR)],
                  selectforeground=[('readonly', LIGHT_TEXT_COLOR)])

        # Checkbutton Stilleri
        style.configure('TCheckbutton',
                        background=BG_COLOR,
                        font=('Helvetica', 10))
        style.map('TCheckbutton',
                  indicatorcolor=[('selected', SECONDARY_COLOR), ('!selected', TEXT_COLOR)])

        # Treeview (Liste) Stilleri
        style.configure('Treeview',
                        rowheight=28,
                        fieldbackground=ENTRY_BG_COLOR,
                        background=ENTRY_BG_COLOR,
                        borderwidth=0,
                        relief='flat')
        style.map('Treeview', background=[('selected', SECONDARY_COLOR)])
        
        style.configure('Treeview.Heading',
                        background=PRIMARY_COLOR,
                        foreground=LIGHT_TEXT_COLOR,
                        font=('Helvetica', 10, 'bold'),
                        padding=8)
        style.map('Treeview.Heading', background=[('active', SECONDARY_COLOR)])


    def on_closing(self):
        if self.db_manager:
            self.db_manager.close()
        self.master.destroy()

    def create_teacher_tab(self, parent_frame):
        left_panel = ttk.Frame(parent_frame)
        left_panel.pack(side="left", fill="y", padx=10, pady=10)

        form_frame = ttk.LabelFrame(left_panel, text="ℹ️ Öğretmen Bilgileri")
        form_frame.pack(side="top", fill="x")

        labels = ["Adı:", "Soyadı:", "Branşı:", "TC Kimlik No:", "Telefon No:"]
        self.teacher_entries = {}
        for i, label_text in enumerate(labels):
            ttk.Label(form_frame, text=label_text).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            entry = ttk.Entry(form_frame, width=30)
            entry.grid(row=i, column=1, padx=5, pady=5, sticky="ew")
            self.teacher_entries[label_text.replace(":", "").strip()] = entry

        ttk.Label(form_frame, text="Nöbet Tutabileceği Günler:").grid(row=len(labels), column=0, padx=5, pady=5, sticky="nw")
        self.available_days_vars = {}
        days_frame = ttk.Frame(form_frame)
        days_frame.grid(row=len(labels), column=1, padx=5, pady=5, sticky="ew")

        teacher_week_days = week_days[:5]
        for i, day in enumerate(teacher_week_days):
            var = tk.BooleanVar(value=True)
            cb = ttk.Checkbutton(days_frame, text=day, variable=var)
            cb.grid(row=i // 3, column=i % 3, sticky="w")
            self.available_days_vars[day] = var

        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=len(labels) + 2, column=0, columnspan=2, pady=10)
        
        button_texts = ["➕ Ekle", "🔄 Güncelle", "🗑️ Sil", "🧹 Temizle"]
        commands = [self.add_teacher_gui, self.update_teacher_gui, self.delete_teacher_gui, self.clear_teacher_form]
        for text, command in zip(button_texts, commands):
            ttk.Button(button_frame, text=text, command=command).pack(side="left", padx=5)

        teacher_duty_list_frame = ttk.LabelFrame(left_panel, text="📋 Seçili Öğretmenin Nöbetleri")
        teacher_duty_list_frame.pack(side="bottom", fill="both", expand=True, pady=(10, 0))

        duty_columns = ("Tarih", "Gün", "Nöbet Yeri")
        self.teacher_duty_tree = ttk.Treeview(teacher_duty_list_frame, columns=duty_columns, show="headings")
        for col in duty_columns:
            self.teacher_duty_tree.heading(col, text=col)
        self.teacher_duty_tree.column("Tarih", width=80, anchor="center")
        self.teacher_duty_tree.column("Gün", width=70, anchor="center")
        self.teacher_duty_tree.pack(fill="both", expand=True)

        list_frame = ttk.LabelFrame(parent_frame, text="👥 Öğretmen Listesi")
        list_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        columns = ("ID", "Adı", "Soyadı", "Branşı", "Müsait Günler", "Toplam", "Bu Ay", "Bu Yıl")
        self.teacher_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        for col in columns: self.teacher_tree.heading(col, text=col)
        
        col_widths = {"ID": 40, "Adı": 100, "Soyadı": 100, "Branşı": 80, "Müsait Günler": 200, "Toplam": 50, "Bu Ay": 50, "Bu Yıl": 50}
        for col, width in col_widths.items():
            self.teacher_tree.column(col, width=width, anchor="center" if col not in ["Adı", "Soyadı", "Müsait Günler"] else "w")

        self.teacher_tree.pack(fill="both", expand=True)
        self.teacher_tree.bind("<<TreeviewSelect>>", self.load_teacher_to_form)
        self.refresh_teacher_list()

    def refresh_teacher_list(self):
        for item in self.teacher_tree.get_children():
            self.teacher_tree.delete(item)
        
        teachers = self.db_manager.get_teachers()
        total_counts = self.db_manager.get_teacher_duty_counts()
        
        today = datetime.date.today()
        month_start, year_start = today.replace(day=1), today.replace(month=1, day=1)
        next_month_start = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        month_end, year_end = next_month_start - datetime.timedelta(days=1), today.replace(month=12, day=31)
        
        monthly_counts = self.db_manager.get_teacher_duty_counts_for_period(month_start, month_end)
        yearly_counts = self.db_manager.get_teacher_duty_counts_for_period(year_start, year_end)

        for teacher in teachers:
            teacher_id = teacher['id']
            self.teacher_tree.insert("", "end", values=(
                teacher_id, teacher['ad'], teacher['soyad'], teacher['brans'], 
                teacher['available_days'], total_counts.get(teacher_id, 0),
                monthly_counts.get(teacher_id, 0), yearly_counts.get(teacher_id, 0)
            ))

    def get_selected_days(self):
        return ",".join(sorted([day for day, var in self.available_days_vars.items() if var.get()], key=week_days.index))

    def set_selected_days(self, days_str):
        days_list = days_str.split(',') if days_str else []
        for day, var in self.available_days_vars.items():
            var.set(day in days_list)

    def add_teacher_gui(self):
        ad = self.teacher_entries["Adı"].get().strip()
        soyad = self.teacher_entries["Soyadı"].get().strip()
        brans = self.teacher_entries["Branşı"].get().strip()
        tc = self.teacher_entries["TC Kimlik No"].get().strip()
        tel = self.teacher_entries["Telefon No"].get().strip()
        available_days = self.get_selected_days()

        if not all([ad, soyad, brans, tc]):
            messagebox.showwarning("Eksik Bilgi", "Ad, Soyad, Branş ve TC Kimlik No alanları zorunludur.")
            return
        if not tc.isdigit() or len(tc) != 11:
            messagebox.showwarning("Geçersiz TC", "TC Kimlik No 11 haneli ve rakamlardan oluşmalıdır.")
            return
        if not available_days:
            messagebox.showwarning("Eksik Bilgi", "Lütfen öğretmenin nöbet tutabileceği en az bir gün seçin.")
            return

        if self.db_manager.add_teacher(ad, soyad, brans, tc, tel, available_days):
            messagebox.showinfo("Başarılı", "Öğretmen başarıyla eklendi.")
            self.refresh_teacher_list()
            self.clear_teacher_form()
            self.update_teacher_dropdowns()

    def update_teacher_gui(self):
        selected_item = self.teacher_tree.selection()
        if not selected_item:
            messagebox.showwarning("Seçim Yok", "Lütfen güncellemek için bir öğretmen seçin.")
            return

        teacher_id = self.teacher_tree.item(selected_item, "values")[0]
        ad, soyad, brans, tc, tel = (self.teacher_entries[key].get().strip() for key in ["Adı", "Soyadı", "Branşı", "TC Kimlik No", "Telefon No"])
        available_days = self.get_selected_days()

        if not all([ad, soyad, brans, tc]):
            messagebox.showwarning("Eksik Bilgi", "Ad, Soyad, Branş ve TC Kimlik No alanları zorunludur.")
            return
        if not tc.isdigit() or len(tc) != 11:
            messagebox.showwarning("Geçersiz TC", "TC Kimlik No 11 haneli ve rakamlardan oluşmalıdır.")
            return
        if not available_days:
            messagebox.showwarning("Eksik Bilgi", "Lütfen öğretmenin nöbet tutabileceği en az bir gün seçin.")
            return

        if self.db_manager.update_teacher(int(teacher_id), ad, soyad, brans, tc, tel, available_days):
            messagebox.showinfo("Başarılı", "Öğretmen bilgileri güncellendi.")
            self.refresh_teacher_list()
            self.clear_teacher_form()
            self.update_teacher_dropdowns()

    def delete_teacher_gui(self):
        selected_item = self.teacher_tree.selection()
        if not selected_item:
            messagebox.showwarning("Seçim Yok", "Lütfen silmek için bir öğretmen seçin.")
            return

        teacher_id, ad, soyad = self.teacher_tree.item(selected_item, "values")[:3]
        if messagebox.askyesno("Silme Onayı", f"'{ad} {soyad}' adlı öğretmeni ve tüm nöbetlerini silmek istediğinizden emin misiniz?"):
            if self.db_manager.delete_teacher(int(teacher_id)):
                messagebox.showinfo("Başarılı", "Öğretmen ve ilgili nöbetler başarıyla silindi.")
                self.refresh_teacher_list()
                self.refresh_duty_list()
                self.clear_teacher_form()
                self.update_teacher_dropdowns()

    def load_teacher_to_form(self, event):
        for item in self.teacher_duty_tree.get_children():
            self.teacher_duty_tree.delete(item)

        selected_item = self.teacher_tree.selection()
        if selected_item:
            values = self.teacher_tree.item(selected_item, "values")
            teacher_id = values[0]
            teacher_data = self.db_manager.get_teacher_by_id(teacher_id)
            if not teacher_data: return

            self.teacher_entries["Adı"].delete(0, tk.END); self.teacher_entries["Adı"].insert(0, teacher_data['ad'])
            self.teacher_entries["Soyadı"].delete(0, tk.END); self.teacher_entries["Soyadı"].insert(0, teacher_data['soyad'])
            self.teacher_entries["Branşı"].delete(0, tk.END); self.teacher_entries["Branşı"].insert(0, teacher_data['brans'])
            self.teacher_entries["TC Kimlik No"].delete(0, tk.END); self.teacher_entries["TC Kimlik No"].insert(0, teacher_data['tc_kimlik_no'])
            self.teacher_entries["Telefon No"].delete(0, tk.END); self.teacher_entries["Telefon No"].insert(0, teacher_data['telefon_no'])
            self.set_selected_days(teacher_data['available_days'])

            for duty in self.db_manager.get_duties_for_teacher(int(teacher_id)):
                duty_date = duty['nobet_tarihi']
                self.teacher_duty_tree.insert("", "end", values=(
                    duty_date.strftime('%d.%m.%Y'), week_days[duty_date.weekday()], duty['nobet_yeri']
                ))

    def clear_teacher_form(self):
        for entry in self.teacher_entries.values():
            entry.delete(0, tk.END)
        self.set_selected_days("Pazartesi,Salı,Çarşamba,Perşembe,Cuma")
        if self.teacher_tree.selection():
            self.teacher_tree.selection_remove(self.teacher_tree.selection()[0])
        for item in self.teacher_duty_tree.get_children():
            self.teacher_duty_tree.delete(item)

    def create_duty_tab(self, parent_frame):
        left_panel = ttk.Frame(parent_frame)
        left_panel.pack(side="left", fill="y", padx=10, pady=10)
        right_panel = ttk.Frame(parent_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        form_frame = ttk.LabelFrame(left_panel, text="✍️ Nöbet Atama")
        form_frame.pack(side="top", fill="x", anchor="n")
        
        ttk.Label(form_frame, text="Öğretmen:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.teacher_combo = ttk.Combobox(form_frame, width=30, state="readonly")
        self.teacher_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.update_teacher_dropdowns()

        ttk.Label(form_frame, text="Nöbet Yeri:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.duty_location_combo = ttk.Combobox(form_frame, values=self.duty_locations, width=30, state="readonly")
        self.duty_location_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(form_frame, text="Tarih (GG.AA.YYYY):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.duty_date_entry = ttk.Entry(form_frame, width=30)
        self.duty_date_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        self.duty_date_entry.insert(0, datetime.date.today().strftime('%d.%m.%Y'))

        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        btn_texts = ["➕ Ata", "🔄 Güncelle", "🗑️ Sil", "🧹 Temizle"]
        btn_cmds = [self.assign_duty_gui, self.update_duty_gui, self.delete_duty_gui, self.clear_duty_form]
        for text, cmd in zip(btn_texts, btn_cmds):
            ttk.Button(button_frame, text=f"Nöbet {text}", command=cmd).pack(side="left", padx=5)

        duty_location_frame = ttk.LabelFrame(left_panel, text="📍 Nöbet Yeri Yönetimi")
        duty_location_frame.pack(side="top", fill="x", anchor="n", pady=(10,0))
        ttk.Label(duty_location_frame, text="Nöbet Yeri Adı:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.new_duty_location_entry = ttk.Entry(duty_location_frame, width=20)
        self.new_duty_location_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        loc_button_frame = ttk.Frame(duty_location_frame)
        loc_button_frame.grid(row=1, column=0, columnspan=2)
        loc_btn_texts = ["➕ Ekle", "🔄 Güncelle", "🗑️ Sil"]
        loc_btn_cmds = [self.add_new_duty_location, self.update_duty_location, self.delete_duty_location]
        for text, cmd in zip(loc_btn_texts, loc_btn_cmds):
            ttk.Button(loc_button_frame, text=text, command=cmd).pack(side="left", padx=5)

        list_search_frame = ttk.LabelFrame(right_panel, text="🔍 Nöbet Programı ve Arama")
        list_search_frame.pack(side="top", fill="both", expand=True)

        search_frame = ttk.Frame(list_search_frame)
        search_frame.pack(fill="x", padx=5, pady=5)
        ttk.Label(search_frame, text="Kişi Ara:").pack(side="left", padx=(0, 5))
        self.search_teacher_entry = ttk.Entry(search_frame, width=20)
        self.search_teacher_entry.pack(side="left", padx=5)
        ttk.Label(search_frame, text="Tarih Ara:").pack(side="left", padx=(10, 5))
        self.search_date_entry = ttk.Entry(search_frame, width=15)
        self.search_date_entry.pack(side="left", padx=5)
        ttk.Label(search_frame, text="Yer Ara:").pack(side="left", padx=(10, 5))
        self.search_location_combo = ttk.Combobox(search_frame, values=["Tümü"] + self.duty_locations, width=15, state="readonly")
        self.search_location_combo.set("Tümü")
        self.search_location_combo.pack(side="left", padx=5)
        ttk.Button(search_frame, text="🔍 Ara", command=self.search_duties).pack(side="left", padx=10)
        ttk.Button(search_frame, text="🧹 Temizle", command=self.clear_search_and_show_all_duties).pack(side="left", padx=5)


        self.duty_tree = ttk.Treeview(list_search_frame, columns=("ID", "Öğretmen Adı Soyadı", "Nöbet Yeri", "Tarih"), show="headings")
        self.duty_tree.heading("ID", text="ID"); self.duty_tree.column("ID", width=40, anchor="center")
        self.duty_tree.heading("Öğretmen Adı Soyadı", text="Öğretmen Adı Soyadı"); self.duty_tree.column("Öğretmen Adı Soyadı", width=200)
        self.duty_tree.heading("Nöbet Yeri", text="Nöbet Yeri"); self.duty_tree.column("Nöbet Yeri", width=120, anchor="center")
        self.duty_tree.heading("Tarih", text="Tarih"); self.duty_tree.column("Tarih", width=100, anchor="center")
        self.duty_tree.pack(fill="both", expand=True, pady=(5,0))
        self.duty_tree.bind("<<TreeviewSelect>>", self.load_duty_to_form)
        
        # GÜNCELLEME: Çift nöbet renklendirmesi için yeni renk
        self.duty_tree.tag_configure('double_duty', background='#FFF0E1', foreground='#E74C3C')

        today = datetime.date.today()
        today_str = today.strftime(f"%d.%m.%Y {week_days[today.weekday()]}")
        today_frame = ttk.LabelFrame(right_panel, text=f"📌 Bugünün Nöbetçileri ({today_str})")
        today_frame.pack(side="bottom", fill="x", pady=(10, 0))
        self.todays_duty_label = ttk.Label(today_frame, text="Yükleniyor...", font=("Helvetica", 10, "bold"), wraplength=700, justify="center")
        self.todays_duty_label.pack(padx=10, pady=10)

        self.refresh_duty_list()

    def display_todays_duties(self):
        today = datetime.date.today()
        todays_duties = [d for d in self.db_manager.get_duties() if d['nobet_tarihi'] == today]
        
        if not todays_duties:
            display_text = "Bugün için kayıtlı nöbet bulunmamaktadır."
        else:
            todays_duties.sort(key=lambda x: x['nobet_yeri'])
            duty_texts = []
            for duty in todays_duties:
                teacher = self.db_manager.get_teacher_by_id(duty['ogretmen_id'])
                if teacher:
                    duty_texts.append(f"📍 {duty['nobet_yeri']}: {teacher['ad']} {teacher['soyad']}")
            display_text = "  |  ".join(duty_texts)
        
        if hasattr(self, 'todays_duty_label'):
            self.todays_duty_label.config(text=display_text)

    def update_teacher_dropdowns(self):
        teachers = self.db_manager.get_teachers()
        self.teacher_combo['values'] = [f"{t['ad']} {t['soyad']} (ID: {t['id']})" for t in teachers]
        if teachers: self.teacher_combo.set(self.teacher_combo['values'][0])
        else: self.teacher_combo.set('')

    def refresh_duty_list(self, filtered_duties=None):
        for item in self.duty_tree.get_children():
            self.duty_tree.delete(item)

        duties_to_show = filtered_duties if filtered_duties is not None else self.db_manager.get_duties()
        
        # DÜZELTME: Bu satır TypeError hatasına neden oluyordu.
        # teacher_weekly_duty_count = defaultdict(lambda: defaultdict(int)) -> YANLIŞ
        teacher_weekly_duty_count = defaultdict(int) # -> DOĞRU

        for duty in duties_to_show:
            teacher = self.db_manager.get_teacher_by_id(duty['ogretmen_id'])
            if not teacher: # Eğer öğretmen silinmişse ama nöbeti kalmışsa (normalde olmamalı)
                continue
            teacher_name = f"{teacher['ad']} {teacher['soyad']}"
            
            # Renklendirme için tag ataması
            tags = ()
            year, week, _ = duty['nobet_tarihi'].isocalendar()
            # Anahtar olarak (yıl, hafta, öğretmen_id) kullanılıyor
            key = (year, week, teacher['id'])
            teacher_weekly_duty_count[key] += 1
            if teacher_weekly_duty_count[key] > 1:
                tags = ('double_duty',)

            self.duty_tree.insert("", "end", values=(
                duty['id'], teacher_name, duty['nobet_yeri'], duty['nobet_tarihi'].strftime('%d.%m.%Y')
            ), tags=tags)
            
        self.refresh_teacher_list()
        self.display_todays_duties()


    def assign_duty_gui(self):
        selected_teacher_str = self.teacher_combo.get()
        duty_location = self.duty_location_combo.get()
        duty_date_str = self.duty_date_entry.get().strip()

        if not selected_teacher_str or not duty_location or not duty_date_str:
            messagebox.showwarning("Eksik Bilgi", "Lütfen tüm nöbet bilgilerini doldurun.")
            return

        try:
            teacher_id = int(selected_teacher_str.split('(ID: ')[1][:-1])
            duty_date = datetime.datetime.strptime(duty_date_str, '%d.%m.%Y').date()
        except (ValueError, IndexError):
            messagebox.showerror("Hata", "Öğretmen veya tarih formatı hatalı. Lütfen kontrol edin.")
            return

        teacher_info = self.db_manager.get_teacher_by_id(teacher_id)
        if teacher_info:
            day_of_week_turkish = week_days[duty_date.weekday()]
            if day_of_week_turkish not in teacher_info.get('available_days', ''):
                messagebox.showwarning("Uyarı", f"{teacher_info['ad']} {teacher_info['soyad']} adlı öğretmen, {day_of_week_turkish} günü nöbet tutmaya müsait değil.")
                return

        if self.db_manager.assign_duty(teacher_id, duty_location, duty_date):
            messagebox.showinfo("Başarılı", "Nöbet başarıyla atandı.")
            self.refresh_duty_list()
            self.clear_duty_form()
        else:
            messagebox.showwarning("Uyarı", "Bu öğretmene bu yerde ve tarihte zaten nöbet atanmış veya bir veritabanı hatası oluştu.")

    def update_duty_gui(self):
        selected_item = self.duty_tree.selection()
        if not selected_item:
            messagebox.showwarning("Seçim Yok", "Lütfen güncellemek için bir nöbet seçin.")
            return

        duty_id = self.duty_tree.item(selected_item, "values")[0]
        selected_teacher_str, duty_location, duty_date_str = self.teacher_combo.get(), self.duty_location_combo.get(), self.duty_date_entry.get().strip()

        if not all([selected_teacher_str, duty_location, duty_date_str]):
            messagebox.showwarning("Eksik Bilgi", "Lütfen tüm nöbet bilgilerini doldurun.")
            return

        try:
            teacher_id = int(selected_teacher_str.split('(ID: ')[1][:-1])
            duty_date = datetime.datetime.strptime(duty_date_str, '%d.%m.%Y').date()
        except (ValueError, IndexError):
            messagebox.showerror("Hata", "Öğretmen veya tarih formatı hatalı.")
            return

        teacher_info = self.db_manager.get_teacher_by_id(teacher_id)
        if teacher_info and week_days[duty_date.weekday()] not in teacher_info.get('available_days', ''):
            messagebox.showwarning("Uyarı", f"{teacher_info['ad']} {teacher_info['soyad']} adlı öğretmen, {week_days[duty_date.weekday()]} günü nöbet tutmaya müsait değil.")
            return

        if self.db_manager.update_duty(int(duty_id), teacher_id, duty_location, duty_date):
            messagebox.showinfo("Başarılı", "Nöbet bilgileri güncellendi.")
            self.refresh_duty_list()
            self.clear_duty_form()

    def delete_duty_gui(self):
        selected_item = self.duty_tree.selection()
        if not selected_item:
            messagebox.showwarning("Seçim Yok", "Lütfen silmek için bir nöbet seçin.")
            return

        duty_id = self.duty_tree.item(selected_item, "values")[0]
        if messagebox.askyesno("Silme Onayı", "Seçili nöbeti silmek istediğinizden emin misiniz?"):
            if self.db_manager.delete_duty(int(duty_id)):
                messagebox.showinfo("Başarılı", "Nöbet başarıyla silindi.")
                self.refresh_duty_list()
                self.clear_duty_form()

    def load_duty_to_form(self, event):
        selected_item = self.duty_tree.selection()
        if selected_item:
            duty_id = self.duty_tree.item(selected_item, "values")[0]
            duty = self.db_manager.get_duty_by_id(duty_id)
            if duty:
                teacher = self.db_manager.get_teacher_by_id(duty['ogretmen_id'])
                if teacher:
                    self.teacher_combo.set(f"{teacher['ad']} {teacher['soyad']} (ID: {teacher['id']})")
                self.duty_location_combo.set(duty['nobet_yeri'])
                self.duty_date_entry.delete(0, tk.END)
                self.duty_date_entry.insert(0, duty['nobet_tarihi'].strftime('%d.%m.%Y'))

    def clear_duty_form(self):
        self.teacher_combo.set('')
        self.duty_location_combo.set('')
        self.duty_date_entry.delete(0, tk.END)
        self.duty_date_entry.insert(0, datetime.date.today().strftime('%d.%m.%Y'))
        if self.duty_tree.selection():
            self.duty_tree.selection_remove(self.duty_tree.selection()[0])

    def refresh_duty_location_widgets(self):
        self.duty_locations = self.db_manager.get_locations()
        self.duty_location_combo['values'] = self.duty_locations
        self.search_location_combo['values'] = ["Tümü"] + self.duty_locations
        self.new_duty_location_entry.delete(0, tk.END)

    def add_new_duty_location(self):
        new_location = self.new_duty_location_entry.get().strip()
        if not new_location:
            messagebox.showwarning("Uyarı", "Lütfen geçerli bir nöbet yeri girin.")
            return

        if self.db_manager.add_location(new_location):
            messagebox.showinfo("Başarılı", f"'{new_location}' nöbet yeri eklendi.")
            self.refresh_duty_location_widgets()

    def update_duty_location(self):
        selected_location, new_name = self.duty_location_combo.get(), self.new_duty_location_entry.get().strip()
        if not selected_location:
            messagebox.showwarning("Uyarı", "Lütfen güncellenecek mevcut bir nöbet yeri seçin.")
            return
        if not new_name:
            messagebox.showwarning("Uyarı", "Yeni nöbet yeri adını girin.")
            return
        if selected_location == new_name: return

        success, count = self.db_manager.update_location(selected_location, new_name)
        if success:
            messagebox.showinfo("Başarılı", f"'{selected_location}' -> '{new_name}' olarak güncellendi.\nİlişkili {count} nöbet kaydı da güncellendi.")
            self.refresh_duty_location_widgets()
            self.refresh_duty_list()
            self.duty_location_combo.set(new_name)

    def delete_duty_location(self):
        selected_location = self.duty_location_combo.get()
        if not selected_location:
            messagebox.showwarning("Uyarı", "Lütfen silinecek bir nöbet yeri seçin.")
            return
        if not messagebox.askyesno("Silme Onayı", f"'{selected_location}' nöbet yerini silmek istediğinizden emin misiniz?"):
            return
            
        result = self.db_manager.delete_location(selected_location)
        if result == "deleted":
            messagebox.showinfo("Başarılı", f"'{selected_location}' nöbet yeri silindi.")
            self.refresh_duty_location_widgets(); self.duty_location_combo.set('')
        elif result == "in_use":
            messagebox.showwarning("Uyarı", f"'{selected_location}' nöbet yerinde atanmış nöbetler var. Bu yeri silemezsiniz.")
        else:
             messagebox.showerror("Hata", "Silme işlemi sırasında bir hata oluştu.")

    def search_duties(self):
        search_teacher, search_date, search_loc = self.search_teacher_entry.get().strip().lower(), self.search_date_entry.get().strip(), self.search_location_combo.get()
        all_duties = self.db_manager.get_duties()
        
        def check(duty):
            teacher = self.db_manager.get_teacher_by_id(duty['ogretmen_id'])
            teacher_name = f"{teacher['ad']} {teacher['soyad']}".lower() if teacher else ""
            
            teacher_match = not search_teacher or search_teacher in teacher_name
            date_match = not search_date or search_date in duty['nobet_tarihi'].strftime('%d.%m.%Y')
            loc_match = search_loc == "Tümü" or search_loc == duty['nobet_yeri']
            return teacher_match and date_match and loc_match

        filtered = [d for d in all_duties if check(d)]
        self.refresh_duty_list(filtered)

    def clear_search_and_show_all_duties(self):
        self.search_teacher_entry.delete(0, tk.END)
        self.search_date_entry.delete(0, tk.END)
        self.search_location_combo.set("Tümü")
        self.refresh_duty_list()

    def create_report_tab(self, parent_frame):
        pdf_reports_frame = ttk.LabelFrame(parent_frame, text="📄 PDF Raporları")
        pdf_reports_frame.pack(padx=10, pady=10, fill="x")

        report_types = {"Haftalık": "weekly", "Aylık": "monthly", "Yıllık": "yearly", "Tüm Nöbetler": "all"}
        for text, type_ in report_types.items():
             ttk.Button(pdf_reports_frame, text=f"📄 {text} Raporu", command=lambda t=type_: generate_pdf_report(self.db_manager, t)).pack(side="top", pady=5, fill="x")

        custom_report_frame = ttk.LabelFrame(pdf_reports_frame, text="📅 Özel Tarih Aralığı Raporu")
        custom_report_frame.pack(padx=5, pady=(10,5), fill="x")
        ttk.Label(custom_report_frame, text="Başlangıç Tarihi:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.custom_start_date_entry = ttk.Entry(custom_report_frame, width=20)
        self.custom_start_date_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(custom_report_frame, text="Bitiş Tarihi:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.custom_end_date_entry = ttk.Entry(custom_report_frame, width=20)
        self.custom_end_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(custom_report_frame, text="📄 Tarih Aralığı Raporu Oluştur", command=self.generate_custom_date_pdf_report).grid(row=2, column=0, columnspan=2, padx=5, pady=10, sticky="ew")

        excel_report_frame = ttk.LabelFrame(parent_frame, text="📈 Excel Raporları")
        excel_report_frame.pack(padx=10, pady=10, fill="x")
        ttk.Button(excel_report_frame, text="📈 Tüm Nöbetleri Excel'e Aktar", command=self.export_all_duties_to_excel).pack(side="top", pady=5, fill="x")

        # --- YENİ EKLENEN BÖLÜM ---
        about_frame = ttk.LabelFrame(parent_frame, text="💡 Hakkında")
        about_frame.pack(padx=10, pady=10, fill="x")
        ttk.Button(about_frame, text="👨‍💻 Geliştirici Bilgisi", command=self.show_about_info).pack(side="top", pady=5, fill="x")
        # --- YENİ BÖLÜM SONU ---

    # --- YENİ EKLENEN METOT ---
    def show_about_info(self):
        """Geliştirici bilgilerini gösteren bir bilgi kutusu açar."""
        messagebox.showinfo(
            "Geliştirici Bilgisi",
            "Bu uygulama Emrullah ALKAÇ tarafından geliştirilmiştir.\n\n"
            "Bilgi için 0542 694 98 90 numarasına ya da\n"
            "kimyoremr@gmail.com adresine başvurabilirsiniz."
        )
    # --- YENİ METOT SONU ---

    def generate_custom_date_pdf_report(self):
        start_date_str, end_date_str = self.custom_start_date_entry.get().strip(), self.custom_end_date_entry.get().strip()
        if not start_date_str or not end_date_str:
            messagebox.showwarning("Eksik Bilgi", "Lütfen başlangıç ve bitiş tarihlerini girin.")
            return
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y').date()
            end_date = datetime.datetime.strptime(end_date_str, '%d.%m.%Y').date()
            if start_date > end_date:
                messagebox.showwarning("Tarih Hatası", "Başlangıç tarihi bitiş tarihinden sonra olamaz.")
                return
        except ValueError:
            messagebox.showerror("Hata", "Tarih formatı hatalı. Lütfen GG.AA.YYYY formatında girin.")
            return
        generate_pdf_report(self.db_manager, "custom", start_date, end_date)
        
    def export_all_duties_to_excel(self):
        if not OPENPYXL_AVAILABLE:
            messagebox.showerror("Eksik Kütüphane", "Excel'e aktarma özelliği için 'openpyxl' kütüphanesi gereklidir.\nLütfen terminale 'pip install openpyxl' komutunu yazarak yükleyin.")
            return
            
        all_duties = sorted(self.db_manager.get_duties(), key=lambda x: x['nobet_tarihi'])
        if not all_duties:
            messagebox.showinfo("Bilgi", "Dışa aktarılacak nöbet bulunamadı.")
            return
            
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Tüm Nöbet Raporu"
        
        headers = ["Tarih", "Gün", "Nöbet Yeri", "Öğretmen Adı", "Öğretmen Soyadı", "Branşı"]
        sheet.append(headers)
        
        header_font = openpyxl.styles.Font(bold=True, color="FFFFFF")
        header_fill = openpyxl.styles.PatternFill("solid", fgColor="4F81BD")
        for cell in sheet[1]: cell.font, cell.fill = header_font, header_fill

        for duty in all_duties:
            teacher = self.db_manager.get_teacher_by_id(duty['ogretmen_id'])
            if teacher:
                sheet.append([
                    duty['nobet_tarihi'].strftime('%d.%m.%Y'),
                    week_days[duty['nobet_tarihi'].weekday()],
                    duty['nobet_yeri'], teacher['ad'], teacher['soyad'], teacher['brans']
                ])
        
        for col in sheet.columns:
            max_length = 0
            for cell in col:
                if len(str(cell.value)) > max_length: max_length = len(str(cell.value))
            sheet.column_dimensions[col[0].column_letter].width = max_length + 2
        
        try:
            file_name = f"Tum_Nobet_Raporu_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            workbook.save(file_name)
            messagebox.showinfo("Başarılı", f"Rapor başarıyla '{file_name}' olarak kaydedildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Excel dosyası kaydedilirken bir hata oluştu: {e}")

    def create_auto_schedule_tab(self, parent_frame):
        auto_frame = ttk.LabelFrame(parent_frame, text="⚙️ Otomatik Haftalık Nöbet Programı Oluşturma")
        auto_frame.pack(padx=10, pady=10, fill="both", expand=True)

        ttk.Label(auto_frame, text="Başlangıç Haftası (GG.AA.YYYY):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.auto_schedule_start_date_entry = ttk.Entry(auto_frame, width=30)
        self.auto_schedule_start_date_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.auto_schedule_start_date_entry.insert(0, datetime.date.today().strftime('%d.%m.%Y'))
        ttk.Button(auto_frame, text="🤖 Haftalık Program Oluştur", command=self.generate_weekly_schedule_gui).grid(row=1, column=0, columnspan=2, padx=5, pady=10)

        self.auto_schedule_tree = ttk.Treeview(auto_frame, columns=("Tarih", "Gün", "Nöbet Yeri", "Öğretmen"), show="headings")
        for col_text in ("Tarih", "Gün", "Nöbet Yeri", "Öğretmen"):
            self.auto_schedule_tree.heading(col_text, text=col_text)
        self.auto_schedule_tree.column("Tarih", width=100, anchor="center")
        self.auto_schedule_tree.column("Gün", width=80, anchor="center")
        self.auto_schedule_tree.column("Nöbet Yeri", width=150)
        self.auto_schedule_tree.column("Öğretmen", width=200)
        self.auto_schedule_tree.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        
        # GÜNCELLEME: Çift nöbet renklendirmesi için yeni renk
        self.auto_schedule_tree.tag_configure('double_duty', background='#FFF0E1', foreground='#E74C3C')
        
        auto_frame.grid_rowconfigure(2, weight=1); auto_frame.grid_columnconfigure(1, weight=1)

    def generate_weekly_schedule_gui(self):
        start_date_str = self.auto_schedule_start_date_entry.get().strip()
        try:
            start_date = datetime.datetime.strptime(start_date_str, '%d.%m.%Y').date()
            start_of_week = start_date - datetime.timedelta(days=start_date.weekday())
        except ValueError:
            messagebox.showerror("Hata", "Tarih formatı hatalı. Lütfen GG.AA.YYYY formatında girin.")
            return

        if not messagebox.askyesno("Onay", f"{start_of_week.strftime('%d.%m.%Y')} haftası için otomatik nöbet programı oluşturulsun mu?"):
            return

        created_duties = self.generate_weekly_schedule(start_of_week)
        if created_duties:
            messagebox.showinfo("Başarılı", f"{len(created_duties)} adet nöbet başarıyla oluşturuldu ve programa eklendi.")
            self.refresh_duty_list()
            self.display_auto_schedule_results(created_duties)
        else:
            messagebox.showinfo("Bilgi", "Bu hafta için yeni nöbet oluşturulamadı. Yeterli öğretmen veya uygun yer olmayabilir.")
            self.display_auto_schedule_results([])

    def generate_weekly_schedule(self, start_of_week):
        teachers = self.db_manager.get_teachers()
        if not teachers:
            messagebox.showwarning("Uyarı", "Öğretmen bulunamadı. Lütfen önce öğretmen ekleyin.")
            return []

        teacher_duty_counts = self.db_manager.get_teacher_duty_counts()
        last_duty_locations = {t['id']: self.db_manager.get_last_duty_location_for_teacher(t['id']) for t in teachers}
        
        # GÜNCELLEME: Çift nöbet kontrolü
        previous_week_start = start_of_week - datetime.timedelta(days=7)
        previous_week_end = start_of_week - datetime.timedelta(days=1)
        duties_last_week = self.db_manager.get_teacher_duty_counts_for_period(previous_week_start, previous_week_end)
        teachers_with_double_duty_last_week = {teacher_id for teacher_id, count in duties_last_week.items() if count > 1}

        existing_duties = {(d['nobet_tarihi'], d['nobet_yeri']): d['ogretmen_id'] for d in self.db_manager.get_duties() if start_of_week <= d['nobet_tarihi'] < start_of_week + datetime.timedelta(days=5)}
        
        assigned_this_run, successful_assignments = [], []
        teachers_assigned_double_this_week = set()

        for i in range(5):
            current_date = start_of_week + datetime.timedelta(days=i)
            day_of_week = week_days[current_date.weekday()]
            
            shuffled_locations = random.sample(self.duty_locations, len(self.duty_locations))
            for location in shuffled_locations:
                if (current_date, location) in existing_duties: continue

                eligible = [t for t in teachers if day_of_week in t.get('available_days', '')]
                if not eligible: continue
                
                # GÜNCELLEME: Sıralama mantığı güncellendi
                # 1. Toplam nöbet sayısı (az olan öncelikli)
                # 2. Bu hafta zaten çift nöbeti var mı (olmayan öncelikli)
                # 3. Geçen hafta çift nöbeti var mıydı (olmayan öncelikli)
                # 4. En son aynı yerde mi nöbet tuttu (tutmayan öncelikli)
                # 5. Rastgelelik
                eligible.sort(key=lambda t: (
                    teacher_duty_counts.get(t['id'], 0),
                    1 if t['id'] in teachers_assigned_double_this_week else 0,
                    1 if t['id'] in teachers_with_double_duty_last_week else 0,
                    1 if last_duty_locations.get(t['id']) == location else 0,
                    random.random()
                ))


                for teacher in eligible:
                    # Bir öğretmene aynı gün içinde ikinci bir nöbet atanmaz.
                    if any(d['nobet_tarihi'] == current_date and d['ogretmen_id'] == teacher['id'] for d in assigned_this_run):
                        continue

                    if self.db_manager.assign_duty(teacher['id'], location, current_date):
                        # Haftada ikinci nöbeti ise işaretle
                        if any(d['ogretmen_id'] == teacher['id'] for d in assigned_this_run):
                            teachers_assigned_double_this_week.add(teacher['id'])

                        assigned_this_run.append({'ogretmen_id': teacher['id'], 'nobet_yeri': location, 'nobet_tarihi': current_date})
                        successful_assignments.append({'Tarih': current_date, 'Gün': day_of_week, 'Nöbet Yeri': location, 'Öğretmen': f"{teacher['ad']} {teacher['soyad']}", 'ogretmen_id': teacher['id']})
                        teacher_duty_counts[teacher['id']] = teacher_duty_counts.get(teacher['id'], 0) + 1
                        last_duty_locations[teacher['id']] = location
                        break
                        
        return successful_assignments

    def display_auto_schedule_results(self, duties_list):
        for item in self.auto_schedule_tree.get_children():
            self.auto_schedule_tree.delete(item)

        if not duties_list:
            self.auto_schedule_tree.insert("", "end", values=("", "", "Nöbet Oluşturulamadı", ""))
            return
            
        # YENİ: Haftalık nöbet sayılarını hesaplayıp renklendirme yapmak için
        teacher_duty_count_this_week = defaultdict(int)

        for duty in duties_list:
            tags = ()
            teacher_duty_count_this_week[duty['ogretmen_id']] += 1
            if teacher_duty_count_this_week[duty['ogretmen_id']] > 1:
                tags = ('double_duty',)

            self.auto_schedule_tree.insert("", "end", values=(
                duty['Tarih'].strftime('%d.%m.%Y'), duty['Gün'], duty['Nöbet Yeri'], duty['Öğretmen']
            ), tags=tags)

if __name__ == "__main__":
    root = tk.Tk()
    app = SchoolDutySchedulerApp(root)
    root.mainloop()