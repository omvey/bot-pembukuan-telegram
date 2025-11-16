#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bot_nota_merged.py

Bot Telegram untuk membuat nota penjualan & belanja:
- Menyimpan nota ke SQLite
- Membuat nota dalam bentuk gambar (PNG)
- Menampilkan history, statistik, dan laporan
- UI Telegram dengan tombol inline
- Kompatibel untuk deploy di Railway

Pastikan environment:
    BOT_TOKEN = "TOKEN_KAMU"
"""

import os
import json
import random
import logging
import sqlite3
from io import BytesIO
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from PIL import Image, ImageDraw, ImageFont

# ========================
# KONFIGURASI
# ========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_FILE = "keuangan_merged.db"
NOTA_IMAGE_DIR = "nota_images"
os.makedirs(NOTA_IMAGE_DIR, exist_ok=True)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ========================
# DATABASE
# ========================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Tabel penjualan
    c.execute("""
        CREATE TABLE IF NOT EXISTS nota_penjualan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            nomor_nota TEXT UNIQUE,
            nama_pelanggan TEXT,
            tanggal TEXT,
            timestamp TEXT,
            daftar_barang TEXT,
            total INTEGER,
            bayar INTEGER,
            sisa INTEGER
        )
    """)

    # Tabel belanja
    c.execute("""
        CREATE TABLE IF NOT EXISTS nota_belanja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            nomor_nota TEXT UNIQUE,
            nama_supplier TEXT,
            tanggal TEXT,
            timestamp TEXT,
            daftar_barang TEXT,
            total INTEGER
        )
    """)

    conn.commit()
    conn.close()
    log.info("Database OK.")

# ========================
# FUNGSI UTILITAS
# ========================

def rupiah(x):
    try:
        return "Rp {:,}".format(int(x)).replace(",", ".")
    except:
        return str(x)

def buat_nomor(prefix="PNJ"):
    d = datetime.now().strftime("%d%m%y")
    r = random.randint(100, 999)
    return f"{prefix}-{d}-{r}"

def buat_gambar_nota(nota):
    """Buat nota PNG menggunakan Pillow"""
    W = 600
    H = 500 + len(nota["items"]) * 30

    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except:
        font = ImageFont.load_default()

    y = 20
    draw.text((20, y), f"NOTA: {nota['nomor']}", fill="black", font=font)
    y += 30
    draw.text((20, y), f"Tanggal: {nota['tanggal']}", fill="black", font=font)
    y += 40

    draw.text((20, y), "Daftar Barang:", fill="black", font=font)
    y += 30

    for brg in nota["items"]:
        line = f"- {brg['nama']} x {brg['qty']} = {rupiah(brg['subtotal'])}"
        draw.text((30, y), line, fill="black", font=font)
        y += 28

    y += 15
    draw.text((20, y), f"Total: {rupiah(nota['total'])}", fill="black", font=font)
    y += 28
    draw.text((20, y), f"Bayar: {rupiah(nota.get('bayar',0))}", fill="black", font=font)
    y += 28
    draw.text((20, y), f"Sisa: {rupiah(nota.get('sisa',0))}", fill="black", font=font)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

# ========================
# HANDLER BOT
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🧾 Buat Nota Penjualan", callback_data="menu_penjualan")],
        [InlineKeyboardButton("📦 Buat Nota Belanja", callback_data="menu_belanja")],
        [InlineKeyboardButton("📜 History Nota", callback_data="menu_history")],
    ]
    await update.message.reply_text(
        "Selamat datang di *Bot Nota*!\nPilih menu:",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

# ------------------------
# MENU PENJUALAN
# ------------------------

async def menu_penjualan(update, context):
    q = update.callback_query
    await q.answer()

    context.user_data["mode"] = "penjualan"
    context.user_data["items"] = []

    await q.message.reply_text("Masukkan *nama pelanggan*:", parse_mode="Markdown")
    context.user_data["step"] = "nama_pelanggan"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    step = context.user_data.get("step")

    if step == "nama_pelanggan":
        context.user_data["nama_pelanggan"] = update.message.text
        context.user_data["step"] = "tambah_barang"
        await update.message.reply_text("Masukkan barang dalam format:\n`nama_barang, qty, harga`\ncontoh:\nKacang Bawang, 2, 15000",
                                        parse_mode="Markdown")
        return

    if step == "tambah_barang":
        try:
            nama, qty, harga = update.message.text.split(",")
            qty = int(qty)
            harga = int(harga)
        except:
            await update.message.reply_text("Format salah. Ulangi lagi.")
            return

        subtotal = qty * harga
        context.user_data["items"].append({
            "nama": nama.strip(),
            "qty": qty,
            "harga": harga,
            "subtotal": subtotal
        })

        kb = [
            [InlineKeyboardButton("Tambah Barang", callback_data="penj_add")],
            [InlineKeyboardButton("Selesai", callback_data="penj_done")],
        ]
        await update.message.reply_text(
            f"Ditambahkan: {nama} x {qty} = {rupiah(subtotal)}",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    if step == "bayar_penjualan":
        try:
            bayar = int(update.message.text)
        except:
            await update.message.reply_text("Masukkan angka.")
            return

        items = context.user_data["items"]
        total = sum(i["subtotal"] for i in items)
        sisa = bayar - total

        nomor = buat_nomor("PNJ")
        tanggal = datetime.now().strftime("%d-%m-%Y")

        # SIMPAN DB
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            INSERT INTO nota_penjualan (user_id, nomor_nota, nama_pelanggan, tanggal, timestamp, daftar_barang, total, bayar, sisa)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            update.message.from_user.id,
            nomor,
            context.user_data["nama_pelanggan"],
            tanggal,
            datetime.now().isoformat(),
            json.dumps(items, ensure_ascii=False),
            total,
            bayar,
            sisa
        ))
        conn.commit()
        conn.close()

        nota = {
            "nomor": nomor,
            "tanggal": tanggal,
            "items": items,
            "total": total,
            "bayar": bayar,
            "sisa": sisa,
        }

        img = buat_gambar_nota(nota)

        await update.message.reply_photo(
            img,
            caption=f"Nota selesai!\nNomor: *{nomor}*",
            parse_mode="Markdown"
        )

        context.user_data.clear()
        return

# ------------------------
# CALLBACK BUTTON
# ------------------------

async def button(update: Update, context):
    q = update.callback_query
    data = q.data

    # menu utama
    if data == "menu_penjualan":
        await menu_penjualan(update, context)
        return

    if data == "penj_add":
        context.user_data["step"] = "tambah_barang"
        await q.message.reply_text("Masukkan barang (nama, qty, harga):")
        return

    if data == "penj_done":
        items = context.user_data["items"]
        total = sum(i["subtotal"] for i in items)

        context.user_data["step"] = "bayar_penjualan"
        await q.message.reply_text(
            f"Total: {rupiah(total)}\n\nMasukkan nominal bayar:"
        )
        return

    if data == "menu_history":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        rows = c.execute("SELECT nomor_nota, nama_pelanggan, total FROM nota_penjualan ORDER BY id DESC LIMIT 10").fetchall()
        conn.close()

        if not rows:
            await q.message.reply_text("Belum ada history.")
            return

        teks = "📜 *10 Nota Terakhir:*\n\n"
        for r in rows:
            teks += f"{r[0]} — {r[1]} — {rupiah(r[2])}\n"

        await q.message.reply_text(teks, parse_mode="Markdown")
        return

# ========================
# MAIN
# ========================

def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()

