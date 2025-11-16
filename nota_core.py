import os
import json
import random
import sqlite3
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# =======================
#  DATABASE CONFIG
# =======================
DB_FILE = "history_nota.db"  # Railway akan simpan di direktori kerja

# Barang tersedia
DAFTAR_BARANG = [
    {"nama": "Kc Bwg Renceng", "harga": 16000},
    {"nama": "Kc Bwg Renceng Grosir", "harga": 1050},
    {"nama": "Kc Bwg Renceng Grosir 1200", "harga": 1200},
    {"nama": "Kc Bwg Toples 1/2 Kg", "harga": 35000},
    {"nama": "Kc Bwg Toples 1 Kg", "harga": 60000},
    {"nama": "Kc Bawag Ball 2 Kg", "harga": 100000},
]

# =======================
#  HELPERS
# =======================
def format_rupiah(angka):
    return f"Rp {angka:,.0f}".replace(",", ".")


def buat_nomor_nota():
    now = datetime.now()
    tanggal = now.strftime("%d")
    bulan = now.strftime("%m")
    nomor = random.randint(1, 99999)
    return f"BDP-{tanggal}-{bulan}-{nomor:05d}"


# =======================
#  INIT DATABASE
# =======================
def init_database():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS nota_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor_nota TEXT UNIQUE,
            nama_pelanggan TEXT,
            tanggal TEXT,
            timestamp TEXT,
            daftar_barang TEXT,
            retur_items TEXT,
            total_sebelum_retur INTEGER,
            total_retur INTEGER,
            total_setelah_retur INTEGER,
            bayar INTEGER,
            sisa INTEGER,
            status TEXT,
            keterangan TEXT
        )
        """
    )
    conn.commit()
    conn.close()


# =======================
#  SAVE HISTORY
# =======================
def simpan_histori_nota(nomor_nota, nama, tanggal, daftar_barang, retur_items, total_setelah, bayar, sisa):
    init_database()

    total_sebelum = sum(i["jumlah"] for i in daftar_barang)
    total_retur = sum(i["jumlah"] for i in retur_items)

    status = "LUNAS" if sisa >= 0 else "BELUM LUNAS"
    ket = f"Sisa {format_rupiah(sisa)}" if sisa >= 0 else f"Kurang {format_rupiah(-sisa)}"

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO nota_history (
            nomor_nota, nama_pelanggan, tanggal, timestamp,
            daftar_barang, retur_items,
            total_sebelum_retur, total_retur, total_setelah_retur,
            bayar, sisa, status, keterangan
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            nomor_nota, nama, tanggal, datetime.now().isoformat(),
            json.dumps(daftar_barang, ensure_ascii=False),
            json.dumps(retur_items, ensure_ascii=False),
            total_sebelum, total_retur, total_setelah,
            bayar, sisa, status, ket,
        ),
    )
    conn.commit()
    conn.close()


# =======================
#  READ HISTORY
# =======================

def baca_histori_nota(limit=None):
    if not os.path.exists(DB_FILE):
        return []

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    query = "SELECT * FROM nota_history ORDER BY timestamp DESC"
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    rows = cur.fetchall()
    conn.close()

    hasil = []
    for row in rows:
        hasil.append(
            {
                "id": row[0],
                "nomor_nota": row[1],
                "nama_pelanggan": row[2],
                "tanggal": row[3],
                "timestamp": row[4],
                "daftar_barang": json.loads(row[5]),
                "retur_items": json.loads(row[6]),
                "total_sebelum_retur": row[7],
                "total_retur": row[8],
                "total_setelah_retur": row[9],
                "bayar": row[10],
                "sisa": row[11],
                "status": row[12],
                "keterangan": row[13],
            }
        )

    return hasil


# =======================
#  SAVE PNG RECEIPT
# =======================

def simpan_sebagai_gambar(nomor_nota, nama_pelanggan, tanggal, daftar_barang, retur_items, total_akhir, bayar, sisa):
    # Lokasi file (Railway: direktori kerja)
    filename = f"nota_{nomor_nota}.png"

    width = 600
    height = 400 + (len(daftar_barang) * 40) + (len(retur_items) * 40)

    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 20)
    except:
        font = ImageFont.load_default()

    y = 20
    d.text((20, y), f"Nota {nomor_nota}", font=font, fill="black")
    y += 40
    d.text((20, y), f"Pelanggan: {nama_pelanggan}", font=font, fill="black")
    y += 30
    d.text((20, y), f"Tanggal: {tanggal}", font=font, fill="black")
    y += 40

    d.text((20, y), "Barang:", font=font, fill="black")
    y += 30

    for b in daftar_barang:
        d.text(
            (20, y),
            f"{b['nama']} x{b['qty']} = {format_rupiah(b['jumlah'])}",
            font=font,
            fill="black",
        )
        y += 30

    if retur_items:
        y += 20
        d.text((20, y), "Retur:", font=font, fill="red")
        y += 30

        for r in retur_items:
            d.text(
                (20, y),
                f"RETUR {r['nama']} x{r['qty']} = -{format_rupiah(r['jumlah'])}",
                font=font,
                fill="red",
            )
            y += 30

    y += 20
    d.text((20, y), f"Total: {format_rupiah(total_akhir)}", font=font, fill="green")
    y += 30
    d.text((20, y), f"Bayar: {format_rupiah(bayar)}", font=font, fill="black")
    y += 30

    if sisa >= 0:
        d.text((20, y), f"Sisa: {format_rupiah(sisa)}", font=font, fill="blue")
    else:
        d.text((20, y), f"Kurang: {format_rupiah(-sisa)}", font=font, fill="red")

    img.save(filename)
    return filename