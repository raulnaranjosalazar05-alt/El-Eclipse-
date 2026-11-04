import os
import threading
import psycopg2
import urllib.parse
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
        cur.execute("DROP TABLE IF EXISTS usuarios;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_telegram BIGINT PRIMARY KEY,
                nombre VARCHAR(50),
                clase VARCHAR(20),
                sexo VARCHAR(10),
                rango VARCHAR(5) DEFAULT 'E',
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
        print("✅ Base de datos lista.")
    except Exception as e:
        print(f"❌ ERROR DE BD: {e}")

# --- FUNCIÓN PARA BORRAR MENSAJES ---
async def borrar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE, clave):
    msg_id = context.user_data.get(clave)
    if msg_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
        except:
            pass

# --- COMANDO /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    try:
        await update.message.delete()
    except:
        pass 

    # Borrar mensaje de bienvenida anterior si existe
    await borrar_mensaje(update, context, 'msg_bienvenida')

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    
    if resultado and resultado[0] is not None:
        cur.close()
        conn.close()
        msg = await update.message.reply_text(
            "🌑 *Regreso detectado.*\n\nEl Sistema ya tiene tu registro. Usa /perfil para ver tu ficha.",
            parse_mode="Markdown"
        )
        context.user_data['msg_bienvenida'] = msg.message_id
        return

    context.user_data['maestro_id'] = None
    if context.args:
        try:
            context.user_data['maestro_id'] = int(context.args[0])
        except ValueError:
            pass

    context.user_data['estado'] = 'esperando_nombre'

    msg = await update.message.reply_text(
        "🌑 *El Sistema te ha detectado.*\n\n"
        "Antes de cruzar el primer portal, necesito tu designación.\n"
        "**¿Cuál es tu nombre, Sujeto?**",
        parse_mode="Markdown"
    )
    context.user_data['msg_bienvenida'] = msg.message_id
    cur.close()
    conn.close()

# --- MANEJADOR DE MENSAJES (Limpieza estricta) ---
async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    estado = context.user_data.get('estado')

    if estado == 'esperando_nombre':
        if not update.message.text:
            try:
                await update.message.delete() 
            except:
                pass
            # Borrar el mensaje de error anterior si existe
            await borrar_mensaje(update, context, 'msg_error')
            msg = await update.message.reply_text("⚠️ El Sistema no procesa imágenes ni audios. **Escribe tu nombre con letras.**", parse_mode="Markdown")
            context.user_data['msg_error'] = msg.message_id
            return
            
        nombre_elegido = update.message.text
        
        try:
            await update.message.delete()
        except:
            pass
        
        # Borrar mensajes de error y bienvenida para limpiar el chat
        await borrar_mensaje(update, context, 'msg_error')
        await borrar_mensaje(update, context, 'msg_bienvenida')

        context.user_data['nombre_temp'] = nombre_elegido
        context.user_data['estado'] = 'esperando_sexo'
        
        keyboard = [
            [InlineKeyboardButton("♂️ Masculino", callback_data='sexo_m')],
            [InlineKeyboardButton("♀️ Femenino", callback_data='sexo_f')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = await update.message.reply_text(
            f"Registro aceptado, **{nombre_elegido}**.\n\n"
            "El Sistema necesita conocer tu estructura biológica.\n"
            "**Selecciona tu sexo:**",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        context.user_data['msg_pregunta_sexo'] = msg.message_id
        return

    if estado in ['esperando_sexo', 'esperando_clase']:
        try:
            await update.message.delete()
        except:
            pass
        return

# --- RECIBIR EL SEXO ---
async def boton_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if context.user_data.get('estado') != 'esperando_sexo':
        return
        
    sexo_elegido = "M" if query.data == 'sexo_m' else "F"
    context.user_data['sexo_temp'] = sexo_elegido
    context.user_data['estado'] = 'esperando_clase'
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Ejecutor/a", callback_data='clase_ejecutor')],
        [InlineKeyboardButton("🔮 Mago/a", callback_data='clase_mago')],
        [InlineKeyboardButton("🛡️ Guardián/na", callback_data='clase_guardian')],
        [InlineKeyboardButton("🗡️ Asesino/a", callback_data='clase_asesino')],
        [InlineKeyboardButton("🏹 Arquero/a", callback_data='clase_arquero')],
        [InlineKeyboardButton("✨ Clérigo/a", callback_data='clase_clerigo')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Sexo registrado.\n\n"
        "Ahora el Sistema necesita saber qué camino tomarás. **Elige tu clase:**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# --- RECIBIR LA CLASE (Y GENERAR FOTO) ---
async def boton_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    
    if context.user_data.get('estado') != 'esperando_clase':
        return

    user_id = update.effective_user.id
    clase_base = query.data.replace('clase_', '') 
    nombre_elegido = context.user_data.get('nombre_temp', 'Desconocido')
    sexo_elegido = context.user_data.get('sexo_temp', 'M')
    maestro_id = context.user_data.get('maestro_id', None)
    
    nombres_clases = {
        'ejecutor': {'M': 'Ejecutor', 'F': 'Ejecutora'},
        'mago': {'M': 'Mago', 'F': 'Maga'},
        'guardian': {'M': 'Guardián', 'F': 'Guardiana'},
        'asesino': {'M': 'Asesino', 'F': 'Asesina'},
        'arquero': {'M': 'Arquero', 'F': 'Arquera'},
        'clerigo': {'M': 'Clérigo', 'F': 'Clériga'}
    }
    clase_final = nombres_clases.get(clase_base, nombres_clases['ejecutor'])[sexo_elegido]
    
    stats = {
        'ejecutor': {'vida': 120, 'atq': 25, 'mov': 15, 'intel': 5,  'res': 15, 'tac': 15},
        'mago':     {'vida': 80,  'atq': 5,  'mov': 10, 'intel': 25, 'res': 10, 'tac': 25},
        'guardian': {'vida': 180, 'atq': 10, 'mov': 5,  'intel': 10, 'res': 25, 'tac': 25},
        'asesino':  {'vida': 90,  'atq': 20, 'mov': 25, 'intel': 5,  'res': 5,  'tac': 20},
        'arquero':  {'vida': 100, 'atq': 15, 'mov': 20, 'intel': 10, 'res': 10, 'tac': 20},
        'clerigo':  {'vida': 110, 'atq': 10, 'mov': 10, 'intel': 20, 'res': 15, 'tac': 20}
    }
    s = stats.get(clase_base, stats['ejecutor'])
    
    # --- GENERAR FOTO CON POLLINATIONS ---
    prompt = f"A {sexo_elegido} {clase_final} in a dark futuristic RPG, glowing neon portal, epic fantasy style, portrait"
    prompt_url = urllib.parse.quote(prompt)
    foto_url = f"https://image.pollinations.ai/prompt/{prompt_url}?width=512&height=512&nologo=true"
    
    # --- HISTORIA SIMULADA (Luego la haremos con Groq) ---
    historia = f"El día que el cielo se tiñó de violeta, {nombre_elegido} despertó con el poder de un {clase_final}. Ahora, el Sistema te observa."

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (id_telegram, nombre, clase, sexo, rango, maestro_id, historia, foto_url, vida, atq, mov, intel, res, tac)
        VALUES (%s, %s, %s, %s, 'E', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_telegram) DO UPDATE SET
        nombre = EXCLUDED.nombre, clase = EXCLUDED.clase, sexo = EXCLUDED.sexo, rango = 'E', maestro_id = EXCLUDED.maestro_id, historia = EXCLUDED.historia, foto_url = EXCLUDED.foto_url, vida = EXCLUDED.vida, atq = EXCLUDED.atq, mov = EXCLUDED.mov, intel = EXCLUDED.intel, res = EXCLUDED.res, tac = EXCLUDED.tac
    """, (user_id, nombre_elegido, clase_final, sexo_elegido, maestro_id, historia, foto_url, s['vida'], s['atq'], s['mov'], s['intel'], s['res'], s['tac']))
    conn.commit()
    cur.close()
    conn.close()
    
    icono_sexo = "♂️" if sexo_elegido == 'M' else "♀️"
    
    texto_final = (
        f"✅ *REGISTRO COMPLETADO*\n\n"
        f"👤 Sujeto: **{nombre_elegido}**\n"
        f"⚔️ Clase: **{clase_final}**\n"
        f"{icono_sexo} Sexo: **{'Masculino' if sexo_elegido == 'M' else 'Femenino'}**\n"
        f"🏅 Rango: **E** | 📊 Nivel: **1**\n\n"
        f"📖 *Historia:* {historia}\n\n"
        f"❤️ Vida: {s['vida']} | ⚔️ ATQ: {s['atq']} | 💨 MOV: {s['mov']}\n"
        f"🧠 INT: {s['intel']} | 🛡️ RES: {s['res']} | 🎯 TAC: {s['tac']}\n\n"
    )
    
    if maestro_id:
        texto_final += f"👑 *Has sido registrado bajo la tutela de un Maestro.*\n\n"
        
    texto_final += "*El Sistema te observa. Prepárate para el primer portal.*"
    
    # Borramos el mensaje de los botones (que ya no sirve)
    try:
        await query.message.delete()
    except:
        pass

    # Enviamos la foto con el texto
    await context.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=foto_url, 
        caption=texto_final, 
        parse_mode="Markdown"
    )
    
    context.user_data['estado'] = 'en_menu'

# --- COMANDO /perfil ---
async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Borrar el comando /perfil del chat
    try:
        await update.message.delete()
    except:
        pass

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT nombre, clase, sexo, rango, nivel, vida, atq, mov, intel, res, tac, historia, foto_url FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        nombre, clase, sexo, rango, nivel, vida, atq, mov, intel, res, tac, historia, foto_url = user
        icono_sexo = "♂️" if sexo == 'M' else "♀️"
        
        texto = (
            f"🌑 *FICHA DEL SISTEMA*\n\n"
            f"👤 Sujeto: **{nombre}**\n"
            f"⚔️ Clase: **{clase}**\n"
            f"{icono_sexo} Sexo: **{'Masculino' if sexo == 'M' else 'Femenino'}**\n"
            f"🏅 Rango: **{rango}** | 📊 Nivel: **{nivel}**\n\n"
            f"📖 *Historia:* {historia}\n\n"
            f"❤️ Vida: {vida} | ⚔️ ATQ: {atq} | 💨 MOV: {mov}\n"
            f"🧠 INT: {intel} | 🛡️ RES: {res} | 🎯 TAC: {tac}\n"
        )
        
        await context.bot.send_photo(
            chat_id=update.effective_chat.id, 
            photo=foto_url, 
            caption=texto, 
            parse_mode="Markdown"
        )
    else:
        msg = await update.message.reply_text("⚠️ El Sistema no te reconoce. Escribe /start primero.")
        # Se podría programar un auto-borrado para este mensaje luego

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
    app.add_handler(CommandHandler("perfil", perfil)) # NUEVO COMANDO
    
    app.add_handler(MessageHandler(~filters.COMMAND, manejar_mensajes))
    
    app.add_handler(CallbackQueryHandler(boton_sexo, pattern='^sexo_'))
    app.add_handler(CallbackQueryHandler(boton_clase, pattern='^clase_'))
    
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
