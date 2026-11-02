import os
import threading
import psycopg2
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL") # Render la crea sola si enlazas la DB
PORT = int(os.environ.get("PORT", 8080))

# --- BASE DE DATOS ---
def init_db():
    # Se conecta a la base de datos de Render
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    # Crea la tabla de usuarios si no existe
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id_telegram BIGINT PRIMARY KEY,
            nombre VARCHAR(50),
            clase VARCHAR(20),
            nivel INT DEFAULT 1,
            vida INT DEFAULT 100,
            ataque INT DEFAULT 10,
            movilidad INT DEFAULT 10,
            inteligencia INT DEFAULT 10,
            vitalidad INT DEFAULT 10,
            tactica INT DEFAULT 10
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# --- COMANDOS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    # Guardamos al usuario en la base de datos si es nuevo
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT id_telegram FROM usuarios WHERE id_telegram = %s", (user_id,))
    existe = cur.fetchone()
    
    if not existe:
        cur.execute(
            "INSERT INTO usuarios (id_telegram, nombre) VALUES (%s, %s)",
            (user_id, username)
        )
        conn.commit()
        mensaje = f"🌑 *El Sistema te ha detectado.*\n\nBienvenido, Sujeto {username}.\nTu registro ha sido guardado en la base de datos. Pronto elegirás tu clase."
    else:
        mensaje = f"🌑 *Regreso detectado.*\n\nHola de nuevo, Sujeto {username}. El Sistema no olvida a los suyos."
        
    cur.close()
    conn.close()
    
    await update.message.reply_text(mensaje, parse_mode="Markdown")

class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"El Sistema esta vivo.")

def main():
    # Arrancar servidor web para Render
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    # Iniciar Base de Datos
    if DATABASE_URL:
        init_db()
        print("Base de datos conectada y lista.")

    # Arrancar Bot
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("Escuchando a los Sujetos...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
