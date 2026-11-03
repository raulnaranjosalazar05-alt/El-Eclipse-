import os
import threading
import psycopg2
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))

# --- BASE DE DATOS ---
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_telegram BIGINT PRIMARY KEY,
                nombre VARCHAR(50),
                clase VARCHAR(20),
                nivel INT DEFAULT 1,
                vida INT DEFAULT 100,
                atq INT DEFAULT 10,
                mov INT DEFAULT 10,
                intel INT DEFAULT 10,
                vit INT DEFAULT 10,
                tac INT DEFAULT 10
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Base de datos lista.")
    except Exception as e:
        print(f"❌ ERROR DE BD: {e}")

# --- COMANDO /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    cur.close()
    conn.close()

    if resultado and resultado[0] is not None:
        await update.message.reply_text(
            "🌑 *Regreso detectado.*\n\nEl Sistema ya tiene tu registro. Pronto podrás luchar.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Antes de cruzar el primer portal, necesito tu designación.\n"
        "**¿Cuál es tu nombre, Sujeto?**",
        parse_mode="Markdown"
    )
    context.user_data['esperando_nombre'] = True

# --- RECIBIR EL NOMBRE ---
async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('esperando_nombre'):
        if not update.message.text:
            await update.message.reply_text("⚠️ El Sistema solo acepta texto. Escribe tu nombre.")
            return
            
        nombre_elegido = update.message.text
        context.user_data['nombre_temp'] = nombre_elegido
        context.user_data['esperando_nombre'] = False
        
        keyboard = [
            [InlineKeyboardButton("⚔️ Espadachín", callback_data='clase_espadachin')],
            [InlineKeyboardButton("🔮 Mago", callback_data='clase_mago')],
            [InlineKeyboardButton("🛡️ Guardián", callback_data='clase_guardian')],
            [InlineKeyboardButton("🗡️ Asesino", callback_data='clase_asesino')],
            [InlineKeyboardButton("🏹 Arquero", callback_data='clase_arquero')],
            [InlineKeyboardButton("✨ Clérigo", callback_data='clase_clerigo')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Registro aceptado, **{nombre_elegido}**.\n\n"
            "Ahora el Sistema necesita saber qué camino tomarás. **Elige tu clase:**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# --- RECIBIR EL BOTÓN DE LA CLASE ---
async def boton_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    
    user_id = update.effective_user.id
    clase_elegida = query.data.replace('clase_', '') 
    nombre_elegido = context.user_data.get('nombre_temp', 'Desconocido')
    
    # --- ESTADÍSTICAS SIMPLES (5, 10, 15, 20, 25) ---
    stats = {
        # ATQ, MOV, INT, VIT, TAC
        'espadachin': {'vida': 120, 'atq': 25, 'mov': 15, 'intel': 5, 'vit': 15, 'tac': 15},
        'mago':       {'vida': 80,  'atq': 5,  'mov': 10, 'intel': 25, 'vit': 10, 'tac': 25},
        'guardian':   {'vida': 180, 'atq': 10, 'mov': 5,  'intel': 10, 'vit': 25, 'tac': 25},
        'asesino':    {'vida': 90,  'atq': 20, 'mov': 25, 'intel': 5,  'vit': 5,  'tac': 20},
        'arquero':    {'vida': 100, 'atq': 15, 'mov': 20, 'intel': 10, 'vit': 10, 'tac': 20},
        'clerigo':    {'vida': 110, 'atq': 10, 'mov': 10, 'intel': 20, 'vit': 15, 'tac': 20}
    }
    
    s = stats.get(clase_elegida, stats['espadachin'])
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (id_telegram, nombre, clase, vida, atq, mov, intel, vit, tac)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_telegram) DO UPDATE SET
        nombre = EXCLUDED.nombre, clase = EXCLUDED.clase, vida = EXCLUDED.vida, atq = EXCLUDED.atq, mov = EXCLUDED.mov, intel = EXCLUDED.intel, vit = EXCLUDED.vit, tac = EXCLUDED.tac
    """, (user_id, nombre_elegido, clase_elegida.capitalize(), s['vida'], s['atq'], s['mov'], s['intel'], s['vit'], s['tac']))
    conn.commit()
    cur.close()
    conn.close()
    
    texto_final = (
        f"✅ *REGISTRO COMPLETADO*\n\n"
        f"👤 Sujeto: **{nombre_elegido}**\n"
        f"🌟 Clase: **{clase_elegida.capitalize()}**\n"
        f"🔝 Nivel: **1**\n\n"
        f"❤️ Vida: {s['vida']}\n"
        f"🤜 Ataque: {s['atq']}\n"
        f"👣 Movilidad: {s['mov']}\n"
        f"🧠 Inteligencia: {s['intel']}\n"
        f"🛡️ Vitalidad: {s['vit']}\n"
        f"🎯 Táctica: {s['tac']}\n\n"
        f"*El Sistema te observa. Prepárate para el primer portal.*"
    )
    
    await query.edit_message_text(text=texto_final, parse_mode="Markdown")

# --- SERVIDOR WEB FALSO ---
class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"El Sistema esta vivo.")

def main():
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    init_db()

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nombre))
    app.add_handler(CallbackQueryHandler(boton_clase))
    
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
