import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- TRUCO PARA RENDER ---
# Render necesita un puerto web abierto para no apagar el bot
class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"El Sistema esta vivo.")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), WebServer)
    server.serve_forever()

# --- LÓGICA DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Registro iniciado. Pronto podrás crear tu Cazador y entrar a los portales.\n"
        "Por ahora, el Sistema solo está probando tu conexión.",
        parse_mode="Markdown"
    )

def main():
    # Iniciar el servidor web falso en un hilo aparte
    threading.Thread(target=run_web_server, daemon=True).start()

    # Iniciar el bot de Telegram
    # ¡AQUÍ DEBES PONER TU TOKEN REAL ENTRE LAS COMILLAS!
    TOKEN = "AQUI_PEGAS_EL_TOKEN_DE_BOTFATHER"
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("El Eclipse ha despertado...")
    app.run_polling()

if __name__ == "__main__":
    main()
