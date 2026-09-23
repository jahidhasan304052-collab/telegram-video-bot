import os
import sqlite3
import secrets
import string
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# SETTINGS
# =========================

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 8696209858
DB_NAME = "videos.db"

# =========================
# DATABASE
# =========================

def init_db():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            code TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            caption TEXT
        )
    """)

    conn.execute(
        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
        (OWNER_ID,)
    )

    conn.commit()
    conn.close()


def is_admin(user_id):
    conn = sqlite3.connect(DB_NAME)

    result = conn.execute(
        "SELECT 1 FROM admins WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    conn.close()

    return result is not None


def generate_code():
    while True:
        code = "BV" + "".join(
            secrets.choice(string.digits)
            for _ in range(6)
        )

        conn = sqlite3.connect(DB_NAME)

        exists = conn.execute(
            "SELECT 1 FROM videos WHERE code = ?",
            (code,)
        ).fetchone()

        conn.close()

        if not exists:
            return code


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🤖 স্বাগতম!\n\n"
        "🎬 ভিডিও দেখতে পোস্টের কোড পাঠাও।\n"
        "উদাহরণ: BV123456\n\n"
        "📌 Admin হলে সরাসরি ভিডিও পাঠাতে পারবে।"
    )


# =========================
# VIDEO UPLOAD
# =========================

async def upload_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text(
            "❌ শুধু Admin ভিডিও আপলোড করতে পারবে।"
        )
        return

    video = update.message.video

    code = generate_code()
    file_id = video.file_id
    caption = update.message.caption or ""

    conn = sqlite3.connect(DB_NAME)

    conn.execute(
        "INSERT INTO videos (code, file_id, caption) VALUES (?, ?, ?)",
        (code, file_id, caption)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ ভিডিও সংরক্ষণ হয়েছে!\n\n"
        f"🔑 Video Code: `{code}`\n\n"
        f"এই কোড ব্যবহার করে ভিডিও পাওয়া যাবে।",
        parse_mode="Markdown"
    )


# =========================
# VIDEO SEARCH
# =========================

async def get_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text.strip().upper()

    if not text.startswith("BV"):
        return

    conn = sqlite3.connect(DB_NAME)

    result = conn.execute(
        "SELECT file_id, caption FROM videos WHERE code = ?",
        (text,)
    ).fetchone()

    conn.close()

    if not result:
        await update.message.reply_text(
            "❌ এই কোডের কোনো ভিডিও পাওয়া যায়নি।"
        )
        return

    file_id, caption = result

    await update.message.reply_video(
        video=file_id,
        caption=caption or None
    )


# =========================
# ADD ADMIN
# =========================

async def add_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ শুধু Owner পারবে।")
        return

    if not context.args:
        await update.message.reply_text(
            "ব্যবহার:\n/addadmin USER_ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ সঠিক User ID দাও।")
        return

    conn = sqlite3.connect(DB_NAME)

    conn.execute(
        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
        (user_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Admin যোগ হয়েছে!\nUser ID: {user_id}"
    )


# =========================
# REMOVE ADMIN
# =========================

async def remove_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ শুধু Owner পারবে।")
        return

    if not context.args:
        await update.message.reply_text(
            "ব্যবহার:\n/deladmin USER_ID"
        )
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ সঠিক User ID দাও।")
        return

    if user_id == OWNER_ID:
        await update.message.reply_text(
            "❌ Owner-কে বাদ দেওয়া যাবে না।"
        )
        return

    conn = sqlite3.connect(DB_NAME)

    conn.execute(
        "DELETE FROM admins WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Admin সরানো হয়েছে!\nUser ID: {user_id}"
    )


# =========================
# ADMIN LIST
# =========================

async def list_admins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ শুধু Owner পারবে।")
        return

    conn = sqlite3.connect(DB_NAME)

    admins = conn.execute(
        "SELECT user_id FROM admins"
    ).fetchall()

    conn.close()

    text = "👑 Admin List:\n\n"

    for admin in admins:
        text += f"• {admin[0]}\n"

    await update.message.reply_text(text)


# =========================
# RENDER PORT
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

    def log_message(self, format, *args):
        pass


def run_server():

    port = int(os.getenv("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    server.serve_forever()


# =========================
# MAIN
# =========================

def main():

    if not TOKEN:
        raise ValueError("BOT_TOKEN is missing!")

    init_db()

    threading.Thread(
        target=run_server,
        daemon=True
    ).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("deladmin", remove_admin))
    app.add_handler(CommandHandler("admins", list_admins))

    app.add_handler(
        MessageHandler(filters.VIDEO, upload_video)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            get_video
        )
    )

    print("Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
