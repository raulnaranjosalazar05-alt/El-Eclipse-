import os
import threading
import psycopg2
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))

def init_db():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL no está configurada en Render.")
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
        print("✅ Base de datos conectada y lista.")
    except Exception as e:
        print(f"❌ ERROR DE CONEXIÓN A LA BD: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    mensaje = f"🌑 *El Sistema te ha detectado.*\n\nBienvenido, Sujeto {username}."

    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            cur = conn.cursor()
            cur.execute("SELECT id_telegram FROM usuarios WHERE id_telegram = %s", (user_id,))
            if not cur.fetchone():
                cur.execute("INSERT INTO usuarios (id_telegram, nombre) VALUES (%s, %s)", (user_id, username))
                conn.commit()
                mensaje += "\nTu registro ha sido guardado en la memoria del Sistema."
            else:
                mensaje = f"🌑 *Regreso detectado.*\n\nHola de nuevo, Sujeto {username}."
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Error en el comando start: {e}")
            mensaje += "\n(El Sistema tuvo un fallo de memoria, pero sigues vivo)."
            
    await update.message.reply_text(mensaje, parse_mode="Markdown")

class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"El Sistema esta vivo.")

def main():
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    if DATABASE_URL:
        init_db()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
