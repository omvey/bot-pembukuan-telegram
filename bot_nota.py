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

# ===== SETUP LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== KONFIGURASI =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN environment variable tidak ditemukan!")
    exit(1)

# Database SQLite
DB_FILE = os.path.join(os.path.dirname(__file__), "keuangan.db")

# State management untuk setiap user
user_sessions = {}

# ===== FUNGSI DATABASE =====
def init_database():
    """Inisialisasi database SQLite"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Tabel untuk nota penjualan
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nota_penjualan (
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
        
        # Tabel untuk nota belanja
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nota_belanja (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                nomor_nota TEXT UNIQUE,
                nama_supplier TEXT,
                tanggal TEXT,
                timestamp TEXT,
                daftar_barang TEXT,
                total_belanja INTEGER,
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

def simpan_nota_penjualan(user_id, nomor_nota, nama_pelanggan, tanggal, daftar_barang, retur_items, total_setelah_retur, bayar, sisa):
    """Menyimpan nota penjualan ke database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        daftar_barang_json = json.dumps(daftar_barang, ensure_ascii=False)
        retur_items_json = json.dumps(retur_items, ensure_ascii=False)
        
        total_sebelum_retur = sum(item["subtotal"] for item in daftar_barang)
        total_retur = sum(item["subtotal"] for item in retur_items)
        status = "LUNAS" if sisa >= 0 else "BELUM LUNAS"
        keterangan = f"Sisa {sisa}" if sisa >= 0 else f"Kurang {-sisa}"
        
        cursor.execute('''
            INSERT INTO nota_penjualan 
            (user_id, nomor_nota, nama_pelanggan, tanggal, timestamp, daftar_barang, retur_items, 
             total_sebelum_retur, total_retur, total_setelah_retur, bayar, sisa, status, keterangan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, nomor_nota, nama_pelanggan, tanggal, datetime.datetime.now().isoformat(),
            daftar_barang_json, retur_items_json, total_sebelum_retur, total_retur,
            total_setelah_retur, bayar, sisa, status, keterangan
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Nota penjualan {nomor_nota} disimpan ke database")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error menyimpan nota penjualan: {str(e)}")
        return False

def simpan_nota_belanja(user_id, nomor_nota, nama_supplier, tanggal, daftar_barang, total_belanja, keterangan):
    """Menyimpan nota belanja ke database"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        daftar_barang_json = json.dumps(daftar_barang, ensure_ascii=False)
        
        cursor.execute('''
            INSERT INTO nota_belanja 
            (user_id, nomor_nota, nama_supplier, tanggal, timestamp, daftar_barang, total_belanja, keterangan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, nomor_nota, nama_supplier, tanggal, datetime.datetime.now().isoformat(),
            daftar_barang_json, total_belanja, keterangan
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Nota belanja {nomor_nota} disimpan ke database")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error menyimpan nota belanja: {str(e)}")
        return False

# ===== FUNGSI UTILITY =====
def format_rupiah(angka):
    """Format angka ke format Rupiah"""
    return f"Rp {angka:,.0f}".replace(",", ".")

def buat_nomor_nota(prefix="PNJ"):
    """Generate nomor nota unik"""
    sekarang = datetime.datetime.now()
    tanggal = sekarang.strftime("%d")
    bulan = sekarang.strftime("%m")
    tahun = sekarang.strftime("%y")
    nomor_acak = random.randint(1, 999)
    return f"{prefix}-{tanggal}{bulan}{tahun}-{nomor_acak:03d}"

def buat_keyboard_opsi(tambah_selesai=False, dengan_retur=False):
    """Buat inline keyboard untuk opsi"""
    keyboard = []
    
    if tambah_selesai:
        keyboard.append([InlineKeyboardButton("✅ Selesai Tambah Barang", callback_data="selesai_barang")])
    
    if dengan_retur:
        keyboard.append([InlineKeyboardButton("🔄 Retur Barang", callback_data="retur_barang")])
    
    keyboard.append([InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def format_nota_penjualan(data):
    """Format nota penjualan menjadi teks dengan format kolom yang rapi"""
    
    # Header nota
    nota_text = f"*            NOTA PENJUALAN            *\n"
    nota_text += f"*            Berkah Dua Putri            *\n"
    
    # Informasi dasar nota
    nota_text += "─" * 27 + "\n"
    nota_text += f"📋 *No: {data['nomor_nota']}*\n"
    nota_text += f"👤 *Pelanggan: {data['nama_pelanggan']}*\n"
    nota_text += f"📅 *Tanggal: {data['tanggal']}*\n"
    nota_text += "─" * 27 + "\n\n"
    
    # Header tabel barang
    nota_text += "📦 *DAFTAR BARANG:*\n"
    nota_text += "┌" + "─" * 25 + "┐\n"
    
    # Daftar barang dengan format kolom
    for i, item in enumerate(data['daftar_barang'], 1):
        nama_barang = item['nama']
        qty = f"{item['qty']}x"
        harga_satuan = format_rupiah(item['harga'])
        subtotal = format_rupiah(item['subtotal'])
        
        # Format baris barang
        baris_nama = f"│ {i:2d}. {nama_barang:<20} │\n"
        baris_detail = f"│     {qty:>4} @ {harga_satuan:>12} = {subtotal:>12} │\n"
        
        nota_text += baris_nama
        nota_text += baris_detail
    
    nota_text += "└" + "─" * 25 + "┘\n"
    
    # Barang retur (jika ada)
    if data['retur_items']:
        nota_text += "\n🔄 *BARANG RETUR:*\n"
        nota_text += "┌" + "─" * 25 + "┐\n"
        
        for i, item in enumerate(data['retur_items'], 1):
            nama_barang = item['nama']
            qty = f"{item['qty']}x"
            harga_satuan = format_rupiah(item['harga'])
            subtotal = format_rupiah(item['subtotal'])
            
            # Format baris retur
            baris_nama = f"│ {i:2d}. {nama_barang:<20} │\n"
            baris_detail = f"│     {qty:>4} @ {harga_satuan:>12} = {subtotal:>12} │\n"
            
            nota_text += baris_nama
            nota_text += baris_detail
        
        nota_text += "└" + "─" * 25 + "┘\n"
    
    # Ringkasan pembayaran
    nota_text += "\n" + "─" * 27 + "\n"
    nota_text += "💰 *RINGKASAN PEMBAYARAN:*\n"
    
    # Hitung total
    total_barang = sum(item['subtotal'] for item in data['daftar_barang'])
    total_retur = sum(item['subtotal'] for item in data['retur_items'])
    total_setelah_retur = total_barang - total_retur
    
    # Format ringkasan dengan alignment
    nota_text += f"Total Barang    : {format_rupiah(total_barang):>15}\n"
    
    if data['retur_items']:
        nota_text += f"Total Retur     : {format_rupiah(total_retur):>15}\n"
        nota_text += f"                {'':->20}>\n"
    
    nota_text += f"*Total Bersih*  : *{format_rupiah(total_setelah_retur):>15}*\n"
    nota_text += f"Bayar           : {format_rupiah(data['bayar']):>15}\n"
    nota_text += f"                {'':->20}>\n"
    
    if data['sisa'] >= 0:
        nota_text += f"*Sisa*          : *{format_rupiah(data['sisa']):>15}*\n"
        status_emoji = "✅"
    else:
        nota_text += f"*Kurang*        : *{format_rupiah(-data['sisa']):>15}*\n"
        status_emoji = "❌"
    
    nota_text += f"\n{status_emoji} *Status: {data['status']}*"
    nota_text += "\n\n_*Terima kasih atas kepercayaannya*_ 🙏"
    
    return nota_text
    
def format_nota_belanja(data):
    """Format nota belanja menjadi teks"""
    nota_text = f"""
🛍️ *NOTA BELANJA*

📋 *No: {data['nomor_nota']}*
🏢 *Supplier: {data['nama_supplier']}*
📅 *Tanggal: {data['tanggal']}*

📦 *DAFTAR BARANG:*
"""
    
    for item in data['daftar_barang']:
        nota_text += f"• {item['nama']}\n"
        nota_text += f"  {item['qty']} x {format_rupiah(item['harga'])} = {format_rupiah(item['subtotal'])}\n"
    
    nota_text += f"\n💰 *TOTAL BELANJA: {format_rupiah(data['total_belanja'])}*"
    
    if data['keterangan']:
        nota_text += f"\n📝 *Keterangan: {data['keterangan']}*"
    
    return nota_text

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
🤖 *BOT MANAJEMEN KEUANGAN*
*Kacang Bawang Berkah Dua Putri*

*Fitur yang tersedia:*
📝 /jual - Buat nota penjualan
🛍️ /beli - Buat nota belanja
📊 /histori - Lihat histori nota
📈 /statistik - Statistik penjualan & belanja
ℹ️ /info - Info bot

*Cara penggunaan:*
1. Untuk penjualan: /jual
2. Untuk pembelian: /beli
3. Input data sesuai permintaan bot
4. Nota akan dikirim dalam format teks
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def buat_nota_penjualan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /jual"""
    user_id = update.effective_user.id
    
    # Inisialisasi session
    user_sessions[user_id] = {
        'state': 'input_nama_pelanggan',
        'type': 'penjualan',
        'data': {
            'daftar_barang': [],
            'retur_items': [],
            'nomor_nota': buat_nomor_nota("PNJ"),
            'tanggal': datetime.datetime.now().strftime("%d/%m/%Y")
        }
    }
    
    await update.message.reply_text(
        "📝 *BUAT NOTA PENJUALAN*\n\n"
        "Masukkan nama pelanggan:",
        parse_mode='Markdown'
    )

async def buat_nota_belanja(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /beli"""
    user_id = update.effective_user.id
    
    # Inisialisasi session
    user_sessions[user_id] = {
        'state': 'input_nama_supplier',
        'type': 'belanja',
        'data': {
            'daftar_barang': [],
            'nomor_nota': buat_nomor_nota("BLJ"),
            'tanggal': datetime.datetime.now().strftime("%d/%m/%Y")
        }
    }
    
    await update.message.reply_text(
        "🛍️ *BUAT NOTA BELANJA*\n\n"
        "Masukkan nama supplier:",
        parse_mode='Markdown'
    )

async def histori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /histori"""
    user_id = update.effective_user.id
    
    try:
        # Buat keyboard untuk pilihan histori
        keyboard = [
            [InlineKeyboardButton("📝 Penjualan", callback_data="histori_penjualan")],
            [InlineKeyboardButton("🛍️ Belanja", callback_data="histori_belanja")],
            [InlineKeyboardButton("🚫 Tutup", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "📊 *PILIH JENIS HISTORI:*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def statistik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /statistik"""
    user_id = update.effective_user.id
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Statistik penjualan bulan ini
        bulan_ini = datetime.datetime.now().strftime("%m/%Y")
        cursor.execute('''
            SELECT COUNT(*), SUM(total_setelah_retur) 
            FROM nota_penjualan 
            WHERE user_id = ? AND tanggal LIKE ?
        ''', (user_id, f'%/{bulan_ini}'))
        
        penjualan = cursor.fetchone()
        total_penjualan = penjualan[1] if penjualan[1] else 0
        
        # Statistik belanja bulan ini
        cursor.execute('''
            SELECT COUNT(*), SUM(total_belanja) 
            FROM nota_belanja 
            WHERE user_id = ? AND tanggal LIKE ?
        ''', (user_id, f'%/{bulan_ini}'))
        
        belanja = cursor.fetchone()
        total_belanja = belanja[1] if belanja[1] else 0
        
        conn.close()
        
        # Hitung laba/rugi
        laba_rugi = total_penjualan - total_belanja
        
        statistik_text = f"""
📈 *STATISTIK BULAN INI* ({bulan_ini})

🛒 *PENJUALAN:*
• Jumlah transaksi: {penjualan[0]}
• Total penjualan: {format_rupiah(total_penjualan)}

🛍️ *BELANJA:*
• Jumlah transaksi: {belanja[0]}
• Total belanja: {format_rupiah(total_belanja)}

💰 *LABA/RUGI:*
• {format_rupiah(laba_rugi)} ({'✅ LABA' if laba_rugi >= 0 else '❌ RUGI'})
"""
        
        await update.message.reply_text(statistik_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /info"""
    info_text = """
ℹ️ *INFORMASI BOT*

*Kacang Bawang Berkah Dua Putri*
📍 Cikupa Werasari Sadananya Ciamis

*Fitur:*
• Buat nota penjualan dengan retur
• Buat nota belanja 
• Simpan histori transaksi
• Statistik penjualan & belanja

*Version:* 2.0
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
    session_type = session.get('type', '')
    
    if state == 'input_nama_pelanggan':
        # Simpan nama pelanggan
        session['data']['nama_pelanggan'] = message_text
        session['state'] = 'input_barang_nama'
        
        await update.message.reply_text(
            f"👤 *Nama Pelanggan:* {message_text}\n\n"
            "📦 *TAMBAH BARANG*\nMasukkan nama barang:",
            parse_mode='Markdown'
        )
    
    elif state == 'input_nama_supplier':
        # Simpan nama supplier
        session['data']['nama_supplier'] = message_text
        session['state'] = 'input_barang_nama_belanja'
        
        await update.message.reply_text(
            f"🏢 *Nama Supplier:* {message_text}\n\n"
            "📦 *TAMBAH BARANG*\nMasukkan nama barang:",
            parse_mode='Markdown'
        )
    
    elif state == 'input_barang_nama':
        # Simpan nama barang penjualan
        session['data']['current_item'] = {'nama': message_text}
        session['state'] = 'input_barang_harga'
        
        await update.message.reply_text(
            f"📦 *Nama Barang:* {message_text}\n\n"
            "Masukkan harga satuan:",
            parse_mode='Markdown'
        )
    
    elif state == 'input_barang_harga':
        # Simpan harga barang
        try:
            harga = int(message_text.replace(".", "").replace(",", ""))
            session['data']['current_item']['harga'] = harga
            session['state'] = 'input_barang_qty'
            
            await update.message.reply_text(
                f"💰 *Harga:* {format_rupiah(harga)}\n\n"
                "Masukkan jumlah barang:",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_barang_qty':
        # Simpan quantity barang
        try:
            qty = int(message_text)
            if qty <= 0:
                await update.message.reply_text("❌ Jumlah harus lebih dari 0!")
                return
            
            current_item = session['data']['current_item']
            current_item['qty'] = qty
            current_item['subtotal'] = current_item['harga'] * qty
            
            # Tambahkan ke daftar barang
            session['data']['daftar_barang'].append(current_item)
            
            # Reset current item
            session['data']['current_item'] = {}
            session['state'] = 'pilih_tambah_barang'
            
            # Tampilkan ringkasan sementara
            total_sementara = sum(item['subtotal'] for item in session['data']['daftar_barang'])
            
            summary_text = f"✅ *Barang ditambahkan:*\n{current_item['nama']}\nQty: {qty} x {format_rupiah(current_item['harga'])} = {format_rupiah(current_item['subtotal'])}\n\n"
            summary_text += f"💰 *Total sementara:* {format_rupiah(total_sementara)}\n\n"
            summary_text += "Pilih opsi di bawah:"
            
            await update.message.reply_text(
                summary_text,
                parse_mode='Markdown',
                reply_markup=buat_keyboard_opsi(tambah_selesai=True, dengan_retur=(session_type == 'penjualan'))
            )
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_barang_nama_belanja':
        # Simpan nama barang belanja
        session['data']['current_item'] = {'nama': message_text}
        session['state'] = 'input_barang_harga_belanja'
        
        await update.message.reply_text(
            f"📦 *Nama Barang:* {message_text}\n\n"
            "Masukkan harga satuan:",
            parse_mode='Markdown'
        )
    
    elif state == 'input_barang_harga_belanja':
        # Simpan harga barang belanja
        try:
            harga = int(message_text.replace(".", "").replace(",", ""))
            session['data']['current_item']['harga'] = harga
            session['state'] = 'input_barang_qty_belanja'
            
            await update.message.reply_text(
                f"💰 *Harga:* {format_rupiah(harga)}\n\n"
                "Masukkan jumlah barang:",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_barang_qty_belanja':
        # Simpan quantity barang belanja
        try:
            qty = int(message_text)
            if qty <= 0:
                await update.message.reply_text("❌ Jumlah harus lebih dari 0!")
                return
            
            current_item = session['data']['current_item']
            current_item['qty'] = qty
            current_item['subtotal'] = current_item['harga'] * qty
            
            # Tambahkan ke daftar barang
            session['data']['daftar_barang'].append(current_item)
            
            # Reset current item
            session['data']['current_item'] = {}
            session['state'] = 'pilih_tambah_barang_belanja'
            
            # Tampilkan ringkasan sementara
            total_sementara = sum(item['subtotal'] for item in session['data']['daftar_barang'])
            
            summary_text = f"✅ *Barang ditambahkan:*\n{current_item['nama']}\nQty: {qty} x {format_rupiah(current_item['harga'])} = {format_rupiah(current_item['subtotal'])}\n\n"
            summary_text += f"💰 *Total sementara:* {format_rupiah(total_sementara)}\n\n"
            summary_text += "Pilih opsi di bawah:"
            
            await update.message.reply_text(
                summary_text,
                parse_mode='Markdown',
                reply_markup=buat_keyboard_opsi(tambah_selesai=True)
            )
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_retur_nama':
        # Simpan nama barang retur
        session['data']['current_retur'] = {'nama': message_text}
        session['state'] = 'input_retur_harga'
        
        await update.message.reply_text(
            f"🔄 *Nama Barang Retur:* {message_text}\n\n"
            "Masukkan harga satuan:",
            parse_mode='Markdown'
        )
    
    elif state == 'input_retur_harga':
        # Simpan harga barang retur
        try:
            harga = int(message_text.replace(".", "").replace(",", ""))
            session['data']['current_retur']['harga'] = harga
            session['state'] = 'input_retur_qty'
            
            await update.message.reply_text(
                f"💰 *Harga:* {format_rupiah(harga)}\n\n"
                "Masukkan jumlah barang retur:",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_retur_qty':
        # Simpan quantity barang retur
        try:
            qty = int(message_text)
            if qty <= 0:
                await update.message.reply_text("❌ Jumlah harus lebih dari 0!")
                return
            
            current_retur = session['data']['current_retur']
            current_retur['qty'] = qty
            current_retur['subtotal'] = current_retur['harga'] * qty
            
            # Tambahkan ke daftar retur
            session['data']['retur_items'].append(current_retur)
            
            # Reset current retur
            session['data']['current_retur'] = {}
            session['state'] = 'pilih_tambah_retur'
            
            # Tampilkan ringkasan retur
            total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
            
            summary_text = f"🔄 *Barang retur ditambahkan:*\n{current_retur['nama']}\nQty: {qty} x {format_rupiah(current_retur['harga'])} = {format_rupiah(current_retur['subtotal'])}\n\n"
            summary_text += f"💰 *Total retur:* {format_rupiah(total_retur)}\n\n"
            summary_text += "Pilih opsi di bawah:"
            
            await update.message.reply_text(
                summary_text,
                parse_mode='Markdown',
                reply_markup=buat_keyboard_opsi(tambah_selesai=True)
            )
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_bayar':
        # Handle input pembayaran
        try:
            bayar = int(message_text.replace(".", "").replace(",", ""))
            total_barang = sum(item['subtotal'] for item in session['data']['daftar_barang'])
            total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
            total_setelah_retur = total_barang - total_retur
            sisa = bayar - total_setelah_retur
            
            # Simpan data pembayaran
            session['data']['bayar'] = bayar
            session['data']['sisa'] = sisa
            session['data']['total_setelah_retur'] = total_setelah_retur
            session['data']['status'] = "LUNAS" if sisa >= 0 else "BELUM LUNAS"
            
            # Simpan ke database dan kirim nota
            success = simpan_nota_penjualan(
                user_id, 
                session['data']['nomor_nota'],
                session['data']['nama_pelanggan'],
                session['data']['tanggal'],
                session['data']['daftar_barang'],
                session['data']['retur_items'],
                total_setelah_retur,
                bayar,
                sisa
            )
            
            if success:
                # Kirim nota
                nota_text = format_nota_penjualan(session['data'])
                await update.message.reply_text(nota_text, parse_mode='Markdown')
                
                session['state'] = 'idle'
                # Hapus session setelah selesai
                if user_id in user_sessions:
                    del user_sessions[user_id]
            else:
                await update.message.reply_text("❌ Gagal menyimpan nota!")
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_total_belanja':
        # Handle input total belanja dan keterangan
        try:
            total_belanja = int(message_text.replace(".", "").replace(",", ""))
            
            # Simpan data belanja
            session['data']['total_belanja'] = total_belanja
            session['state'] = 'input_keterangan_belanja'
            
            await update.message.reply_text(
                f"💰 *Total Belanja:* {format_rupiah(total_belanja)}\n\n"
                "Masukkan keterangan (opsional):",
                parse_mode='Markdown'
            )
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_keterangan_belanja':
        # Handle input keterangan belanja
        keterangan = message_text if message_text else "-"
        
        # Simpan ke database dan kirim nota
        success = simpan_nota_belanja(
            user_id, 
            session['data']['nomor_nota'],
            session['data']['nama_supplier'],
            session['data']['tanggal'],
            session['data']['daftar_barang'],
            session['data']['total_belanja'],
            keterangan
        )
        
        if success:
            # Kirim nota
            session['data']['keterangan'] = keterangan
            nota_text = format_nota_belanja(session['data'])
            await update.message.reply_text(nota_text, parse_mode='Markdown')
            
            session['state'] = 'idle'
            # Hapus session setelah selesai
            if user_id in user_sessions:
                del user_sessions[user_id]
        else:
            await update.message.reply_text("❌ Gagal menyimpan nota!")

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
    session_type = session.get('type', '')
    
    if callback_data == 'tambah_barang':
        # Tambah barang baru
        if session_type == 'penjualan':
            session['state'] = 'input_barang_nama'
            await query.edit_message_text(
                "📦 *TAMBAH BARANG*\nMasukkan nama barang:",
                parse_mode='Markdown'
            )
        else:  # belanja
            session['state'] = 'input_barang_nama_belanja'
            await query.edit_message_text(
                "📦 *TAMBAH BARANG*\nMasukkan nama barang:",
                parse_mode='Markdown'
            )
    
    elif callback_data == 'selesai_barang':
        # Selesai memilih barang
        if not session['data']['daftar_barang']:
            await query.edit_message_text("❌ Minimal harus ada 1 barang!")
            return
        
        if session_type == 'penjualan':
            session['state'] = 'input_bayar'
            total_barang = sum(item['subtotal'] for item in session['data']['daftar_barang'])
            total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
            total_setelah_retur = total_barang - total_retur
            
            # Tampilkan ringkasan akhir
            summary_text = "📋 *RINGKASAN NOTA PENJUALAN*\n\n"
            for item in session['data']['daftar_barang']:
                summary_text += f"• {item['qty']}x {item['nama']} = {format_rupiah(item['subtotal'])}\n"
            
            if session['data']['retur_items']:
                summary_text += "\n🔄 *BARANG RETUR:*\n"
                for item in session['data']['retur_items']:
                    summary_text += f"• {item['qty']}x {item['nama']} = {format_rupiah(item['subtotal'])}\n"
            
            summary_text += f"\n💰 *TOTAL: {format_rupiah(total_setelah_retur)}*\n\n"
            summary_text += "Masukkan jumlah pembayaran:"
            
            await query.edit_message_text(summary_text, parse_mode='Markdown')
        else:
            # Untuk belanja, langsung ke input total
            session['state'] = 'input_total_belanja'
            total_belanja = sum(item['subtotal'] for item in session['data']['daftar_barang'])
            
            summary_text = "📋 *RINGKASAN NOTA BELANJA*\n\n"
            for item in session['data']['daftar_barang']:
                summary_text += f"• {item['qty']}x {item['nama']} = {format_rupiah(item['subtotal'])}\n"
            
            summary_text += f"\n💰 *TOTAL: {format_rupiah(total_belanja)}*\n\n"
            summary_text += "Masukkan total belanja (bisa disesuaikan):"
            
            await query.edit_message_text(summary_text, parse_mode='Markdown')
    
    elif callback_data == 'retur_barang':
        # Mulai proses retur
        session['state'] = 'input_retur_nama'
        await query.edit_message_text(
            "🔄 *TAMBAH BARANG RETUR*\nMasukkan nama barang retur:",
            parse_mode='Markdown'
        )
    
    elif callback_data == 'tambah_retur':
        # Tambah barang retur baru
        session['state'] = 'input_retur_nama'
        await query.edit_message_text(
            "🔄 *TAMBAH BARANG RETUR*\nMasukkan nama barang retur:",
            parse_mode='Markdown'
        )
    
    elif callback_data == 'selesai_retur':
        # Selesai retur, kembali ke menu utama
        session['state'] = 'pilih_tambah_barang'
        
        total_barang = sum(item['subtotal'] for item in session['data']['daftar_barang'])
        total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
        
        summary_text = f"💰 *Total barang:* {format_rupiah(total_barang)}\n"
        summary_text += f"🔄 *Total retur:* {format_rupiah(total_retur)}\n"
        summary_text += f"💰 *Total setelah retur:* {format_rupiah(total_barang - total_retur)}\n\n"
        summary_text += "Pilih opsi di bawah:"
        
        await query.edit_message_text(
            summary_text,
            parse_mode='Markdown',
            reply_markup=buat_keyboard_opsi(tambah_selesai=True, dengan_retur=True)
        )
    
    elif callback_data.startswith('histori_'):
        # Tampilkan histori
        jenis = callback_data.split('_')[1]
        
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            if jenis == 'penjualan':
                cursor.execute('''
                    SELECT nomor_nota, nama_pelanggan, tanggal, total_setelah_retur, status 
                    FROM nota_penjualan 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                ''', (user_id,))
                judul = "PENJUALAN"
            else:
                cursor.execute('''
                    SELECT nomor_nota, nama_supplier, tanggal, total_belanja, keterangan 
                    FROM nota_belanja 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                ''', (user_id,))
                judul = "BELANJA"
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                await query.edit_message_text(f"📭 *Belum ada data histori {judul}*", parse_mode='Markdown')
                return
            
            histori_text = f"📊 *HISTORI {judul} TERAKHIR*\n\n"
            for row in rows:
                if jenis == 'penjualan':
                    nomor_nota, nama, tanggal, total, status = row
                    status_emoji = "✅" if status == "LUNAS" else "⏳"
                    histori_text += f"{status_emoji} *{nomor_nota}*\n"
                    histori_text += f"   👤 {nama}\n"
                else:
                    nomor_nota, nama, tanggal, total, keterangan = row
                    histori_text += f"🛍️ *{nomor_nota}*\n"
                    histori_text += f"   🏢 {nama}\n"
                
                histori_text += f"   📅 {tanggal}\n"
                histori_text += f"   💰 {format_rupiah(total)}\n\n"
            
            await query.edit_message_text(histori_text, parse_mode='Markdown')
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}")
    
    elif callback_data == 'cancel':
        # Batalkan proses
        session['state'] = 'idle'
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text("❌ Proses dibatalkan")

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
    application.add_handler(CommandHandler("jual", buat_nota_penjualan))
    application.add_handler(CommandHandler("beli", buat_nota_belanja))
    application.add_handler(CommandHandler("histori", histori))
    application.add_handler(CommandHandler("statistik", statistik))
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
