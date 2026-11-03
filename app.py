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
        
        # ¡OJO! Esto borra la tabla vieja para actualizarla con las nuevas columnas.
        # Como estamos en pruebas, está perfecto. Cuando el juego salga a la luz, quitaremos esta línea.
        cur.execute("DROP TABLE IF EXISTS usuarios;")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_telegram BIGINT PRIMARY KEY,
                nombre VARCHAR(50),
                clase VARCHAR(20),
                sexo VARCHAR(10),
                maestro_id BIGINT,
                historia TEXT,
                foto_url TEXT,
                nivel INT DEFAULT 1,
                vida INT DEFAULT 100,
                atq INT DEFAULT 10,
                mov INT DEFAULT 10,
                intel INT DEFAULT 10,
                res INT DEFAULT 10,
                tac INT DEFAULT 10
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Base de datos lista y actualizada.")
    except Exception as e:
        print(f"❌ ERROR DE BD: {e}")

# --- COMANDO /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    try:
        await update.message.delete()
    except:
        pass 

    maestro_id = None
    if context.args:
        try:
            maestro_id = int(context.args[0])
            if maestro_id == user_id:
                maestro_id = None 
        except ValueError:
            pass

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    
    if resultado and resultado[0] is not None:
        cur.close()
        conn.close()
        await update.message.reply_text(
            "🌑 *Regreso detectado.*\n\nEl Sistema ya tiene tu registro. Pronto podrás pelear.",
            parse_mode="Markdown"
        )
        return

    context.user_data['maestro_id'] = maestro_id

    await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Antes de cruzar el primer portal, necesito tu designación.\n"
        "**¿Cuál es tu nombre, Sujeto?**",
        parse_mode="Markdown"
    )
    context.user_data['esperando_nombre'] = True
    cur.close()
    conn.close()

# --- RECIBIR EL NOMBRE ---
async def recibir_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('esperando_nombre'):
        if not update.message.text:
            try:
                await update.message.delete() 
            except:
                pass
            await update.message.reply_text("⚠️ El Sistema no procesa imágenes ni audios aquí. **Escribe tu nombre con letras.**", parse_mode="Markdown")
            return
            
        nombre_elegido = update.message.text
        
        try:
            await update.message.delete()
        except:
            pass

        context.user_data['nombre_temp'] = nombre_elegido
        context.user_data['esperando_nombre'] = False
        
        keyboard = [
            [InlineKeyboardButton("♂️ Masculino", callback_data='sexo_m')],
            [InlineKeyboardButton("♀️ Femenino", callback_data='sexo_f')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Registro aceptado, **{nombre_elegido}**.\n\n"
            "El Sistema necesita conocer tu estructura biológica para el registro visual.\n"
            "**Selecciona tu sexo:**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

# --- RECIBIR EL SEXO ---
async def boton_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    sexo_elegido = "M" if query.data == 'sexo_m' else "F"
    context.user_data['sexo_temp'] = sexo_elegido
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Espadachín", callback_data='clase_espadachin')],
        [InlineKeyboardButton("🔮 Mago", callback_data='clase_mago')],
        [InlineKeyboardButton("🛡️ Guardián", callback_data='clase_guardian')],
        [InlineKeyboardButton("🗡️ Asesino", callback_data='clase_asesino')],
        [InlineKeyboardButton("🏹 Arquero", callback_data='clase_arquero')],
        [InlineKeyboardButton("✨ Clérigo", callback_data='clase_clerigo')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Sexo registrado.\n\n"
        "Ahora el Sistema necesita saber qué camino tomarás. **Elige tu clase:**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# --- RECIBIR LA CLASE ---
async def boton_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    
    user_id = update.effective_user.id
    clase_elegida = query.data.replace('clase_', '') 
    nombre_elegido = context.user_data.get('nombre_temp', 'Desconocido')
    sexo_elegido = context.user_data.get('sexo_temp', 'M')
    maestro_id = context.user_data.get('maestro_id', None)
    
    stats = {
        'espadachin': {'vida': 120, 'atq': 25, 'mov': 15, 'intel': 5,  'res': 15, 'tac': 15},
        'mago':       {'vida': 80,  'atq': 5,  'mov': 10, 'intel': 25, 'res': 10, 'tac': 25},
        'guardian':   {'vida': 180, 'atq': 10, 'mov': 5,  'intel': 10, 'res': 25, 'tac': 25},
        'asesino':    {'vida': 90,  'atq': 20, 'mov': 25, 'intel': 5,  'res': 5,  'tac': 20},
        'arquero':    {'vida': 100, 'atq': 15, 'mov': 20, 'intel': 10, 'res': 10, 'tac': 20},
        'clerigo':    {'vida': 110, 'atq': 10, 'mov': 10, 'intel': 20, 'res': 15, 'tac': 20}
    }
    
    s = stats.get(clase_elegida, stats['espadachin'])
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (id_telegram, nombre, clase, sexo, maestro_id, vida, atq, mov, intel, res, tac)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_telegram) DO UPDATE SET
        nombre = EXCLUDED.nombre, clase = EXCLUDED.clase, sexo = EXCLUDED.sexo, maestro_id = EXCLUDED.maestro_id, vida = EXCLUDED.vida, atq = EXCLUDED.atq, mov = EXCLUDED.mov, intel = EXCLUDED.intel, res = EXCLUDED.res, tac = EXCLUDED.tac
    """, (user_id, nombre_elegido, clase_elegida.capitalize(), sexo_elegido, maestro_id, s['vida'], s['atq'], s['mov'], s['intel'], s['res'], s['tac']))
    conn.commit()
    cur.close()
    conn.close()
    
    texto_final = (
        f"✅ *REGISTRO COMPLETADO*\n\n"
        f"👤 Sujeto: **{nombre_elegido}**\n"
        f"⚔️ Clase: **{clase_elegida.capitalize()}**\n"
        f"♂️/♀️ Sexo: **{'Masculino' if sexo_elegido == 'M' else 'Femenino'}**\n"
        f"📊 Nivel: **1**\n\n"
        f"❤️ Vida: {s['vida']}\n"
        f"⚔️ Ataque: {s['atq']}\n"
        f"💨 Movilidad: {s['mov']}\n"
        f"🧠 Inteligencia: {s['intel']}\n"
        f"🛡️ Resistencia: {s['res']}\n"
        f"🎯 Táctica: {s['tac']}\n\n"
    )
    
    if maestro_id:
        texto_final += f"👑 *Has sido registrado bajo la tutela de un Maestro.*\n\n"
        
    texto_final += "*El Sistema te observa. Prepárate para el primer portal.*"
    
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
    app.add_handler(CallbackQueryHandler(boton_sexo, pattern='^sexo_'))
    app.add_handler(CallbackQueryHandler(boton_clase, pattern='^clase_'))
    
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
