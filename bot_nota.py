import os
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from nota_core import (
    DAFTAR_BARANG,
    buat_nomor_nota,
    simpan_histori_nota,
    simpan_sebagai_gambar,
    baca_histori_nota,
)

# ===============================
#  SETUP
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # diset di Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===============================
#  COMMAND: /start
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selamat datang di Bot Nota!"
        "Perintah yang tersedia:\n"
        "• /buatnota <nama> <barang> <bayar>\n"
        "   Contoh: /buatnota Budi 'Kc Bwg Renceng:2,Kc Bwg Toples 1 Kg:1' 100000\n\n"
        "• /histori — Melihat 20 nota terbaru\n"
        "• /detail <nomor_nota> — Detail nota tertentu\n"
    )

# ===============================
#  COMMAND: /buatnota
# ===============================
async def buatnota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 3:
            return await update.message.reply_text(
                "Format salah.\nContoh:\n"
                "/buatnota Budi 'Kc Bwg Renceng:2,Kc Bwg Toples 1 Kg:1' 100000"
            )

        nama = args[0]
        daftar_barang_raw = args[1]
        bayar = int(args[2])

        # ===============================
        #  Parse barang
        # ===============================
        items = daftar_barang_raw.split(",")
        daftar_barang = []
        nomor = 1
        total = 0

        for item in items:
            nama_item, qty_str = item.split(":")
            qty = int(qty_str)

            # cari harga barang
            harga = None
            nama_fix = None
            for b in DAFTAR_BARANG:
                if b["nama"].lower() == nama_item.lower():
                    harga = b["harga"]
                    nama_fix = b["nama"]
                    break

            if harga is None:
                return await update.message.reply_text(f"Barang '{nama_item}' tidak ditemukan dalam daftar.")

            jumlah = harga * qty
            total += jumlah

            daftar_barang.append({
                "no": nomor,
                "nama": nama_fix,
                "harga": harga,
                "qty": qty,
                "jumlah": jumlah
            })
            nomor += 1

        nomor_nota = buat_nomor_nota()
        tanggal = datetime.now().strftime("%d/%m/%Y")
        retur_items = []
        total_setelah = total
        sisa = bayar - total_setelah

        # ===============================
        #  Buat PNG nota
        # ===============================
        img_path = simpan_sebagai_gambar(
            nomor_nota, nama, tanggal,
            daftar_barang, retur_items,
            total_setelah, bayar, sisa
        )

        # ===============================
        #  Simpan database
        # ===============================
        simpan_histori_nota(
            nomor_nota, nama, tanggal,
            daftar_barang, retur_items,
            total_setelah, bayar, sisa
        )

        # ===============================
        #  Balas ke Telegram
        # ===============================
        await update.message.reply_photo(photo=open(img_path, "rb"))
        await update.message.reply_text(f"Nota berhasil dibuat!\nNomor: {nomor_nota}")

    except Exception as e:
        logger.error(e)
        await update.message.reply_text(f"Terjadi error: {e}")

# ===============================
#  COMMAND: /histori
# ===============================
async def histori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = baca_histori_nota(limit=20)
    if not data:
        return await update.message.reply_text("Histori kosong.")

    teks = "20 Nota Terbaru:\n\n"
    for nota in data:
        teks += f"• {nota['nomor_nota']} — {nota['nama_pelanggan']} — Rp {nota['total_setelah_retur']}\n"

    await update.message.reply_text(teks)

# ===============================
#  COMMAND: /detail
# ===============================
async def detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Format: /detail <nomor_nota>")

    nomor = context.args[0]
    data = baca_histori_nota()

    for nota in data:
        if nota["nomor_nota"] == nomor:
            teks = (
                f"Nomor Nota: {nota['nomor_nota']}\n"
                f"Nama: {nota['nama_pelanggan']}\n"
                f"Tanggal: {nota['tanggal']}\n"
                f"Total: Rp {nota['total_setelah_retur']}\n"
                f"Status: {nota['status']}\n"
                f"Keterangan: {nota['keterangan']}"
            )
            return await update.message.reply_text(teks)

    await update.message.reply_text("Nota tidak ditemukan.")


# ===============================
#  MAIN
# ===============================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buatnota", buatnota))
    app.add_handler(CommandHandler("histori", histori))
    app.add_handler(CommandHandler("detail", detail))

    app.run_polling()


if __name__ == "__main__":
    main()