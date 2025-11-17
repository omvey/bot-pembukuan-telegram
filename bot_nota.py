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

# Data pilihan
DAFTAR_PELANGGAN = [
    "ASEP RIDWAN", "UJANG", "Pelanggan Umum"
]

DAFTAR_BARANG_PENJUALAN = [
    "Kc Bawang Renceng",
    "Kc Bawang Kiloan"
]

DAFTAR_BARANG_BELANJA = [
    "Kacang Kupas", "Bumbu", "Minyak", "Plastik", "Label", 
    "Biaya Produksi", "Gas LPG", "Upah goreng", "Upah Bungkus", "Lain-lain"
]

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

def buat_nomor_nota(prefix="BDP"):
    """Generate nomor nota unik"""
    sekarang = datetime.datetime.now()
    tanggal = sekarang.strftime("%d")
    bulan = sekarang.strftime("%m")
    tahun = sekarang.strftime("%y")
    nomor_acak = random.randint(1, 999)
    return f"{prefix}-{tanggal}-{bulan}-{tahun}-{nomor_acak:03d}"

def get_harga_renceng(nama_pelanggan):
    """Tentukan harga Kc Bawang Renceng berdasarkan pelanggan"""
    if "ASEP R" in nama_pelanggan.upper():
        return 1050
    elif "UJANG" in nama_pelanggan.upper():
        return 1200
    else:
        return 1600  # Pelanggan Umum

def header_pesan():
    "*           𝙱𝙾𝚃 𝙼𝙰𝙽𝙰𝙹𝙴𝙼𝙴𝙽 𝙺𝙴𝚄𝙰𝙽𝙶𝙰𝙽        *\n*               𝗕𝗘𝗥𝗞𝗔𝗛 𝗗𝗨𝗔 𝗣𝗨𝗧𝗥𝗜          *\n──────────────────────────\n\n"

def buat_keyboard_menu_utama():
    """Buat keyboard menu utama 2 kolom"""
    keyboard = [
        [
            InlineKeyboardButton("📝 JUAL", callback_data="menu_jual"),
            InlineKeyboardButton("🛍️ BELI", callback_data="menu_beli")
        ],
        [
            InlineKeyboardButton("📊 HISTORI", callback_data="menu_histori"),
            InlineKeyboardButton("📈 STATISTIK", callback_data="menu_statistik")
        ],
        [
            InlineKeyboardButton("ℹ️ INFO", callback_data="menu_info")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def buat_keyboard_pelanggan():
    """Buat keyboard pilihan pelanggan dengan 2 kolom"""
    
    keyboard = []
    
    # Membuat tombol dalam 2 kolom
    for i in range(0, len(DAFTAR_PELANGGAN), 2):
        row = []
        # Tombol pertama di baris
        row.append(InlineKeyboardButton(
            f"{DAFTAR_PELANGGAN[i]}", 
            callback_data=f"pelanggan_{i+1}"
        ))
        
        # Tombol kedua di baris (jika ada)
        if i + 1 < len(DAFTAR_PELANGGAN):
            row.append(InlineKeyboardButton(
                f"{DAFTAR_PELANGGAN[i+1]}", 
                callback_data=f"pelanggan_{i+2}"
            ))
        
        keyboard.append(row)
    
    # Tambahkan tombol cancel di baris terakhir
    keyboard.append([InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")])
    
    return InlineKeyboardMarkup(keyboard)

def buat_keyboard_barang_penjualan(nama_pelanggan=""):
    """Buat keyboard pilihan barang penjualan dengan harga otomatis"""
    keyboard = []
    for i, barang in enumerate(DAFTAR_BARANG_PENJUALAN, 1):
        if barang == "Kc Bawang Renceng" and nama_pelanggan:
            harga = get_harga_renceng(nama_pelanggan)
            button_text = f"{barang} - {format_rupiah(harga)}"
        else:
            button_text = f"{barang}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"barang_jual_{i}")])
    keyboard.append([InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def buat_keyboard_barang_belanja():
    """Buat keyboard pilihan barang belanja"""
    keyboard = []
    for i, barang in enumerate(DAFTAR_BARANG_BELANJA, 1):
        keyboard.append([InlineKeyboardButton(f"{i}. {barang}", callback_data=f"barang_beli_{i}")])
    keyboard.append([InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def buat_keyboard_pembayaran(total_setelah_retur):
    """Buat keyboard pilihan nominal pembayaran"""
    keyboard = []
    
    # Pilihan sesuai total
    keyboard.append([InlineKeyboardButton(f"💰 Bayar LUNAS: {format_rupiah(total_setelah_retur)}", 
                                        callback_data=f"bayar_pas_{total_setelah_retur}")])
    
    # Input manual
    keyboard.append([InlineKeyboardButton("⌨️ Input Manual", callback_data="bayar_manual")])
    keyboard.append([InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")])
    
    return InlineKeyboardMarkup(keyboard)

def buat_keyboard_histori_pelanggan():
    """Buat keyboard pilihan histori berdasarkan pelanggan"""
    keyboard = []
    
    # Tambahkan semua pelanggan
    for i, pelanggan in enumerate(DAFTAR_PELANGGAN, 1):
        keyboard.append([InlineKeyboardButton(f"👤 {pelanggan}", callback_data=f"histori_pelanggan_{i}")])
    
    # Tambahkan opsi semua pelanggan
    keyboard.append([InlineKeyboardButton("📊 Semua Pelanggan", callback_data="histori_semua")])
    keyboard.append([InlineKeyboardButton("🚫 Tutup", callback_data="cancel")])
    
    return InlineKeyboardMarkup(keyboard)

def format_nota_penjualan(data):
    """Format nota penjualan menjadi teks dengan format kolom yang rapi"""
    
    # Header nota
    nota_text = """
*           𝙱𝙾𝚃 𝙼𝙰𝙽𝙰𝙹𝙴𝙼𝙴𝙽 𝙺𝙴𝚄𝙰𝙽𝙶𝙰𝙽        *
*               𝗕𝗘𝗥𝗞𝗔𝗛 𝗗𝗨𝗔 𝗣𝗨𝗧𝗥𝗜          *
"""
    # Informasi dasar nota
    nota_text += "─" * 26 + "\n\n"
    nota_text += f"📋 *No                   : {data['nomor_nota']}*\n"
    nota_text += f"👤 *Pelanggan      : {data['nama_pelanggan']}*\n"
    nota_text += f"📅 *Tanggal          : {data['tanggal']}*\n"
    nota_text += "─" * 26 + "\n\n"
    # Header tabel barang
    nota_text += "📦 *DAFTAR BARANG:*\n"
    
    # Daftar barang dengan format kolom
    for i, item in enumerate(data['daftar_barang'], 1):
        nama_barang = item['nama']
        qty = f"{item['qty']}x"
        harga_satuan = format_rupiah(item['harga'])
        subtotal = format_rupiah(item['subtotal'])
        
        # Format baris barang
        nota_text += f"{i:2d}. {nama_barang}\n"
        nota_text += f"     {qty} @ {harga_satuan:>12} = {subtotal:>12}\n"
    
    # Barang retur (jika ada)
    if data['retur_items']:
        nota_text += "\n🔄 *BARANG RETUR:*\n"
        
        for i, item in enumerate(data['retur_items'], 1):
            nama_barang = item['nama']
            qty = f"{item['qty']}x"
            harga_satuan = format_rupiah(item['harga'])
            subtotal = format_rupiah(item['subtotal'])
            
            # Format baris retur
            nota_text += f"{i:2d}. {nama_barang}\n"
            nota_text += f"     {qty} @ {harga_satuan:>12} = {subtotal:>12}\n"
    
    # Ringkasan pembayaran
    nota_text += "\n" + "─" * 26 + "\n"
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
    """Format nota belanja menjadi teks dengan format kolom yang rapi"""
    
    # Header nota
    nota_text = """
🛍️ *NOTA BELANJA*
*Kacang Bawang Berkah Dua Putri*

"""
    
    # Informasi dasar nota
    nota_text += f"📋 *No: {data['nomor_nota']}*\n"
    nota_text += f"🏢 *Supplier: {data['nama_supplier']}*\n"
    nota_text += f"📅 *Tanggal: {data['tanggal']}*\n"
    nota_text += "─" * 26 + "\n\n"
    
    # Header tabel barang
    nota_text += "📦 *DAFTAR BARANG:*\n"
    
    # Daftar barang dengan format kolom
    for i, item in enumerate(data['daftar_barang'], 1):
        nama_barang = item['nama']
        qty = f"{item['qty']}x"
        harga_satuan = format_rupiah(item['harga'])
        subtotal = format_rupiah(item['subtotal'])
        
        # Format baris barang
        nota_text += f"{i:2d}. {nama_barang}\n"
        nota_text += f"     {qty} @ {harga_satuan:>12} = {subtotal:>12}\n"
    
    # Ringkasan
    nota_text += "\n" + "─" * 26 + "\n"
    nota_text += "💰 *RINGKASAN BELANJA:*\n"
    
    total_belanja = sum(item['subtotal'] for item in data['daftar_barang'])
    
    nota_text += f"*Total Belanja* : *{format_rupiah(total_belanja):>15}*\n"
    
    if data.get('keterangan'):
        nota_text += f"Keterangan      : {data['keterangan']}\n"
    
    nota_text += "\n_*Catatan pembelian tersimpan*_ 📝"
    
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
    welcome_text = f"{header_pesan}"
    welcome_text += "Silahkan Pilih Menu dibawah"
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode='Markdown',
        reply_markup=buat_keyboard_menu_utama()
    )

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
    
    if callback_data.startswith('menu_'):
        # Handle menu utama
        menu = callback_data.split('_')[1]
        
        if menu == 'jual':
            # Mulai proses penjualan
            session['state'] = 'pilih_pelanggan'
            session['type'] = 'penjualan'
            session['data'] = {
                'daftar_barang': [],
                'retur_items': [],
                'nomor_nota': buat_nomor_nota("PNJ"),
                'tanggal': datetime.datetime.now().strftime("%d/%m/%Y")
            }
            
            await query.edit_message_text(
                """*           𝙱𝙾𝚃 𝙼𝙰𝙽𝙰𝙹𝙴𝙼𝙴𝙽 𝙺𝙴𝚄𝙰𝙽𝙶𝙰𝙽        *\n*               𝗕𝗘𝗥𝗞𝗔𝗛 𝗗𝗨𝗔 𝗣𝗨𝗧𝗥𝗜          *\n"""
                "────────────────────────── \n\n"
                "*BUAT NOTA PENJUALAN*\n\n"
                "Pilih Nama Pelanggan",
                parse_mode='Markdown',
                reply_markup=buat_keyboard_pelanggan()
            )
            
        elif menu == 'beli':
            # Mulai proses belanja
            session['state'] = 'input_nama_supplier'
            session['type'] = 'belanja'
            session['data'] = {
                'daftar_barang': [],
                'nomor_nota': buat_nomor_nota("BLJ"),
                'tanggal': datetime.datetime.now().strftime("%d/%m/%Y")
            }
            
            await query.edit_message_text(
                "🛍️ *BUAT NOTA BELANJA*\n\n"
                "Masukkan nama supplier:",
                parse_mode='Markdown'
            )
            
        elif menu == 'histori':
            # Tampilkan pilihan histori
            await query.edit_message_text(
                "📊 *PILIH HISTORI*\n\n"
                "Pilih berdasarkan pelanggan:",
                parse_mode='Markdown',
                reply_markup=buat_keyboard_histori_pelanggan()
            )
            
        elif menu == 'statistik':
            # Tampilkan statistik
            await tampilkan_statistik(query, user_id)
            
        elif menu == 'info':
            # Tampilkan info dengan keyboard menu
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
            await query.edit_message_text(
                info_text, 
                parse_mode='Markdown',
                reply_markup=buat_keyboard_menu_utama()
            )
    
    elif callback_data.startswith('pelanggan_'):
        # Handle pilihan pelanggan
        pelanggan_index = int(callback_data.split('_')[1]) - 1
        nama_pelanggan = DAFTAR_PELANGGAN[pelanggan_index]
        
        session['data']['nama_pelanggan'] = nama_pelanggan
        session['state'] = 'pilih_barang_penjualan'
        
        await query.edit_message_text(
            """*           𝙱𝙾𝚃 𝙼𝙰𝙽𝙰𝙹𝙴𝙼𝙴𝙽 𝙺𝙴𝚄𝙰𝙽𝙶𝙰𝙽        *\n*               𝗕𝗘𝗥𝗞𝗔𝗛 𝗗𝗨𝗔 𝗣𝗨𝗧𝗥𝗜          *\n"""
            "────────────────────────── \n\n"
            f"*Nama Pelanggan : {nama_pelanggan}*\n\n"
            "📦 Pilih barang",
            parse_mode='Markdown',
            reply_markup=buat_keyboard_barang_penjualan(nama_pelanggan)
        )
    
    elif callback_data.startswith('barang_jual_'):
        # Handle pilihan barang penjualan
        barang_index = int(callback_data.split('_')[2]) - 1
        nama_barang = DAFTAR_BARANG_PENJUALAN[barang_index]
        
        # Tentukan harga otomatis untuk Kc Bawang Renceng
        if nama_barang == "Kc Bawang Renceng":
            nama_pelanggan = session['data']['nama_pelanggan']
            harga_otomatis = get_harga_renceng(nama_pelanggan)
            session['data']['current_item'] = {
                'nama': nama_barang,
                'harga': harga_otomatis
            }
            session['state'] = 'input_qty_barang'
            
            await query.edit_message_text(
                """*           𝙱𝙾𝚃 𝙼𝙰𝙽𝙰𝙹𝙴𝙼𝙴𝙽 𝙺𝙴𝚄𝙰𝙽𝙶𝙰𝙽        *\n*               𝗕𝗘𝗥𝗞𝗔𝗛 𝗗𝗨𝗔 𝗣𝗨𝗧𝗥𝗜          *\n"""
                "────────────────────────── \n\n"
                "📦 *Barang dipilih :*"
                f"*{nama_barang}*\n"
                f"💰 *Harga Otomatis :* {format_rupiah(harga_otomatis)}\n\n"
                "Masukkan jumlah barang :",
                parse_mode='Markdown'
            )
        else:
            session['data']['current_item'] = {'nama': nama_barang}
            session['state'] = 'input_harga_barang'
            
            await query.e0dit_message_text(
                f"📦 *Barang:* {nama_barang}\n\n"
                "Masukkan harga satuan:",
                parse_mode='Markdown'
            )
    
    elif callback_data.startswith('barang_beli_'):
        # Handle pilihan barang belanja
        barang_index = int(callback_data.split('_')[2]) - 1
        nama_barang = DAFTAR_BARANG_BELANJA[barang_index]
        
        session['data']['current_item'] = {'nama': nama_barang}
        session['state'] = 'input_harga_barang_belanja'
        
        await query.edit_message_text(
            f"📦 *Barang:* {nama_barang}\n\n"
            "Masukkan harga satuan:",
            parse_mode='Markdown'
        )
    
    elif callback_data == 'tambah_barang_penjualan':
        # Tambah barang penjualan lagi
        session['state'] = 'pilih_barang_penjualan'
        nama_pelanggan = session['data']['nama_pelanggan']
        await query.edit_message_text(
            "📦 Pilih barang yang dijual:",
            parse_mode='Markdown',
            reply_markup=buat_keyboard_barang_penjualan(nama_pelanggan)
        )
    
    elif callback_data == 'selesai_barang_penjualan':
        # Selesai tambah barang penjualan, lanjut ke pembayaran
        if not session['data']['daftar_barang']:
            await query.edit_message_text("❌ Minimal harus ada 1 barang!")
            return
        
        total_barang = sum(item['subtotal'] for item in session['data']['daftar_barang'])
        total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
        total_setelah_retur = total_barang - total_retur
        
        # Tampilkan ringkasan dan pilihan pembayaran
        summary_text = """*           𝙱𝙾𝚃 𝙼𝙰𝙽𝙰𝙹𝙴𝙼𝙴𝙽 𝙺𝙴𝚄𝙰𝙽𝙶𝙰𝙽        *\n*               𝗕𝗘𝗥𝗞𝗔𝗛 𝗗𝗨𝗔 𝗣𝗨𝗧𝗥𝗜          *\n\n"""
        summary_text += "*RINGKASAN NOTA PENJUALAN*\n\n"
        for item in session['data']['daftar_barang']:
            summary_text += f"• {item['nama']}\n"
            summary_text += f"  {item['qty']} Pcs x = {format_rupiah(item['subtotal'])}\n"
        
        if session['data']['retur_items']:
            summary_text += "\n🔄 *BARANG RETUR:*\n"
            for item in session['data']['retur_items']:
                summary_text += f"• {item['qty']}x {item['nama']} = {format_rupiah(item['subtotal'])}\n"
        
        summary_text += f"\n*TOTAL {format_rupiah(total_setelah_retur)}*\n\n"
        summary_text += "Pilih nominal pembayaran:"
        
        await query.edit_message_text(
            summary_text,
            parse_mode='Markdown',
            reply_markup=buat_keyboard_pembayaran(total_setelah_retur)
        )
    
    elif callback_data == 'tambah_barang_belanja':
        # Tambah barang belanja lagi
        session['state'] = 'pilih_barang_belanja'
        await query.edit_message_text(
            "📦 Pilih jenis belanja:",
            parse_mode='Markdown',
            reply_markup=buat_keyboard_barang_belanja()
        )
    
    elif callback_data == 'selesai_barang_belanja':
        # Selesai tambah barang belanja, lanjut ke total
        if not session['data']['daftar_barang']:
            await query.edit_message_text("❌ Minimal harus ada 1 barang!")
            return
        
        session['state'] = 'input_total_belanja'
        total_belanja = sum(item['subtotal'] for item in session['data']['daftar_barang'])
        
        summary_text = "📋 *RINGKASAN NOTA BELANJA*\n\n"
        for item in session['data']['daftar_barang']:
            summary_text += f"• {item['qty']}x {item['nama']} = {format_rupiah(item['subtotal'])}\n"
        
        summary_text += f"\n💰 *TOTAL: {format_rupiah(total_belanja)}*\n\n"
        summary_text += "Masukkan total belanja (bisa disesuaikan):"
        
        await query.edit_message_text(summary_text, parse_mode='Markdown')
    
    elif callback_data.startswith('bayar_pas_'):
        # Handle bayar pas
        nominal = int(callback_data.split('_')[2])
        await proses_pembayaran(query, session, nominal)
    
    elif callback_data.startswith('bayar_nominal_'):
        # Handle bayar dengan nominal tertentu
        nominal = int(callback_data.split('_')[2])
        await proses_pembayaran(query, session, nominal)
    
    elif callback_data == 'bayar_manual':
        # Handle input manual pembayaran
        session['state'] = 'input_bayar_manual'
        
        total_barang = sum(item['subtotal'] for item in session['data']['daftar_barang'])
        total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
        total_setelah_retur = total_barang - total_retur
        
        await query.edit_message_text(
            f"💰 *Total yang harus dibayar:* {format_rupiah(total_setelah_retur)}\n\n"
            "Masukkan jumlah pembayaran:",
            parse_mode='Markdown'
        )
    
    elif callback_data.startswith('histori_pelanggan_'):
        # Handle histori berdasarkan pelanggan
        pelanggan_index = int(callback_data.split('_')[2]) - 1
        nama_pelanggan = DAFTAR_PELANGGAN[pelanggan_index]
        await tampilkan_histori_pelanggan(query, user_id, nama_pelanggan)
    
    elif callback_data == 'histori_semua':
        # Handle semua histori
        await tampilkan_histori_semua(query, user_id)
    
    elif callback_data == 'cancel':
        # Batalkan proses dan kembali ke menu utama
        session['state'] = 'idle'
        if user_id in user_sessions:
            del user_sessions[user_id]
        await query.edit_message_text(
            "❌ Proses dibatalkan",
            reply_markup=buat_keyboard_menu_utama()
        )

async def proses_pembayaran(query, session, nominal_bayar):
    """Proses pembayaran dan simpan nota"""
    total_barang = sum(item['subtotal'] for item in session['data']['daftar_barang'])
    total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
    total_setelah_retur = total_barang - total_retur
    sisa = nominal_bayar - total_setelah_retur
    
    # Simpan data pembayaran
    session['data']['bayar'] = nominal_bayar
    session['data']['sisa'] = sisa
    session['data']['total_setelah_retur'] = total_setelah_retur
    session['data']['status'] = "LUNAS" if sisa >= 0 else "BELUM LUNAS"
    
    # Simpan ke database
    success = simpan_nota_penjualan(
        user_id=query.from_user.id,
        nomor_nota=session['data']['nomor_nota'],
        nama_pelanggan=session['data']['nama_pelanggan'],
        tanggal=session['data']['tanggal'],
        daftar_barang=session['data']['daftar_barang'],
        retur_items=session['data']['retur_items'],
        total_setelah_retur=total_setelah_retur,
        bayar=nominal_bayar,
        sisa=sisa
    )
    
    if success:
        # Kirim nota
        nota_text = format_nota_penjualan(session['data'])
        await query.edit_message_text(nota_text, parse_mode='Markdown')
        
        # Reset session
        session['state'] = 'idle'
        if query.from_user.id in user_sessions:
            del user_sessions[query.from_user.id]
    else:
        await query.edit_message_text("❌ Gagal menyimpan nota!")

async def tampilkan_histori_pelanggan(query, user_id, nama_pelanggan):
    """Tampilkan histori berdasarkan pelanggan"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT nomor_nota, tanggal, total_setelah_retur, status 
            FROM nota_penjualan 
            WHERE user_id = ? AND nama_pelanggan = ?
            ORDER BY timestamp DESC 
            LIMIT 10
        ''', (user_id, nama_pelanggan))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            await query.edit_message_text(
                f"📭 *Belum ada data histori untuk {nama_pelanggan}*",
                parse_mode='Markdown',
                reply_markup=buat_keyboard_menu_utama()
            )
            return
        
        histori_text = f"📊 *HISTORI - {nama_pelanggan}*\n\n"
        total_penjualan = 0
        
        for row in rows:
            nomor_nota, tanggal, total, status = row
            status_emoji = "✅" if status == "LUNAS" else "⏳"
            histori_text += f"{status_emoji} *{nomor_nota}*\n"
            histori_text += f"   📅 {tanggal}\n"
            histori_text += f"   💰 {format_rupiah(total)}\n\n"
            total_penjualan += total
        
        histori_text += f"📈 *Total Penjualan: {format_rupiah(total_penjualan)}*"
        
        await query.edit_message_text(
            histori_text, 
            parse_mode='Markdown',
            reply_markup=buat_keyboard_menu_utama()
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")

async def tampilkan_histori_semua(query, user_id):
    """Tampilkan semua histori"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT nomor_nota, nama_pelanggan, tanggal, total_setelah_retur, status 
            FROM nota_penjualan 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            await query.edit_message_text(
                "📭 *Belum ada data histori*",
                parse_mode='Markdown',
                reply_markup=buat_keyboard_menu_utama()
            )
            return
        
        histori_text = "📊 *HISTORI SEMUA PELANGGAN*\n\n"
        
        for row in rows:
            nomor_nota, nama_pelanggan, tanggal, total, status = row
            status_emoji = "✅" if status == "LUNAS" else "⏳"
            histori_text += f"{status_emoji} *{nomor_nota}*\n"
            histori_text += f"   👤 {nama_pelanggan}\n"
            histori_text += f"   📅 {tanggal}\n"
            histori_text += f"   💰 {format_rupiah(total)}\n\n"
        
        await query.edit_message_text(
            histori_text, 
            parse_mode='Markdown',
            reply_markup=buat_keyboard_menu_utama()
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")

async def tampilkan_statistik(query, user_id):
    """Tampilkan statistik penjualan dan belanja"""
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
        
        await query.edit_message_text(
            statistik_text, 
            parse_mode='Markdown',
            reply_markup=buat_keyboard_menu_utama()
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error: {str(e)}")

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
    
    if state == 'input_nama_supplier':
        # Simpan nama supplier
        session['data']['nama_supplier'] = message_text
        session['state'] = 'pilih_barang_belanja'
        
        await update.message.reply_text(
            f"🏢 *Supplier:* {message_text}\n\n"
            "📦 Pilih jenis belanja:",
            parse_mode='Markdown',
            reply_markup=buat_keyboard_barang_belanja()
        )
    
    elif state == 'input_harga_barang':
        # Simpan harga barang penjualan (untuk barang selain Kc Bawang Renceng)
        try:
            harga = int(message_text.replace(".", "").replace(",", ""))
            session['data']['current_item']['harga'] = harga
            session['state'] = 'input_qty_barang'
            
            await update.message.reply_text(
                f"💰 *Harga:* {format_rupiah(harga)}\n\n"
                "Masukkan jumlah barang:",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_qty_barang':
        # Simpan quantity barang penjualan
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
            session['state'] = 'pilih_tambah_barang_penjualan'
            
            # Tampilkan ringkasan sementara
            total_sementara = sum(item['subtotal'] for item in session['data']['daftar_barang'])
            
            summary_text = """*           𝙱𝙾𝚃 𝙼𝙰𝙽𝙰𝙹𝙴𝙼𝙴𝙽 𝙺𝙴𝚄𝙰𝙽𝙶𝙰𝙽        *\n*               𝗕𝗘𝗥𝗞𝗔𝗛 𝗗𝗨𝗔 𝗣𝗨𝗧𝗥𝗜          *\n\n"""
            summary_text += f"✅ *Barang ditambahkan:*\n{current_item['nama']}\nQty: {qty} x {format_rupiah(current_item['harga'])} = {format_rupiah(current_item['subtotal'])}\n\n"
            summary_text += f"💰 *Total sementara:* {format_rupiah(total_sementara)}\n\n"
            summary_text += "Pilih opsi di bawah:"
            
            # Buat keyboard untuk pilihan selanjutnya
            keyboard = [
                [InlineKeyboardButton("➕ Tambah Barang Lain", callback_data="tambah_barang_penjualan")],
                [InlineKeyboardButton("✅ Selesai Tambah Barang", callback_data="selesai_barang_penjualan")],
                [InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                summary_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_harga_barang_belanja':
        # Simpan harga barang belanja
        try:
            harga = int(message_text.replace(".", "").replace(",", ""))
            session['data']['current_item']['harga'] = harga
            session['state'] = 'input_qty_barang_belanja'
            
            await update.message.reply_text(
                f"💰 *Harga:* {format_rupiah(harga)}\n\n"
                "Masukkan jumlah barang:",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_qty_barang_belanja':
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
            
            # Buat keyboard untuk pilihan selanjutnya
            keyboard = [
                [InlineKeyboardButton("➕ Tambah Barang Lain", callback_data="tambah_barang_belanja")],
                [InlineKeyboardButton("✅ Selesai Tambah Barang", callback_data="selesai_barang_belanja")],
                [InlineKeyboardButton("🚫 Batalkan", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                summary_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_total_belanja':
        # Handle input total belanja
        try:
            total_belanja = int(message_text.replace(".", "").replace(",", ""))
            
            # Simpan dan proses nota belanja
            session['data']['total_belanja'] = total_belanja
            
            # Simpan ke database
            success = simpan_nota_belanja(
                user_id=user_id,
                nomor_nota=session['data']['nomor_nota'],
                nama_supplier=session['data']['nama_supplier'],
                tanggal=session['data']['tanggal'],
                daftar_barang=session['data']['daftar_barang'],
                total_belanja=total_belanja,
                keterangan=""
            )
            
            if success:
                # Kirim nota
                session['data']['keterangan'] = ""
                nota_text = format_nota_belanja(session['data'])
                await update.message.reply_text(nota_text, parse_mode='Markdown')
                
                # Reset session
                session['state'] = 'idle'
                if user_id in user_sessions:
                    del user_sessions[user_id]
            else:
                await update.message.reply_text("❌ Gagal menyimpan nota!")
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif state == 'input_bayar_manual':
        # Handle input manual pembayaran
        try:
            nominal_bayar = int(message_text.replace(".", "").replace(",", ""))
            
            total_barang = sum(item['subtotal'] for item in session['data']['daftar_barang'])
            total_retur = sum(item['subtotal'] for item in session['data']['retur_items'])
            total_setelah_retur = total_barang - total_retur
            sisa = nominal_bayar - total_setelah_retur
            
            # Simpan data pembayaran
            session['data']['bayar'] = nominal_bayar
            session['data']['sisa'] = sisa
            session['data']['total_setelah_retur'] = total_setelah_retur
            session['data']['status'] = "LUNAS" if sisa >= 0 else "BELUM LUNAS"
            
            # Simpan ke database
            success = simpan_nota_penjualan(
                user_id=user_id,
                nomor_nota=session['data']['nomor_nota'],
                nama_pelanggan=session['data']['nama_pelanggan'],
                tanggal=session['data']['tanggal'],
                daftar_barang=session['data']['daftar_barang'],
                retur_items=session['data']['retur_items'],
                total_setelah_retur=total_setelah_retur,
                bayar=nominal_bayar,
                sisa=sisa
            )
            
            if success:
                # Kirim nota
                nota_text = format_nota_penjualan(session['data'])
                await update.message.reply_text(nota_text, parse_mode='Markdown')
                
                # Reset session
                session['state'] = 'idle'
                if user_id in user_sessions:
                    del user_sessions[user_id]
            else:
                await update.message.reply_text("❌ Gagal menyimpan nota!")
            
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")

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
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Jalankan bot
    logger.info("🤖 Bot sedang berjalan...")
    
    try:
        application.run_polling()
    except KeyboardInterrupt:
        logger.info("🛑 Bot dihentikan")
    except Exception as e:
        logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()