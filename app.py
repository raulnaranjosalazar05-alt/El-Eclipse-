import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
PORT = int(os.environ.get("PORT", 8080))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Registro iniciado. El portal está abriendo.\n"
        "Pronto podrás crear tu Cazador.",
        parse_mode="Markdown"
    )

class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"El Sistema esta vivo.")

def main():
    # 1. Arrancamos el falso servidor web para que Render no nos apague
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # 2. Arrancamos el bot
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("El Sistema ha despertado. Escuchando...")
    
    # El drop_pending_updates=True es vital para limpiar mensajes viejos
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
