import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import psycopg2

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
URL_RENDER = os.environ.get("RENDER_EXTERNAL_URL") # Render la da automáticamente
PORT = int(os.environ.get("PORT", 8080))

app_web = Flask(__name__)
app_bot = Application.builder().token(TOKEN).build()

# --- BASE DE DATOS ---
def init_db():
    if not DATABASE_URL:
        print("No hay DATABASE_URL, saltando base de datos.")
        return
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_telegram BIGINT PRIMARY KEY,
                nombre VARCHAR(50),
                clase VARCHAR(20)
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Base de datos lista.")
    except Exception as e:
        print(f"Error en DB: {e}")

# --- COMANDOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            cur = conn.cursor()
            cur.execute("SELECT id_telegram FROM usuarios WHERE id_telegram = %s", (user_id,))
            existe = cur.fetchone()
            if not existe:
                cur.execute("INSERT INTO usuarios (id_telegram, nombre) VALUES (%s, %s)", (user_id, username))
                conn.commit()
                mensaje = f"🌑 *El Sistema te ha detectado.*\n\nBienvenido, Sujeto {username}.\nTu registro ha sido guardado."
            else:
                mensaje = f"🌑 *Regreso detectado.*\n\nHola de nuevo, Sujeto {username}."
            cur.close()
            conn.close()
        except Exception as e:
            mensaje = f"🌑 *El Sistema te ha detectado.*\n\nBienvenido, Sujeto {username}.\n(Error de memoria, pero estás vivo)."
    else:
        mensaje = f"🌑 *El Sistema te ha detectado.*\n\nBienvenido, Sujeto {username}.\n(base de datos no conectada)."
        
    await update.message.reply_text(mensaje, parse_mode="Markdown")

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
    init_db()
    
    # Configurar el Webhook (el puente entre Telegram y Render)
    if URL_RENDER:
        webhook_url = f"{URL_RENDER}/{TOKEN}"
        app_bot.bot.set_webhook(url=webhook_url)
        print(f"Webhook configurado en: {webhook_url}")
    else:
        print("ADVERTENCIA: RENDER_EXTERNAL_URL no está definida. El bot no podrá recibir mensajes.")
    
    # Arrancar el servidor web
    print(f"Servidor escuchando en el puerto {PORT}")
    app_web.run(host="0.0.0.0", port=PORT)
