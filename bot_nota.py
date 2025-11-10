#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import datetime
import random
import sqlite3
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageDraw, ImageFont
import asyncio

# ===== SETUP LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== KONFIGURASI =====
# Ambil token dari environment variable
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN environment variable tidak ditemukan!")
    logger.info("💡 Cara setup:")
    logger.info("1. Di Railway: Add Environment Variable BOT_TOKEN")
    logger.info("2. Isi value dengan token dari @BotFather")
    exit(1)

# Database SQLite (gunakan path yang compatible dengan cloud)
DB_FILE = os.path.join(os.path.dirname(__file__), "history_nota.db")

# Daftar barang yang tersedia
DAFTAR_BARANG = [
    {"nama": "Kc Bwg Renceng ", "harga": 16000},
    {"nama": "Kc Bwg Renceng Grosir", "harga": 1050},
    {"nama": "Kc Bwg Renceng Grosir", "harga": 1200},
    {"nama": "Kc Bwg Toples 1/2 Kg", "harga": 35000},
    {"nama": "Kc Bwg Toples 1 Kg", "harga": 60000},
    {"nama": "Kc Bawag Ball 2 Kg", "harga": 100000}
]

# State management untuk setiap user
user_sessions = {}

# ===== FUNGSI DATABASE =====
def init_database():
    """Inisialisasi database SQLite"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nota_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
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
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error inisialisasi database: {str(e)}")
        return False

def simpan_histori_nota(user_id, nomor_nota, nama_pelanggan, tanggal_otomatis, daftar_barang, retur_items, total_setelah_retur, bayar, sisa):
    """Menyimpan histori nota ke database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        daftar_barang_json = json.dumps(daftar_barang, ensure_ascii=False)
        retur_items_json = json.dumps(retur_items, ensure_ascii=False)
        
        total_sebelum_retur = sum(item["jumlah"] for item in daftar_barang)
        total_retur = sum(item["jumlah"] for item in retur_items)
        status = "LUNAS" if sisa >= 0 else "BELUM LUNAS"
        keterangan = f"Sisa {sisa}" if sisa >= 0 else f"Kurang {-sisa}"
        
        cursor.execute('''
            INSERT INTO nota_history 
            (user_id, nomor_nota, nama_pelanggan, tanggal, timestamp, daftar_barang, retur_items, 
             total_sebelum_retur, total_retur, total_setelah_retur, bayar, sisa, status, keterangan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, nomor_nota, nama_pelanggan, tanggal_otomatis, datetime.datetime.now().isoformat(),
            daftar_barang_json, retur_items_json, total_sebelum_retur, total_retur,
            total_setelah_retur, bayar, sisa, status, keterangan
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Nota {nomor_nota} disimpan ke database")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error menyimpan histori: {str(e)}")
        return False

# ===== FUNGSI UTILITY =====
def format_jumlah(angka):
    """Format angka ke format Rupiah"""
    rp = f"{angka:,.0f}".replace(",", ".")
    return f"Rp {rp}"

def buat_nomor_nota():
    """Generate nomor nota unik"""
    sekarang = datetime.datetime.now()
    tanggal = sekarang.strftime("%d")
    bulan = sekarang.strftime("%m")
    nomor_acak = random.randint(1, 999)
    return f"BDP-{tanggal}-{bulan}-{nomor_acak:05d}"

def buat_keyboard_barang(tambah_selesai=False):
    """Buat inline keyboard untuk pilihan barang"""
    keyboard = []
    for i, barang in enumerate(DAFTAR_BARANG, 1):
        keyboard.append([InlineKeyboardButton(
            f"{i}. {barang['nama']} - {format_jumlah(barang['harga'])}", 
            callback_data=f"pilih_barang_{i}"
        )])
    
    if tambah_selesai:
        keyboard.append([InlineKeyboardButton("✅ Selesai Tambah Barang", callback_data="selesai_barang")])
    
    keyboard.append([InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

# ===== HANDLER COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    user_id = update.effective_user.id
    
    # Reset session user
    user_sessions[user_id] = {
        'state': 'idle',
        'data': {}
    }
    
    welcome_text = """
🤖 *BOT NOTA GENERATOR*
*Kacang Bawang Berkah Dua Putri*

*Fitur yang tersedia:*
📝 /buat_nota - Buat nota baru
📊 /histori - Lihat histori nota
ℹ️ /info - Info bot

*Cara penggunaan:*
1. Ketik /buat_nota untuk membuat nota baru
2. Pilih barang dari menu yang tersedia
3. Input jumlah barang
4. Selesaikan pembayaran
5. Nota akan dikirim dalam format gambar
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def buat_nota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /buat_nota"""
    user_id = update.effective_user.id
    
    # Inisialisasi session
    user_sessions[user_id] = {
        'state': 'input_nama',
        'data': {
            'daftar_barang': [],
            'retur_items': [],
            'nomor_nota': buat_nomor_nota(),
            'tanggal': datetime.datetime.now().strftime("%d/%m/%Y")
        }
    }
    
    await update.message.reply_text(
        "📝 *BUAT NOTA BARU*\n\n"
        "Masukkan nama pelanggan:",
        parse_mode='Markdown'
    )

async def histori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /histori"""
    user_id = update.effective_user.id
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT nomor_nota, nama_pelanggan, tanggal, total_setelah_retur, status 
            FROM nota_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            await update.message.reply_text("📭 *Belum ada data histori*")
            return
        
        histori_text = "📊 *HISTORI NOTA TERAKHIR*\n\n"
        for row in rows:
            nomor_nota, nama_pelanggan, tanggal, total, status = row
            status_emoji = "✅" if status == "LUNAS" else "⏳"
            histori_text += f"{status_emoji} *{nomor_nota}*\n"
            histori_text += f"   👤 {nama_pelanggan}\n"
            histori_text += f"   📅 {tanggal}\n"
            histori_text += f"   💰 {format_jumlah(total)}\n\n"
        
        await update.message.reply_text(histori_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /info"""
    info_text = """
ℹ️ *INFORMASI BOT*

*Kacang Bawang Berkah Dua Putri*
📍 Cikupa Werasari Sadananya Ciamis

*Fitur:*
• Buat nota penjualan
• Simpan histori transaksi
• Export nota sebagai gambar
• Management retur barang

*Version:* 1.0
*Host:* Railway
    """
    await update.message.reply_text(info_text, parse_mode='Markdown')

# ===== HANDLER MESSAGE =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk pesan teks"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    logger.info(f"📨 Message from {user_id}: {message_text}")
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'state': 'idle', 'data': {}}
    
    session = user_sessions[user_id]
    state = session['state']
    
    if state == 'input_nama':
        # Simpan nama pelanggan
        session['data']['nama_pelanggan'] = message_text
        session['state'] = 'pilih_barang'
        
        await update.message.reply_text(
            f"👤 *Nama Pelanggan:* {message_text}\n\n"
            "📦 *PILIH BARANG:*\nPilih barang dari menu di bawah:",
            parse_mode='Markdown',
            reply_markup=buat_keyboard_barang()
        )
    
    elif state == 'input_jumlah':
        # Handle input jumlah barang
        try:
            qty = int(message_text)
            if qty <= 0:
                await update.message.reply_text("❌ Jumlah harus lebih dari 0!")
                return
            
            selected_item = session['data']['selected_item']
            harga = DAFTAR_BARANG[selected_item]['harga']
            jumlah = qty * harga
            
            # Tambahkan ke daftar barang
            session['data']['daftar_barang'].append({
                'no': len(session['data']['daftar_barang']) + 1,
                'nama': DAFTAR_BARANG[selected_item]['nama'],
                'harga': harga,
                'qty': qty,
                'jumlah': jumlah
            })
            
            session['state'] = 'pilih_barang'
            
            # Tampilkan ringkasan sementara
            total_sementara = sum(item['jumlah'] for item in session['data']['daftar_barang'])
            
            summary_text = f"✅ *Barang ditambahkan:*\n{DAFTAR_BARANG[selected_item]['nama']}\nQty: {qty} x {format_jumlah(harga)} = {format_jumlah(jumlah)}\n\n"
            summary_text += f"💰 *Total sementara:* {format_jumlah(total_sementara)}\n\n"
            summary_text += "Pilih barang lagi atau klik 'Selesai' untuk melanjutkan:"
            
            await update.message.reply_text(
                summary_text,
                parse_mode='Markdown',
                reply_markup=buat_keyboard_barang(tambah_selesai=True)
            )
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_bayar':
        # Handle input pembayaran
        try:
            bayar = int(message_text.replace(".", "").replace(",", ""))
            total_setelah_retur = session['data']['total_setelah_retur']
            sisa = bayar - total_setelah_retur
            
            # Simpan data pembayaran
            session['data']['bayar'] = bayar
            session['data']['sisa'] = sisa
            
            # Simpan ke database dan buat nota
            success = await buat_dan_kirim_nota(update, context, session['data'])
            
            if success:
                session['state'] = 'idle'
                # Hapus session setelah selesai
                if user_id in user_sessions:
                    del user_sessions[user_id]
            else:
                await update.message.reply_text("❌ Gagal membuat nota!")
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")

# ===== HANDLER CALLBACK QUERY =====
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk inline keyboard callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    logger.info(f"🔄 Callback from {user_id}: {callback_data}")
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'state': 'idle', 'data': {}}
    
    session = user_sessions[user_id]
    
    if callback_data.startswith('pilih_barang_'):
        # User memilih barang
        item_index = int(callback_data.split('_')[2]) - 1
        session['data']['selected_item'] = item_index
        session['state'] = 'input_jumlah'
        
        barang = DAFTAR_BARANG[item_index]
        await query.edit_message_text(
            f"📦 *PILIH BARANG:*\n{barang['nama']} - {format_jumlah(barang['harga'])}\n\n"
            "Masukkan jumlah barang:",
            parse_mode='Markdown'
        )
    
    elif callback_data == 'selesai_barang':
        # Selesai memilih barang
        if not session['data']['daftar_barang']:
            await query.edit_message_text("❌ Minimal harus ada 1 barang!")
            return
        
        session['state'] = 'input_bayar'
        total_barang = sum(item['jumlah'] for item in session['data']['daftar_barang'])
        session['data']['total_setelah_retur'] = total_barang
        
        # Tampilkan ringkasan akhir
        summary_text = "📋 *RINGKASAN NOTA*\n\n"
        for item in session['data']['daftar_barang']:
            summary_text += f"• {item['qty']}x {item['nama']} = {format_jumlah(item['jumlah'])}\n"
        
        summary_text += f"\n💰 *TOTAL: {format_jumlah(total_barang)}*\n\n"
        summary_text += "Masukkan jumlah pembayaran:"
        
        await query.edit_message_text(summary_text, parse_mode='Markdown')
    
    elif callback_data == 'cancel':
        # Batalkan proses
        session['state'] = 'idle'
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text("❌ Proses dibatalkan")

# ===== FUNGSI BUAT NOTA GAMBAR =====
async def buat_dan_kirim_nota(update: Update, context: ContextTypes.DEFAULT_TYPE, data):
    """Buat nota dalam format gambar dan kirim ke user"""
    try:
        # Extract data
        nomor_nota = data['nomor_nota']
        nama_pelanggan = data['nama_pelanggan']
        tanggal_otomatis = data['tanggal']
        daftar_barang = data['daftar_barang']
        total_setelah_retur = data['total_setelah_retur']
        bayar = data['bayar']
        sisa = data['sisa']
        retur_items = data.get('retur_items', [])
        
        # Buat gambar nota sederhana (tanpa font external)
        width, height = 600, 400 + (len(daftar_barang) * 30)
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        
        # Use default font
        try:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        except:
            font_large = None
            font_medium = None
            font_small = None
        
        y = 30
        
        # Header
        draw.text((width//2, y), "KACANG BAWANG BERKAH DUA PUTRI", fill="black", font=font_large, anchor="mm")
        y += 30
        draw.text((width//2, y), "Cikupa Werasari Sadananya Ciamis", fill="black", font=font_medium, anchor="mm")
        y += 40
        
        # Info Nota
        draw.text((50, y), f"Nomor: {nomor_nota}", fill="black", font=font_small)
        y += 20
        draw.text((50, y), f"Pelanggan: {nama_pelanggan}", fill="black", font=font_small)
        y += 20
        draw.text((50, y), f"Tanggal: {tanggal_otomatis}", fill="black", font=font_small)
        y += 30
        
        # Daftar Barang
        draw.text((50, y), "DAFTAR BARANG:", fill="black", font=font_medium)
        y += 30
        
        for barang in daftar_barang:
            item_text = f"{barang['qty']}x {barang['nama']}"
            draw.text((70, y), item_text, fill="black", font=font_small)
            draw.text((width-100, y), format_jumlah(barang['jumlah']), fill="black", font=font_small, anchor="ra")
            y += 25
        
        y += 20
        
        # Total dan Pembayaran
        draw.text((50, y), f"TOTAL: {format_jumlah(total_setelah_retur)}", fill="black", font=font_medium)
        y += 25
        draw.text((50, y), f"BAYAR: {format_jumlah(bayar)}", fill="black", font=font_medium)
        y += 25
        
        if sisa >= 0:
            draw.text((50, y), f"SISA: {format_jumlah(sisa)}", fill="green", font=font_medium)
        else:
            draw.text((50, y), f"KURANG: {format_jumlah(-sisa)}", fill="red", font=font_medium)
        
        y += 40
        draw.text((width//2, y), "TERIMA KASIH", fill="black", font=font_medium, anchor="mm")
        
        # Simpan gambar sementara
        image_path = f"nota_{nomor_nota}.png"
        image.save(image_path)
        
        # Simpan ke database
        simpan_histori_nota(
            update.effective_user.id, nomor_nota, nama_pelanggan, tanggal_otomatis,
            daftar_barang, retur_items, total_setelah_retur, bayar, sisa
        )
        
        # Kirim gambar ke user
        with open(image_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=photo,
                caption=f"✅ *Nota berhasil dibuat!*\nNomor: `{nomor_nota}`\nTotal: {format_jumlah(total_setelah_retur)}",
                parse_mode='Markdown'
            )
        
        # Hapus file sementara
        os.remove(image_path)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error buat nota: {str(e)}")
        return False

# ===== ERROR HANDLER =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk error"""
    logger.error(f"❌ Error occurred: {context.error}")
    
    try:
        # Kirim pesan error ke user
        await context.bot.send_message(
            chat_id=update.effective_chat.id if update else None,
            text="❌ Terjadi error. Silakan coba lagi atau ketik /start untuk memulai ulang."
        )
    except:
        pass

# ===== MAIN FUNCTION =====
def main():
    """Main function untuk menjalankan bot"""
    logger.info("🚀 Starting Telegram Bot...")
    
    # Inisialisasi database
    if not init_database():
        logger.error("❌ Gagal menginisialisasi database")
        return
    
    # Buat application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buat_nota", buat_nota))
    application.add_handler(CommandHandler("histori", histori))
    application.add_handler(CommandHandler("info", info))
    
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Jalankan bot
    logger.info("🤖 Bot sedang berjalan di Railway...")
    
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Bot dihentikan")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()