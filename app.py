import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
PORT = int(os.environ.get("PORT", 8080))

# --- COMANDOS DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Registro iniciado. El portal está abriendo.\n"
        "Pronto podrás crear tu Cazador.",
        parse_mode="Markdown"
    )

# --- SERVIDOR WEB FALSO (Para que Render no apague el bot) ---
class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"El Sistema esta vivo.")

# --- INICIO ---
if __name__ == "__main__":
    # 1. Encendemos el servidor web falso en un hilo
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # 2. Encendemos el bot
    app_bot = Application.builder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    
    print("El Sistema ha despertado. Escuchando a los Cazadores...")
    app_bot.run_polling(drop_pending_updates=True)
