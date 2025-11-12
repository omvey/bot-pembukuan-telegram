🤖 Bot Manajemen Keuangan - Kacang Bawang Berkah Dua Putri

Bot Telegram untuk manajemen keuangan dan pencatatan transaksi penjualan & belanja usaha Kacang Bawang Berkah Dua Putri.

✨ Fitur

📝 Nota Penjualan

· Buat nota penjualan dengan sistem harga otomatis
· Pilihan pelanggan: UJANG, ASEP R, Pelanggan Umum
· Harga otomatis untuk Kacang Bawang Renceng Grosir:
  · ASEP R: Rp 1.050
  · UJANG: Rp 1.200
  · Pelanggan Umum: Rp 1.600
· Pilihan pembayaran dengan nominal cepat
· Format nota yang rapi dan profesional

🛍️ Nota Belanja

· Pencatatan pengeluaran usaha
· Kategori belanja: Kacang Kupas, Bumbu, Minyak, Plastik, Label, Biaya Produksi, Gas LPG, Upah goreng, Upah Bungkus, Lain-lain
· Input supplier manual

📊 Histori & Statistik

· Histori transaksi berdasarkan pelanggan
· Statistik penjualan dan belanja bulanan
· Perhitungan laba/rugi otomatis
· Filter histori per pelanggan

🚀 Instalasi

Prerequisites

· Python 3.8+
· Telegram Bot Token dari @BotFather

1. Clone Repository

```bash
git clone https://github.com/username/bot-keuangan-kacang-bawang.git
cd bot-keuangan-kacang-bawang
```

2. Install Dependencies

```bash
pip install python-telegram-bot
```

3. Setup Environment Variables

Buat file .env atau set environment variable:

```bash
export BOT_TOKEN="your_telegram_bot_token_here"
```

4. Run Bot

```bash
python bot_keuangan.py
```

🛠️ Deployment

Railway (Recommended)

1. Fork repository ini
2. Buat project baru di Railway
3. Connect dengan GitHub repository
4. Add environment variable BOT_TOKEN
5. Deploy otomatis

Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Run bot
python bot_keuangan.py
```

📋 Cara Penggunaan

Menu Utama

Bot memiliki menu utama dengan 5 pilihan:

1. 📝 JUAL - Buat nota penjualan
2. 🛍️ BELI - Buat nota belanja
3. 📊 HISTORI - Lihat histori transaksi
4. 📈 STATISTIK - Statistik keuangan
5. ℹ️ INFO - Informasi bot

Proses Penjualan

1. Pilih 📝 JUAL
2. Pilih pelanggan dari daftar
3. Pilih barang yang dijual
4. Input jumlah barang
5. Pilih metode pembayaran
6. Nota otomatis dikirim

Proses Belanja

1. Pilih 🛍️ BELI
2. Input nama supplier
3. Pilih kategori belanja
4. Input harga dan jumlah
5. Input total belanja
6. Nota belanja dikirim

🗃️ Database

Bot menggunakan SQLite database dengan 2 tabel utama:

nota_penjualan

· ID transaksi
· Nomor nota unik
· Nama pelanggan
· Tanggal transaksi
· Daftar barang (JSON)
· Total penjualan
· Status pembayaran

nota_belanja

· ID transaksi
· Nomor nota unik
· Nama supplier
· Tanggal transaksi
· Daftar barang (JSON)
· Total belanja

🎯 Contoh Penggunaan

Nota Penjualan

```
🛒 NOTA PENJUALAN
Kacang Bawang Berkah Dua Putri

📋 No: PNJ-250124-001
👤 Pelanggan: ASEP R
📅 Tanggal: 25/01/2024

📦 DAFTAR BARANG:
 1. Kacang Bawang Renceng Grosir
     100x @        Rp 1.050 =        Rp 105.000

💰 RINGKASAN PEMBAYARAN:
Total Barang    :        Rp 105.000
Total Bersih    :        Rp 105.000
Bayar           :        Rp 110.000
                -------------------->
Sisa            :          Rp 5.000

✅ Status: LUNAS
```

Statistik

```
📈 STATISTIK BULAN INI (01/2024)

🛒 PENJUALAN:
• Jumlah transaksi: 15
• Total penjualan: Rp 2.500.000

🛍️ BELANJA:
• Jumlah transaksi: 8
• Total belanja: Rp 1.800.000

💰 LABA/RUGI:
• Rp 700.000 (✅ LABA)
```

🔧 Konfigurasi

Daftar Pelanggan

Edit variabel DAFTAR_PELANGGAN dalam kode:

```python
DAFTAR_PELANGGAN = [
    "UJANG", "ASEP R", "Pelanggan Umum"
]
```

Daftar Barang

Edit variabel DAFTAR_BARANG_PENJUALAN dan DAFTAR_BARANG_BELANJA sesuai kebutuhan.

Harga Otomatis

Edit fungsi get_harga_renceng_grosir() untuk menyesuaikan harga per pelanggan.

🐛 Troubleshooting

Bot tidak merespons

· Pastikan BOT_TOKEN sudah benar
· Cek koneksi internet
· Restart bot

Database error

· Hapus file keuangan.db untuk reset database
· Pastikan folder writable

Pesan tidak terbaca

· Gunakan command /start untuk memulai ulang
· Pastikan menggunakan keyboard inline yang disediakan

📞 Support

Jika mengalami masalah:

1. Cek troubleshooting di atas
2. Pastikan semua step instalasi sudah benar
3. Buat issue di GitHub repository

📄 License

MIT License - bebas digunakan dan dimodifikasi untuk keperluan komersial maupun non-komersial.

👥 Kontribusi

Pull request dipersilakan! Untuk perubahan besar, buka issue terlebih dahulu untuk didiskusikan.

---

Dibuat dengan ❤️ untuk Usaha Kacang Bawang Berkah Dua Putri
