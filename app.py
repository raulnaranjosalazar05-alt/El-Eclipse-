import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- CONFIGURACIÓN ---
TOKEN = os.environ.get("TOKEN")
URL_RENDER = os.environ.get("RENDER_EXTERNAL_URL")
PORT = int(os.environ.get("PORT", 8080))

# Creamos la app web y el bot
app_web = Flask(__name__)
app_bot = Application.builder().token(TOKEN).build()

# --- COMANDOS DEL BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Registro iniciado. El portal está abriendo.\n"
        "Pronto podrás crear tu Cazador.",
        parse_mode="Markdown"
    )

app_bot.add_handler(CommandHandler("start", start))

# --- RUTAS WEB ---
@app_web.route("/")
def home():
    return "El Sistema esta vivo.", 200

@app_web.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    # Telegram envía el mensaje aquí
    update = Update.de_json(request.get_json(force=True), app_bot.bot)
    app_bot.update_queue.put_nowait(update)
    return "OK", 200

# --- INICIO ---
if __name__ == "__main__":
    # Le decimos a Telegram a dónde enviar los mensajes
    if URL_RENDER:
        webhook_url = f"{URL_RENDER}/{TOKEN}"
        app_bot.bot.set_webhook(url=webhook_url)
        print(f"Webhook configurado en: {webhook_url}")
    
    # Arrancamos el servidor web (esto mantiene a Render feliz)
    app_web.run(host="0.0.0.0", port=PORT)
