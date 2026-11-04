import os
import threading
import psycopg2
import urllib.parse
import random
import asyncio
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
        cur.execute("DROP TABLE IF EXISTS usuarios;") # Limpieza de prueba
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
                vida_max INT DEFAULT 100,
                atq INT DEFAULT 10,
                mov INT DEFAULT 10,
                intel INT DEFAULT 10,
                res INT DEFAULT 10,
                tac INT DEFAULT 10,
                en_combate BOOLEAN DEFAULT FALSE,
                monstruo_hp INT DEFAULT 0
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Base de datos lista.")
    except Exception as e:
        print(f"❌ ERROR DE BD: {e}")

# --- FUNCIÓN PARA LIMPIAR CHAT ---
async def limpiar_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Borrar mensajes guardados en memoria
    for clave in ['msg_bienvenida', 'msg_error', 'msg_perfil', 'msg_combate']:
        msg_id = context.user_data.get(clave)
        if msg_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except:
                pass
    # Borrar el mensaje que envió el usuario (si existe)
    if update.message:
        try:
            await update.message.delete()
        except:
            pass

# --- COMANDO /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    
    if resultado and resultado[0] is not None:
        cur.close()
        conn.close()
        msg = await update.message.reply_text(
            "🌑 *Regreso detectado.*\n\nUsa /perfil para ver tu ficha o /portal para entrar a una mazmorra.",
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

# --- MANEJADOR DE MENSAJES (Limpieza y Frases Épicas) ---
async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    estado = context.user_data.get('estado')

    if estado == 'esperando_nombre':
        if not update.message.text:
            try:
                await update.message.delete() 
            except:
                pass
            msg = await update.message.reply_text("⚠️ El Sistema no procesa imágenes ni audios. **Escribe tu nombre con letras.**", parse_mode="Markdown")
            context.user_data['msg_error'] = msg.message_id
            return
            
        nombre_elegido = update.message.text
        try:
            await update.message.delete()
        except:
            pass
        
        await limpiar_chat(update, context)

        context.user_data['nombre_temp'] = nombre_elegido
        context.user_data['estado'] = 'esperando_sexo'
        
        keyboard = [
            [InlineKeyboardButton("♂️ Masculino", callback_data='sexo_m')],
            [InlineKeyboardButton("♀️ Femenino", callback_data='sexo_f')]
        ]
        msg = await update.message.reply_text(
            f"Registro aceptado, **{nombre_elegido}**.\n\n"
            "Selecciona tu sexo:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        context.user_data['msg_pregunta_sexo'] = msg.message_id
        return

    # Si el jugador está en combate y escribe texto, lo guardamos como "Frase Épica"
    if estado == 'en_combate' and update.message.text:
        contexto_frase = update.message.text
        context.user_data['frase_epica'] = contexto_frase
        try:
            await update.message.delete() # Borramos el mensaje para no ensuciar
        except:
            pass
        return

# --- BOTONES DE SEXO Y CLASE ---
async def boton_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if context.user_data.get('estado') != 'esperando_sexo': return
        
    context.user_data['sexo_temp'] = "M" if query.data == 'sexo_m' else "F"
    context.user_data['estado'] = 'esperando_clase'
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Ejecutor/a", callback_data='clase_ejecutor')],
        [InlineKeyboardButton("🔮 Mago/a", callback_data='clase_mago')],
        [InlineKeyboardButton("🛡️ Guardián/na", callback_data='clase_guardian')],
        [InlineKeyboardButton("🗡️ Asesino/a", callback_data='clase_asesino')],
        [InlineKeyboardButton("🏹 Arquero/a", callback_data='clase_arquero')],
        [InlineKeyboardButton("✨ Clérigo/a", callback_data='clase_clerigo')]
    ]
    await query.edit_message_text(
        "Sexo registrado.\n\n**Elige tu clase:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def boton_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    if context.user_data.get('estado') != 'esperando_clase': return

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
    
    # --- FOTO SIN MARCA DE AGUA (Usando el modelo Flux) ---
    prompt = f"A {sexo_elegido} {clase_final} in a dark futuristic RPG, glowing neon portal, epic fantasy style, portrait"
    prompt_url = urllib.parse.quote(prompt)
    # El parámetro model=flux y nologo=true ayudan a quitar la marca
    foto_url = f"https://image.pollinations.ai/prompt/{prompt_url}?width=512&height=512&nologo=true&model=flux"
    
    historia = f"El día que el cielo se tiñó de violeta, {nombre_elegido} despertó con el poder de un {clase_final}. Ahora, el Sistema te observa."

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (id_telegram, nombre, clase, sexo, rango, maestro_id, historia, foto_url, vida, vida_max, atq, mov, intel, res, tac)
        VALUES (%s, %s, %s, %s, 'E', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_telegram) DO UPDATE SET
        nombre = EXCLUDED.nombre, clase = EXCLUDED.clase, sexo = EXCLUDED.sexo, rango = 'E', maestro_id = EXCLUDED.maestro_id, historia = EXCLUDED.historia, foto_url = EXCLUDED.foto_url, vida = EXCLUDED.vida, vida_max = EXCLUDED.vida_max, atq = EXCLUDED.atq, mov = EXCLUDED.mov, intel = EXCLUDED.intel, res = EXCLUDED.res, tac = EXCLUDED.tac
    """, (user_id, nombre_elegido, clase_final, sexo_elegido, maestro_id, historia, foto_url, s['vida'], s['vida'], s['atq'], s['mov'], s['intel'], s['res'], s['tac']))
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
        f"*El Sistema te observa. Escribe /portal para buscar tu primera mazmorra.*"
    )
    
    try: await query.message.delete()
    except: pass

    msg = await context.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=foto_url, 
        caption=texto_final, 
        parse_mode="Markdown"
    )
    context.user_data['msg_perfil'] = msg.message_id
    context.user_data['estado'] = 'en_menu'

# --- COMANDO /perfil ---
async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context) # Borra la foto anterior y mensajes

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT nombre, clase, sexo, rango, nivel, vida, vida_max, atq, mov, intel, res, tac, historia, foto_url FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        nombre, clase, sexo, rango, nivel, vida, vida_max, atq, mov, intel, res, tac, historia, foto_url = user
        icono_sexo = "♂️" if sexo == 'M' else "♀️"
        
        texto = (
            f"🌑 *FICHA DEL SISTEMA*\n\n"
            f"👤 Sujeto: **{nombre}**\n"
            f"⚔️ Clase: **{clase}**\n"
            f"{icono_sexo} Sexo: **{'Masculino' if sexo == 'M' else 'Femenino'}**\n"
            f"🏅 Rango: **{rango}** | 📊 Nivel: **{nivel}**\n\n"
            f"📖 *Historia:* {historia}\n\n"
            f"❤️ Vida: {vida}/{vida_max} | ⚔️ ATQ: {atq} | 💨 MOV: {mov}\n"
            f"🧠 INT: {intel} | 🛡️ RES: {res} | 🎯 TAC: {tac}\n"
        )
        
        msg = await context.bot.send_photo(
            chat_id=update.effective_chat.id, 
            photo=foto_url, 
            caption=texto, 
            parse_mode="Markdown"
        )
        context.user_data['msg_perfil'] = msg.message_id

# --- COMANDO /PORTAL (EL COMBATE) ---
async def portal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT clase, vida FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    
    if not user:
        cur.close()
        conn.close()
        msg = await update.message.reply_text("⚠️ El Sistema no te reconoce. Escribe /start.")
        context.user_data['msg_error'] = msg.message_id
        return

    # Iniciamos el combate contra Karu
    hp_monstruo = 100
    cur.execute("UPDATE usuarios SET en_combate = TRUE, monstruo_hp = %s WHERE id_telegram = %s", (hp_monstruo, user_id))
    conn.commit()
    cur.close()
    conn.close()

    context.user_data['estado'] = 'en_combate'
    context.user_data['monstruo_nombre'] = "Karu, el Registrado"
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar')],
        [InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')],
        [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad')]
    ]
    
    texto = (
        f"🩸 *PORTAL ABIERTO*\n\n"
        f"Una figura se arrastra desde las sombras...\n"
        f"Es **{context.user_data['monstruo_nombre']}** (Rango E).\n\n"
        f"❤️ Vida del Monstruo: {hp_monstruo}/100\n\n"
        f"*El Sistema está calculando tu destino...*\n"
        f"Puedes tocar un botón o escribir tu frase épica en el chat."
    )
    
    msg = await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    context.user_data['msg_combate'] = msg.message_id

# --- LÓGICA DE LOS BOTONES DE COMBATE ---
async def boton_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if context.user_data.get('estado') != 'en_combate':
        return

    accion = query.data.replace('combate_', '')
    user_id = update.effective_user.id
    frase = context.user_data.get('frase_epica', '')
    context.user_data['frase_epica'] = '' # Limpiar para el siguiente turno

    # Efecto de "Cargando..."
    await query.edit_message_text("⏳ *El Sistema está calculando tu destino...*", parse_mode="Markdown")
    await asyncio.sleep(3) # Tensión épica

    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT nombre, clase, vida, atq, monstruo_hp FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    nombre, clase, vida, atq, hp_monstruo = user

    # Cálculos básicos (Python decide)
    if accion == 'atacar':
        dano = atq + random.randint(1, 10)
    elif accion == 'habilidad':
        dano = (atq * 1.5) + random.randint(5, 15)
    elif accion == 'esquivar':
        dano = 0 # Esquivar no hace daño

    hp_monstruo -= int(dano)
    if hp_monstruo < 0: hp_monstruo = 0

    # El monstruo contraataca (si sigue vivo)
    dano_recibido = 0
    if hp_monstruo > 0:
        dano_recibido = random.randint(5, 15)
        vida -= dano_recibido
        if vida < 0: vida = 0

    cur.execute("UPDATE usuarios SET vida = %s, monstruo_hp = %s WHERE id_telegram = %s", (vida, hp_monstruo, user_id))
    conn.commit()
    cur.close()
    conn.close()

    # NARRACIÓN (Aquí iría Groq, por ahora simulado)
    narracion = f"El Sujeto {nombre} se lanza hacia el monstruo. "
    if frase:
        narracion = f"*\"{frase}\"*\n\n" + narracion
    if dano > 0:
        narracion += f"El acero corta la carne podrida. **{dano} de daño** infligido. "
    if dano_recibido > 0:
        narracion += f"Pero la criatura responde con un zarpazo. Sangre brota de tu hombro. **{dano_recibido} de daño recibido**."

    # Si el monstruo muere
    if hp_monstruo <= 0:
        narracion += f"\n\n💀 **{context.user_data['monstruo_nombre']} ha sido erradicado.**"
        narracion += f"\n\n*El Sistema registra tu victoria. Pronto subirás de nivel.*"
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data='volver_menu')]]
        await query.edit_message_text(narracion, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        # Aquí iría la lógica de EXP y drops
        
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET en_combate = FALSE WHERE id_telegram = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        return

    # Si el jugador muere
    if vida <= 0:
        narracion += f"\n\n☠️ **Has caído.** El Sistema te ha borrado del registro."
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data='volver_menu')]]
        await query.edit_message_text(narracion, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("UPDATE usuarios SET en_combate = FALSE WHERE id_telegram = %s", (user_id,))
        conn.commit()
        cur.close()
        conn.close()
        return

    # Siguiente turno
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar')],
        [InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')],
        [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad')]
    ]
    texto_turno = (
        f"{narracion}\n\n"
        f"❤️ Tu Vida: {vida}\n"
        f"🩸 Vida de Karu: {hp_monstruo}/100\n\n"
        f"*¿Cuál es tu siguiente movimiento?*"
    )
    await query.edit_message_text(texto_turno, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- BOTÓN VOLVER AL MENÚ ---
async def volver_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['estado'] = 'en_menu'
    await query.edit_message_text("🌑 *Has vuelto al Refugio. El Sistema espera.*\nUsa /perfil o /portal.", parse_mode="Markdown")

# --- SERVIDOR WEB ---
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
    app.add_handler(CommandHandler("perfil", perfil))
    app.add_handler(CommandHandler("portal", portal))
    
    app.add_handler(MessageHandler(~filters.COMMAND, manejar_mensajes))
    
    app.add_handler(CallbackQueryHandler(boton_sexo, pattern='^sexo_'))
    app.add_handler(CallbackQueryHandler(boton_clase, pattern='^clase_'))
    app.add_handler(CallbackQueryHandler(boton_combate, pattern='^combate_'))
    app.add_handler(CallbackQueryHandler(volver_menu, pattern='^volver_menu$'))
    
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
