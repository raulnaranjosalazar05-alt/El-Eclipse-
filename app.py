import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get("TOKEN")
URL_RENDER = os.environ.get("RENDER_EXTERNAL_URL") # Render la da automáticamente
PORT = int(os.environ.get("PORT", 8080))

# --- COMANDOS DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Registro iniciado. El portal está abriendo.\n"
        "Pronto podrás crear tu Cazador.",
        parse_mode="Markdown"
    )

# --- SERVIDOR WEB (Para que Render no se queje) ---
class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"El Sistema esta vivo.")

    def do_POST(self):
        # Telegram enviará los mensajes aquí
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        # Procesar el mensaje con el bot
        import json
        update = Update.de_json(json.loads(post_data.decode('utf-8')), app.bot)
        app.update_queue.put_nowait(update)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

# --- INICIO DEL BOT ---
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

def run_server():
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    server.serve_forever()

if __name__ == "__main__":
    # 1. Iniciar el servidor web en un hilo aparte
    threading.Thread(target=run_server, daemon=True).start()
    
    # 2. Configurar el Webhook en Telegram
    if URL_RENDER:
        webhook_url = f"{URL_RENDER}/{TOKEN}"
        app.bot.set_webhook(url=webhook_url)
        print(f"Webhook configurado en: {webhook_url}")
    
    # 3. Arrancar el bot
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{URL_RENDER}/{TOKEN}" if URL_RENDER else None
    )
