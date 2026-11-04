import os
import threading
import psycopg2
import urllib.parse
import random
import asyncio
import datetime
import aiohttp
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))
ID_CREADOR = 6985217869

GRUPO_A = ["Ejecutor", "Asesino", "Arquero"]
GRUPO_B = ["Mago", "Guardián", "Clérigo"]

# --- CATÁLOGO DE ARMAS (Tiers: 5, 10, 15) ---
ARMAS = {
    "ejecutor": [
        {"nombre": "Espada Corta", "tier": 1, "stat": 5, "precio": 15},
        {"nombre": "Filo del Eclipse", "tier": 2, "stat": 10, "precio": 40},
        {"nombre": "Mandoble del Vacío", "tier": 3, "stat": 15, "precio": 100}
    ],
    "mago": [
        {"nombre": "Bastón Astillado", "tier": 1, "stat": 5, "precio": 15},
        {"nombre": "Cetro del Registro", "tier": 2, "stat": 10, "precio": 40},
        {"nombre": "Vara de la Creación", "tier": 3, "stat": 15, "precio": 100}
    ],
    "guardian": [
        {"nombre": "Escudo de Madera", "tier": 1, "stat": 5, "precio": 15},
        {"nombre": "Muro de Obsidiana", "tier": 2, "stat": 10, "precio": 40},
        {"nombre": "Baluarte del Sistema", "tier": 3, "stat": 15, "precio": 100}
    ],
    "asesino": [
        {"nombre": "Daga de Óxido", "tier": 1, "stat": 5, "precio": 15},
        {"nombre": "Colmillos Gemelos", "tier": 2, "stat": 10, "precio": 40},
        {"nombre": "Filos del Silencio", "tier": 3, "stat": 15, "precio": 100}
    ],
    "arquero": [
        {"nombre": "Arco Corto", "tier": 1, "stat": 5, "precio": 15},
        {"nombre": "Arco de Energía", "tier": 2, "stat": 10, "precio": 40},
        {"nombre": "Ballesta del Eclipse", "tier": 3, "stat": 15, "precio": 100}
    ],
    "clerigo": [
        {"nombre": "Símbolo Menor", "tier": 1, "stat": 5, "precio": 15},
        {"nombre": "Reliquia del Alba", "tier": 2, "stat": 10, "precio": 40},
        {"nombre": "Cetro de Fe", "tier": 3, "stat": 15, "precio": 100}
    ]
}

MONSTRUOS = {
    "E": [
        {"nombre": "Karu, el Registrado", "hp": 100, "atk": 25, "grupo": "A", "exp": 100},
        {"nombre": "Vex, Sujeto 07", "hp": 120, "atk": 28, "grupo": "B", "exp": 100},
        {"nombre": "Kael, Eco del Portal", "hp": 90, "atk": 30, "grupo": "A", "exp": 100},
        {"nombre": "Zeth, Larva del Umbral", "hp": 80, "atk": 22, "grupo": "B", "exp": 100},
        {"nombre": "Rakan, Colmillo Rojo", "hp": 130, "atk": 32, "grupo": "A", "exp": 100}
    ],
    "JEFE_E": {"nombre": "Guardián del Umbral", "hp": 300, "atk": 40, "grupo": "C", "exp": 0}
}

def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS usuarios;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_telegram BIGINT PRIMARY KEY, nombre VARCHAR(50), clase VARCHAR(20), sexo VARCHAR(10),
                rango VARCHAR(5) DEFAULT 'E', historia TEXT, nivel INT DEFAULT 1, exp INT DEFAULT 0,
                vida INT DEFAULT 100, vida_max INT DEFAULT 100, mana INT DEFAULT 50, mana_max INT DEFAULT 50,
                atq INT DEFAULT 10, mov INT DEFAULT 10, intel INT DEFAULT 10, res INT DEFAULT 10, tac INT DEFAULT 10,
                energia INT DEFAULT 5, estrellas INT DEFAULT 0, en_combate BOOLEAN DEFAULT FALSE,
                monstruo_hp INT DEFAULT 0, monstruo_nombre VARCHAR(100) DEFAULT '', bloqueo_hasta TIMESTAMP,
                arma_equipada VARCHAR(50) DEFAULT 'Ninguna'
            )
        """)
        cur.execute("DROP TABLE IF EXISTS inventario;")
        cur.execute("CREATE TABLE IF NOT EXISTS inventario (id_telegram BIGINT, item VARCHAR(50), tipo VARCHAR(20), stat_bonus INT, clase_original VARCHAR(20), cantidad INT DEFAULT 1, PRIMARY KEY (id_telegram, item));")
        cur.execute("DROP TABLE IF EXISTS derrotados;")
        cur.execute("CREATE TABLE IF NOT EXISTS derrotados (id_telegram BIGINT, nombre VARCHAR(100), PRIMARY KEY (id_telegram, nombre));")
        cur.execute("DROP TABLE IF EXISTS bestiario_imagenes;")
        cur.execute("CREATE TABLE IF NOT EXISTS bestiario_imagenes (nombre VARCHAR(100) PRIMARY KEY, imagen BYTEA);")
        conn.commit(); cur.close(); conn.close()
        print("✅ Base de datos lista.")
    except Exception as e: print(f"❌ ERROR BD: {e}")

async def narrar_con_ia(prompt_sistema, contexto):
    url = "https://text.pollinations.ai/openai"
    payload = {"model": "openai", "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": contexto}], "max_tokens": 100}
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content'].strip().replace('*', '').replace('_', '')
                return None
    except: return None

def texto_respaldo(tipo, nombre, monstruo=""):
    if tipo == "historia":
        return f"El día que el cielo se tiñó de violeta, {nombre} despertó con un poder prohibido. El Sistema lo ha registrado. Ahora debe sobrevivir."
    elif tipo == "combate":
        opciones = [
            f"El Sujeto {nombre} ataca con fiereza. El monstruo {monstruo} responde con un zarpazo que hace sangrar el aire.",
            f"El acero choca contra la piel de {monstruo}. {nombre} siente el dolor, pero no se detiene.",
            f"Un golpe brutal. {monstruo} ruge y {nombre} retrocede. El Sistema observa en silencio."
        ]
        return random.choice(opciones)
    return ""

async def generar_imagen_sistema(prompt, es_monstruo=False):
    if es_monstruo:
        prompt_mejorado = f"epic fantasy monster concept art, {prompt}, glowing eyes, cinematic lighting, masterpiece, detailed"
    else:
        prompt_mejorado = f"anime style portrait of a {prompt}, beautiful detailed eyes, dark fantasy aesthetic, glowing neon aura, masterpiece, highly detailed"
    
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt_mejorado)}?width=512&height=512&nologo=false&model=turbo"
    try:
        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200: return await response.read()
                return None
    except: return None

def calcular_dano_faccion(clase_jugador, grupo_monstruo):
    if grupo_monstruo == "C": return 1.0 
    en_grupo_a = clase_jugador in GRUPO_A or clase_jugador.replace("a", "").capitalize() in GRUPO_A
    if grupo_monstruo == "A": return 1.5 if not en_grupo_a else 0.5
    else: return 1.5 if en_grupo_a else 0.5

def calcular_multiplicador_exp(clase_jugador, grupo_monstruo):
    dano_mult = calcular_dano_faccion(clase_jugador, grupo_monstruo)
    if dano_mult == 1.5: return 1.0
    elif dano_mult == 0.5: return 2.0
    else: return 1.5

async def limpiar_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for clave in ['msg_bienvenida', 'msg_error', 'msg_perfil', 'msg_combate', 'msg_tienda', 'msg_creador', 'msg_pregunta_sexo', 'msg_pregunta_clase', 'msg_transicion']:
        msg_id = context.user_data.get(clave)
        if msg_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except: pass
    if update.message:
        try: await update.message.delete()
        except: pass

def obtener_menu_fijo():
    return ReplyKeyboardMarkup([[KeyboardButton("👤 Perfil"), KeyboardButton("🩸 Portal")], [KeyboardButton("🛒 Tienda"), KeyboardButton("🎒 Inventario")]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    if resultado and resultado[0] is not None:
        cur.close(); conn.close()
        msg = await update.message.reply_text("🌑 *Regreso detectado.*", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
        context.user_data['msg_bienvenida'] = msg.message_id
        return
    context.user_data['estado'] = 'esperando_nombre'
    msg = await update.message.reply_text("🌑 *El Sistema te ha detectado.*\n\n**¿Cuál es tu nombre, Sujeto?**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    context.user_data['msg_bienvenida'] = msg.message_id
    cur.close(); conn.close()

async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    estado = context.user_data.get('estado')
    if texto == "👤 Perfil": await perfil(update, context); return
    elif texto == "🩸 Portal": await portal(update, context); return
    elif texto == "🛒 Tienda": await tienda(update, context); return
    elif texto == "🎒 Inventario": await inventario(update, context); return

    if estado == 'esperando_nombre':
        if not texto:
            try: await update.message.delete() 
            except: pass
            msg = await update.message.reply_text("⚠️ Escribe tu nombre con letras.", parse_mode="Markdown")
            context.user_data['msg_error'] = msg.message_id
            return
        try: await update.message.delete()
        except: pass
        await limpiar_chat(update, context)
        context.user_data['nombre_temp'] = texto
        context.user_data['estado'] = 'esperando_sexo'
        keyboard = [[InlineKeyboardButton("♂️ Masculino", callback_data='sexo_m')], [InlineKeyboardButton("♀️ Femenino", callback_data='sexo_f')]]
        msg = await update.message.reply_text(f"Registro aceptado, **{texto}**.\n\nSelecciona tu sexo:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data['msg_pregunta_sexo'] = msg.message_id
        return

    if estado == 'regalar_estrellas':
        try:
            partes = texto.split()
            target_id, cantidad = int(partes[0]), int(partes[1])
            conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
            cur.execute("UPDATE usuarios SET estrellas = estrellas + %s WHERE id_telegram = %s", (cantidad, target_id))
            conn.commit(); cur.close(); conn.close()
            await update.message.reply_text(f"⭐ Has regalado {cantidad} Estrellas al ID {target_id}.")
        except: await update.message.reply_text("❌ Formato incorrecto.", parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'
        return

    if estado == 'en_combate' and texto:
        context.user_data['frase_epica'] = texto
        try: await update.message.delete()
        except: pass
        return

async def boton_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'esperando_sexo': return
    context.user_data['sexo_temp'] = "M" if query.data == 'sexo_m' else "F"
    context.user_data['estado'] = 'esperando_clase'
    # --- CLASES 3 Y 3 ---
    keyboard = [
        [InlineKeyboardButton("⚔️ Ejecutor", callback_data='clase_ejecutor'), InlineKeyboardButton("🔮 Mago", callback_data='clase_mago'), InlineKeyboardButton("🛡️ Guardián", callback_data='clase_guardian')],
        [InlineKeyboardButton("🗡️ Asesino", callback_data='clase_asesino'), InlineKeyboardButton("🏹 Arquero", callback_data='clase_arquero'), InlineKeyboardButton("✨ Clérigo", callback_data='clase_clerigo')]
    ]
    try: await query.edit_message_text("Sexo registrado.\n\n**Elige tu clase:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except: await context.bot.send_message(chat_id=update.effective_chat.id, text="Sexo registrado.\n\n**Elige tu clase:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def boton_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'esperando_clase': return
    user_id = update.effective_user.id
    clase_base = query.data.replace('clase_', '') 
    nombre_elegido = context.user_data.get('nombre_temp', 'Desconocido')
    sexo_elegido = context.user_data.get('sexo_temp', 'M')
    
    nombres_clases = {'ejecutor': {'M': 'Ejecutor', 'F': 'Ejecutora'}, 'mago': {'M': 'Mago', 'F': 'Maga'}, 'guardian': {'M': 'Guardián', 'F': 'Guardiana'}, 'asesino': {'M': 'Asesino', 'F': 'Asesina'}, 'arquero': {'M': 'Arquero', 'F': 'Arquera'}, 'clerigo': {'M': 'Clérigo', 'F': 'Clériga'}}
    clase_final = nombres_clases.get(clase_base, nombres_clases['ejecutor'])[sexo_elegido]
    stats = {'ejecutor': {'vida': 120, 'mana': 30, 'atq': 25, 'mov': 15, 'intel': 5,  'res': 15, 'tac': 15}, 'mago': {'vida': 80,  'mana': 100,'atq': 5,  'mov': 10, 'intel': 25, 'res': 10, 'tac': 25}, 'guardian': {'vida': 180, 'mana': 40, 'atq': 10, 'mov': 5,  'intel': 10, 'res': 25, 'tac': 25}, 'asesino': {'vida': 90,  'mana': 50, 'atq': 20, 'mov': 25, 'intel': 5,  'res': 5,  'tac': 20}, 'arquero': {'vida': 100, 'mana': 60, 'atq': 15, 'mov': 20, 'intel': 10, 'res': 10, 'tac': 20}, 'clerigo': {'vida': 110, 'mana': 80, 'atq': 10, 'mov': 10, 'intel': 20, 'res': 15, 'tac': 20}}
    s = stats.get(clase_base, stats['ejecutor'])
    
    try: await query.message.delete()
    except: pass

    icono_sexo = "♂️" if sexo_elegido == 'M' else "♀️"
    texto_final = (f"✅ *REGISTRO COMPLETADO*\n\n👤 Sujeto: **{nombre_elegido}**\n⚔️ Clase: **{clase_final}**\n{icono_sexo} Sexo: **{'Masculino' if sexo_elegido == 'M' else 'Femenino'}**\n"
        f"🏅 Rango: **E** | 📊 Nivel: **1**\n\n❤️ Vida: {s['vida']} | 🔮 Maná: {s['mana']}\n⚔️ ATQ: {s['atq']} | 💨 MOV: {s['mov']}\n🧠 INT: {s['intel']} | 🛡️ RES: {s['res']} | 🎯 TAC: {s['tac']}\n\n🌑 *El Sistema te da la bienvenida.*")
    msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=texto_final, parse_mode="Markdown")
    context.user_data['msg_perfil'] = msg.message_id
    await context.bot.send_message(chat_id=update.effective_chat.id, text="​", reply_markup=obtener_menu_fijo())
    context.user_data['estado'] = 'en_menu'

    async def guardar_y_generar():
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        msg_trans = await context.bot.send_message(chat_id=update.effective_chat.id, text="🔮 *El Oráculo de Pollinations te está escaneando...*", parse_mode="Markdown")
        
        prompt_historia = f"Eres 'El Sistema'. Escribe una historia de origen épica y oscura (máximo 3 líneas) para un personaje llamado {nombre_elegido}, que es un {clase_final} en un mundo post-apocalíptico llamado 'El Eclipse'."
        historia_ia = await narrar_con_ia(prompt_historia, f"Genera la historia para {nombre_elegido}.")
        historia_final = historia_ia if historia_ia else texto_respaldo("historia", nombre_elegido)
        
        cur.execute("INSERT INTO usuarios (id_telegram, nombre, clase, sexo, rango, historia, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, estrellas) VALUES (%s, %s, %s, %s, 'E', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0) ON CONFLICT (id_telegram) DO NOTHING", 
                    (user_id, nombre_elegido, clase_final, sexo_elegido, historia_final, s['vida'], s['vida'], s['mana'], s['mana'], s['atq'], s['mov'], s['intel'], s['res'], s['tac']))
        conn.commit(); cur.close(); conn.close()

        genero_ingles = "man" if sexo_elegido == 'M' else "woman"
        detalles_clase = {'ejecutor': "massive greatsword, dark heavy armor", 'mago': "floating crystal staff, dark robes", 'guardian': "massive spiked armor, giant shield", 'asesino': "dark hooded cloak, dual daggers", 'arquero': "glowing energy bow", 'clerigo': "ornate dark robes, glowing holy symbol"}
        detalle = detalles_clase.get(clase_base, "dark fantasy armor")
        prompt = f"{genero_ingles} {clase_final}, {detalle}"
        
        image_bytes = await generar_imagen_sistema(prompt, es_monstruo=False)
        
        texto_foto = (f"🌑 *REGISTRO VISUAL - FACCIÓN POLLINATIONS*\n\n👤 Sujeto: **{nombre_elegido}**\n\n📖 *Historia:*\n{historia_final}\n\n⚠️ *Marca:* El sello es la firma del Consejo.")
        
        if image_bytes:
            try: await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=texto_foto, parse_mode="Markdown")
            except: pass
        
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_trans.message_id)
        except: pass

    asyncio.create_task(guardar_y_generar())

async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context) 
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, historia, energia, estrellas, arma_equipada FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone(); cur.close(); conn.close()
    if user:
        (nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, historia, energia, estrellas, arma_equipada) = user
        icono_sexo = "♂️" if sexo == 'M' else "♀️"
        exp_necesaria = nivel * 100
        texto = (f"🌑 *FICHA DEL SISTEMA*\n\n👤 Sujeto: **{nombre}**\n⚔️ Clase: **{clase}**\n{icono_sexo} Sexo: **{'Masculino' if sexo == 'M' else 'Femenino'}**\n"
            f"🏅 Rango: **{rango}** | 📊 Nivel: **{nivel}** (EXP: {exp}/{exp_necesaria})\n\n📖 *Historia:*\n{historia}\n\n"
            f"🗡️ Arma: **{arma_equipada}**\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}/{mana_max}\n"
            f"⚔️ ATQ: {atq} | 💨 MOV: {mov} | 🧠 INT: {intel}\n🛡️ RES: {res} | 🎯 TAC: {tac}\n\n⚡ *Energía:* {energia}/5 | ⭐ *Estrellas:* {estrellas}")
        msg = await update.message.reply_text(texto, parse_mode="Markdown")
        context.user_data['msg_perfil'] = msg.message_id

async def portal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT vida, energia, rango, bloqueo_hasta, nivel, clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    
    if user[3] and user[3] > datetime.datetime.now():
        cur.close(); conn.close()
        msg = await update.message.reply_text(f"☠️ *Estás herido.* Bloqueado.", parse_mode="Markdown"); context.user_data['msg_error'] = msg.message_id; return
    if user[1] <= 0:
        cur.close(); conn.close()
        msg = await update.message.reply_text("⚡ *Sin Energía.*", parse_mode="Markdown"); context.user_data['msg_error'] = msg.message_id; return
        
    nivel, clase = user[4], user[5]
    rango_jugador = user[2]
    
    cur.execute("SELECT COUNT(*) FROM derrotados WHERE id_telegram = %s", (user_id,))
    derrotados_count = cur.fetchone()[0]
    
    es_jefe = False
    if rango_jugador == "E" and derrotados_count >= 5 and nivel >= 10:
        monstruo = MONSTRUOS["JEFE_E"]
        es_jefe = True
    else:
        enemigos_rango = MONSTRUOS.get(rango_jugador, MONSTRUOS["E"])
        cur.execute("SELECT nombre FROM derrotados WHERE id_telegram = %s", (user_id,))
        derrotados = [row[0] for row in cur.fetchall()]
        disponibles = [e for e in enemigos_rango if e['nombre'] not in derrotados]
        if not disponibles:
            msg = await update.message.reply_text("🌑 *Has derrotado a todos.*", parse_mode="Markdown"); cur.close(); conn.close(); return
        monstruo = random.choice(disponibles)

    cur.execute("UPDATE usuarios SET en_combate = TRUE, monstruo_hp = %s, monstruo_nombre = %s, energia = energia - 1 WHERE id_telegram = %s", (monstruo['hp'], monstruo['nombre'], user_id))
    conn.commit(); cur.close(); conn.close()
    
    context.user_data['monstruo'] = monstruo
    context.user_data['es_jefe'] = es_jefe
    
    msg_trans = await update.message.reply_text("🌀 *Abriendo portal...*", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    
    async def transicion_y_combate():
        conn_img = psycopg2.connect(DATABASE_URL, sslmode='require'); cur_img = conn_img.cursor()
        cur_img.execute("SELECT imagen FROM bestiario_imagenes WHERE nombre = %s", (monstruo['nombre'],))
        row = cur_img.fetchone()
        
        if row:
            image_bytes = bytes(row[0])
        else:
            prompt_m = f"monster {monstruo['nombre']}"
            image_bytes = await generar_imagen_sistema(prompt_m, es_monstruo=True)
            if image_bytes:
                try:
                    cur_img.execute("INSERT INTO bestiario_imagenes (nombre, imagen) VALUES (%s, %s) ON CONFLICT DO NOTHING", (monstruo['nombre'], psycopg2.Binary(image_bytes)))
                    conn_img.commit()
                except: pass
        cur_img.close(); conn_img.close()
        
        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_trans.message_id)
        except: pass
        
        # --- BOTONES DE COMBATE (ANCHO COMPLETO) ---
        keyboard = [
            [InlineKeyboardButton("⚔️ ATACAR", callback_data='combate_atacar')],
            [InlineKeyboardButton("💨 ESQUIVAR", callback_data='combate_esquivar')],
            [InlineKeyboardButton("🔮 HABILIDAD", callback_data='combate_habilidad')],
            [InlineKeyboardButton("🏃 HUIR", callback_data='combate_huir')]
        ]
        
        titulo = "👑 *JEFE FINAL*" if es_jefe else "🩸 *PORTAL ABIERTO*"
        texto = f"{titulo}\n\n**{monstruo['nombre']}** ha aparecido.\n❤️ Vida: {monstruo['hp']}\n\n*¿Qué harás?*"
        
        if image_bytes:
            texto_foto = f"🩸 *ENTIDAD DETECTADA*\n\n{texto}"
            try: 
                msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=texto_foto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
                context.user_data['msg_combate'] = msg.message_id
                context.user_data['estado'] = 'en_combate'
            except: pass
        else:
            msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            context.user_data['msg_combate'] = msg.message_id
            context.user_data['estado'] = 'en_combate'
            
    asyncio.create_task(transicion_y_combate())

async def boton_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'en_combate': return
    accion = query.data.replace('combate_', '')
    user_id = update.effective_user.id
    frase = context.user_data.get('frase_epica', ''); context.user_data['frase_epica'] = ''
    monstruo = context.user_data.get('monstruo', {"nombre": "Karu", "hp": 100, "exp": 100, "atk": 10, "grupo": "A"})
    es_jefe = context.user_data.get('es_jefe', False)
    
    try: await query.edit_message_caption(caption="⏳ *Calculando destino...*", parse_mode="Markdown")
    except: 
        try: await query.edit_message_text("⏳ *Calculando destino...*", parse_mode="Markdown")
        except: pass
        
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, vida, vida_max, mana, atq, mov, intel, exp, nivel, rango, monstruo_hp FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    nombre, clase, vida, vida_max, mana, atq, mov, intel, exp, nivel, rango, hp_monstruo = user
    
    dano = 0; dano_recibido = 0; accion_texto = ""; result_texto = ""
    
    if accion == 'huir':
        if random.randint(1, 100) <= (mov * 2):
            accion_texto = f"{nombre} intenta huir."; result_texto = "Escapa."
            cur.execute("UPDATE usuarios SET en_combate = FALSE WHERE id_telegram = %s", (user_id,)); conn.commit(); cur.close(); conn.close()
            
            narr = "🌑 *Has escapado.* La oscuridad del portal se cierra tras de ti. No hay recompensa para los cobardes, pero vives para pelear otro día."
            try: await query.edit_message_caption(caption=narr, parse_mode="Markdown")
            except: await query.edit_message_text(narr, parse_mode="Markdown")
            
            msg_foto_id = context.user_data.get('msg_combate')
            if msg_foto_id:
                try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_foto_id)
                except: pass
                
            context.user_data['estado'] = 'en_menu'; await context.bot.send_message(chat_id=update.effective_chat.id, text="​", reply_markup=obtener_menu_fijo()); return
        else:
            dano_recibido = monstruo['atk'] + random.randint(1, 5); vida -= dano_recibido
            accion_texto = f"{nombre} intenta huir."; result_texto = f"Falla. {dano_recibido} de daño."
    elif accion == 'esquivar':
        if random.randint(1, 100) <= (mov * 3):
            accion_texto = f"{nombre} esquiva."; result_texto = "Sin daño."
        else:
            dano_recibido = monstruo['atk'] - random.randint(1, 5)
            if dano_recibido < 1: dano_recibido = 1
            vida -= dano_recibido; accion_texto = f"{nombre} intenta esquivar."; result_texto = f"Falla. {dano_recibido} de daño."
    else:
        if accion == 'atacar': 
            dano = atq + random.randint(1, 10); accion_texto = f"{nombre} ataca."
        else:
            costo_mana = 10
            if mana >= costo_mana:
                mana -= costo_mana; stat = intel if clase in ['Mago', 'Maga'] else atq
                dano = int((stat * 1.5) + random.randint(5, 15)); accion_texto = f"{nombre} usa su habilidad."
            else: 
                dano = 0
                accion_texto = f"{nombre} intenta usar su habilidad."
                result_texto = "El Sistema bloquea el ataque: MANÁ INSUFICIENTE."
        if dano > 0:
            mult = calcular_dano_faccion(clase, monstruo['grupo'])
            dano = int(dano * mult)
            if mult == 1.5: accion_texto += " ¡Debilidad detectada! "
            elif mult == 0.5: accion_texto += " Ataque resistido. "
            
        hp_monstruo -= dano
        if hp_monstruo < 0: hp_monstruo = 0
        if dano > 0:
            result_texto = f"{dano} de daño infligido."
            if hp_monstruo > 0:
                dano_recibido = monstruo['atk'] + random.randint(1, 5); vida -= dano_recibido; result_texto += f" {dano_recibido} de daño recibido."
    if vida < 0: vida = 0
    
    contexto_ia = f"Acción: {accion_texto}. Resultado: {result_texto}." + (f" Gritó: '{frase}'." if frase else "")
    narracion_epica = await narrar_con_ia("Eres 'El Sistema', frío y brutal. Narra la acción en 3 líneas.", contexto_ia)
    if not narracion_epica: 
        narracion_epica = texto_respaldo("combate", nombre, monstruo['nombre'])
    
    if hp_monstruo <= 0:
        if es_jefe:
            narracion_epica += f"\n\n👑 **HAS DERROTADO AL JEFE FINAL.**\nEl Sistema te permite ascender al Rango D."
            nuevo_rango = 'D'
            cur.execute("UPDATE usuarios SET rango = %s, vida = %s, mana = %s, en_combate = FALSE, energia = 5 WHERE id_telegram = %s", (nuevo_rango, vida, mana, user_id))
        else:
            mult_exp = calcular_multiplicador_exp(clase, monstruo['grupo'])
            exp_ganada = int(monstruo['exp'] * mult_exp)
            narracion_epica += f"\n\n💀 **{monstruo['nombre']} ha muerto.**\n🌟 *+{exp_ganada} EXP.*"
            exp += exp_ganada
            nuevo_rango = rango
            exp_necesaria = nivel * 100
            if exp >= exp_necesaria and nivel < 10:
                exp -= exp_necesaria
                nivel += 1
                vida_max += 20; vida = vida_max; atq += 2; mov += 1; intel += 2
                narracion_epica += f"\n\n⬆️ **¡NIVEL {nivel}!**"
                
            cur.execute("INSERT INTO derrotados (id_telegram, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, monstruo['nombre']))
            cur.execute("UPDATE usuarios SET vida = %s, vida_max = %s, mana = %s, atq = %s, mov = %s, intel = %s, exp = %s, nivel = %s, rango = %s, en_combate = FALSE, energia = 5 WHERE id_telegram = %s", (vida, vida_max, mana, atq, mov, intel, exp, nivel, nuevo_rango, user_id))
            
        conn.commit(); cur.close(); conn.close()
        
        try: await query.edit_message_caption(caption=f"{narracion_epica}", parse_mode="Markdown")
        except: await query.edit_message_text(f"{narracion_epica}", parse_mode="Markdown")
        
        # Borrar foto del monstruo
        msg_foto_id = context.user_data.get('msg_combate')
        if msg_foto_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_foto_id)
            except: pass
            
        context.user_data['estado'] = 'en_menu'; await context.bot.send_message(chat_id=update.effective_chat.id, text="​", reply_markup=obtener_menu_fijo()); return
        
    if vida <= 0:
        narracion_epica += f"\n\n☠️ **Has muerto.** El Sistema te castiga con 1 hora de bloqueo."
        bloqueo = datetime.datetime.now() + datetime.timedelta(hours=1)
        cur.execute("UPDATE usuarios SET vida = 0, en_combate = FALSE, bloqueo_hasta = %s WHERE id_telegram = %s", (bloqueo, user_id))
        conn.commit(); cur.close(); conn.close()
        
        try: await query.edit_message_caption(caption=f"{narracion_epica}", parse_mode="Markdown")
        except: await query.edit_message_text(f"{narracion_epica}", parse_mode="Markdown")
        
        msg_foto_id = context.user_data.get('msg_combate')
        if msg_foto_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_foto_id)
            except: pass
            
        context.user_data['estado'] = 'en_menu'; await context.bot.send_message(chat_id=update.effective_chat.id, text="​", reply_markup=obtener_menu_fijo()); return
        
    cur.execute("UPDATE usuarios SET vida = %s, mana = %s, monstruo_hp = %s WHERE id_telegram = %s", (vida, mana, hp_monstruo, user_id))
    conn.commit(); cur.close(); conn.close()
    
    keyboard = [
        [InlineKeyboardButton("⚔️ ATACAR", callback_data='combate_atacar')],
        [InlineKeyboardButton("💨 ESQUIVAR", callback_data='combate_esquivar')],
        [InlineKeyboardButton("🔮 HABILIDAD", callback_data='combate_habilidad')],
        [InlineKeyboardButton("🏃 HUIR", callback_data='combate_huir')]
    ]
    try: await query.edit_message_caption(caption=f"{narracion_epica}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}\n🩸 {monstruo['nombre']}: {hp_monstruo}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except: await query.edit_message_text(f"{narracion_epica}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}\n🩸 {monstruo['nombre']}: {hp_monstruo}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    estrellas = cur.fetchone()[0]; cur.close(); conn.close()
    keyboard = [
        [InlineKeyboardButton("🧪 POCIONES", callback_data='tienda_pociones')],
        [InlineKeyboardButton("⚔️ ARMERÍA", callback_data='tienda_armeria')],
        [InlineKeyboardButton("🎁 CAJAS MISTERIOSAS", callback_data='tienda_cajas')],
        [InlineKeyboardButton("👑 BENDICIONES", callback_data='tienda_bendiciones')],
        [InlineKeyboardButton("🔙 VOLVER AL MENÚ", callback_data='volver_menu')]
    ]
    msg = await update.message.reply_text(f"🛒 *MERCADO DEL SISTEMA*\n⭐ Estrellas: **{estrellas}**\n\nElige una categoría:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    context.user_data['msg_tienda'] = msg.message_id

async def tienda_pociones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    texto = ("🧪 *POCIONES*\n\n• *Poción de Vida (5⭐):* Restaura 50 HP.\n• *Poción de Maná (5⭐):* Restaura 50 MP.\n• *Elixir Completo (15⭐):* Restaura toda la Vida y Maná.")
    keyboard = [[InlineKeyboardButton("🧪 Comprar Poción Vida - 5⭐", callback_data='comprar_pocion_vida')], [InlineKeyboardButton("🔮 Comprar Poción Maná - 5⭐", callback_data='comprar_pocion_mana')], [InlineKeyboardButton("🧪 Comprar Elixir Completo - 15⭐", callback_data='comprar_elixir')], [InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def tienda_armeria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    texto = ("⚔️ *ARMERÍA DEL SISTEMA*\n\nEl Sistema te permite comprar armas de tu clase o de otras (con penalización).")
    keyboard = [
        [InlineKeyboardButton("⚔️ Armas de Ejecutor", callback_data='armeria_ejecutor')],
        [InlineKeyboardButton("🔮 Armas de Mago", callback_data='armeria_mago')],
        [InlineKeyboardButton("🛡️ Armas de Guardián", callback_data='armeria_guardian')],
        [InlineKeyboardButton("🗡️ Armas de Asesino", callback_data='armeria_asesino')],
        [InlineKeyboardButton("🏹 Armas de Arquero", callback_data='armeria_arquero')],
        [InlineKeyboardButton("✨ Armas de Clérigo", callback_data='armeria_clerigo')],
        [InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]
    ]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def armeria_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    clase_arma = query.data.replace('armeria_', '')
    armas_lista = ARMAS.get(clase_arma, [])
    
    texto = f"⚔️ *ARMAS DE {clase_arma.upper()}*\n\n"
    keyboard = []
    for arma in armas_lista:
        texto += f"• *{arma['nombre']}* (Tier {arma['tier']}) - +{arma['stat']} Stats | {arma['precio']}⭐\n"
        keyboard.append([InlineKeyboardButton(f"Comprar {arma['nombre']} - {arma['precio']}⭐", callback_data=f"comprar_arma_{arma['nombre']}_{clase_arma}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data='tienda_armeria')])
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def tienda_cajas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    texto = ("🎁 *CAJAS MISTERIOSAS*\n\n• *Caja Común (10⭐):* 70% Poción | 30% Arma Común.\n• *Cofre Épico (30⭐):* 50% Arma Rara | 50% Elixir.")
    keyboard = [[InlineKeyboardButton("📦 Comprar Caja Común - 10⭐", callback_data='comprar_caja_comun')], [InlineKeyboardButton("🎁 Comprar Cofre Épico - 30⭐", callback_data='comprar_cofre_epico')], [InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def tienda_bendiciones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    await query.answer("👑 Las Bendiciones del Creador aún están bloqueadas.", show_alert=True)

async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); user_id = update.effective_user.id
    item = query.data.replace('comprar_', '')
    
    if item.startswith("arma_"):
        partes = item.split("_")
        nombre_arma = partes[1]
        clase_original = partes[2]
        precio = 15 if "Tier 1" in nombre_arma else 40 # Simplificado para el ejemplo
        # Buscamos el precio real
        for c, armas_lista in ARMAS.items():
            for a in armas_lista:
                if a['nombre'] == nombre_arma:
                    precio = a['precio']
                    stat_bonus = a['stat']
                    break
        
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("SELECT estrellas, clase FROM usuarios WHERE id_telegram = %s", (user_id,))
        estrellas, clase_jugador = cur.fetchone()
        
        if estrellas < precio: await query.answer("❌ Sin Estrellas.", show_alert=True); return
        
        # Penalización por herejía
        if clase_jugador.lower() != clase_original.lower():
            stat_bonus = stat_bonus // 2
            
        cur.execute("UPDATE usuarios SET estrellas = estrellas - %s WHERE id_telegram = %s", (precio, user_id))
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, stat_bonus, clase_original, cantidad) VALUES (%s, %s, 'arma', %s, %s, 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id, nombre_arma, stat_bonus, clase_original))
        conn.commit(); cur.close(); conn.close()
        await query.edit_message_text(f"✅ Has comprado **{nombre_arma}**.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]), parse_mode="Markdown")
        return

    precios = {'pocion_vida': 5, 'pocion_mana': 5, 'elixir': 15, 'caja_comun': 10, 'cofre_epico': 30}
    precio = precios.get(item, 0)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    estrellas = cur.fetchone()[0]
    if estrellas < precio: await query.answer("❌ Sin Estrellas.", show_alert=True); return
    cur.execute("UPDATE usuarios SET estrellas = estrellas - %s WHERE id_telegram = %s", (precio, user_id))
    
    if item == 'pocion_vida':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Poción de Vida', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,)); msg = "✅ Poción Vida."
    elif item == 'pocion_mana':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Poción de Maná', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,)); msg = "✅ Poción Maná."
    elif item == 'elixir':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Elixir Completo', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,)); msg = "✅ Elixir."
    elif item == 'caja_comun':
        if random.randint(1, 100) <= 70:
            cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Poción de Vida', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,)); msg = "📦 Poción Vida."
        else:
            arma, bonus = random.choice([("Daga de Óxido", 3), ("Bastón Astillado", 3)])
            cur.execute("INSERT INTO inventario (id_telegram, item, tipo, stat_bonus, cantidad) VALUES (%s, %s, 'arma', %s, 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id, arma, bonus)); msg = f"📦 {arma} (+{bonus})."
    elif item == 'cofre_epico':
        arma, bonus = random.choice([("Filo del Eclipse", 8), ("Cetro del Registro", 8)])
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, stat_bonus, cantidad) VALUES (%s, %s, 'arma', %s, 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id, arma, bonus)); msg = f"🎁 {arma} (+{bonus})."
    conn.commit(); cur.close(); conn.close()
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]), parse_mode="Markdown")

async def inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT item, tipo, stat_bonus, cantidad FROM inventario WHERE id_telegram = %s", (user_id,))
    items = cur.fetchall(); cur.close(); conn.close()
    if not items: msg = await update.message.reply_text("🎒 Vacío."); context.user_data['msg_bienvenida'] = msg.message_id; return
    keyboard = []; texto = "🎒 *INVENTARIO*\n\n"
    for item, tipo, bonus, cant in items:
        if tipo == 'arma': texto += f"🗡️ {item} (+{bonus}) x{cant}\n"; keyboard.append([InlineKeyboardButton(f"Equipar {item}", callback_data=f"equipar_{item}")])
        else: texto += f"🧪 {item} x{cant}\n"
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data='volver_menu')])
    msg = await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"); context.user_data['msg_bienvenida'] = msg.message_id

async def equipar_arma(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); user_id = update.effective_user.id
    arma = query.data.replace('equipar_', ''); conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT stat_bonus FROM inventario WHERE id_telegram = %s AND item = %s", (user_id, arma)); bonus = cur.fetchone()[0]
    cur.execute("SELECT arma_equipada FROM usuarios WHERE id_telegram = %s", (user_id,)); arma_vieja = cur.fetchone()[0]
    if arma_vieja != 'Ninguna':
        cur.execute("SELECT stat_bonus FROM inventario WHERE id_telegram = %s AND item = %s", (user_id, arma_vieja)); res = cur.fetchone()
        if res: cur.execute("UPDATE usuarios SET atq = atq - %s WHERE id_telegram = %s", (res[0], user_id))
    cur.execute("UPDATE usuarios SET atq = atq + %s, arma_equipada = %s WHERE id_telegram = %s", (bonus, arma, user_id))
    conn.commit(); cur.close(); conn.close()
    await query.edit_message_text(f"✅ Equipado: **{arma}**.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data='volver_menu')]]), parse_mode="Markdown")

async def volver_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    await query.edit_message_text("🌑 *Menú.*", parse_mode="Markdown")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="​", reply_markup=obtener_menu_fijo())

async def creador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ID_CREADOR: return
    keyboard = [[InlineKeyboardButton("👑 Invocar Jefe Supremo", callback_data='admin_jefe')], [InlineKeyboardButton("⭐ Regalar Estrellas", callback_data='admin_regalar_estrellas')]]
    await update.message.reply_text("👑 *PANEL DEL CREADOR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def boton_creador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if update.effective_user.id != ID_CREADOR: return
    if query.data == 'admin_jefe':
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("INSERT INTO jefe_supremo (id, nombre, vida, activo) VALUES (1, 'El Devorador', 100000, TRUE) ON CONFLICT (id) DO UPDATE SET vida = 100000, activo = TRUE")
        conn.commit(); cur.close(); conn.close()
        await query.edit_message_text("👑 Jefe invocado.")
    elif query.data == 'admin_regalar_estrellas':
        await query.edit_message_text("Escribe ID y cantidad (ej: `6985217869 100`).", parse_mode="Markdown")
        context.user_data['estado'] = 'regalar_estrellas'

class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"El Sistema esta vivo.")

def main():
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("creador", creador))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Sticker.ALL | filters.AUDIO) & ~filters.COMMAND, manejar_mensajes))
    app.add_handler(CallbackQueryHandler(boton_sexo, pattern='^sexo_'))
    app.add_handler(CallbackQueryHandler(boton_clase, pattern='^clase_'))
    app.add_handler(CallbackQueryHandler(boton_combate, pattern='^combate_'))
    app.add_handler(CallbackQueryHandler(boton_creador, pattern='^admin_'))
    app.add_handler(CallbackQueryHandler(tienda_pociones, pattern='^tienda_pociones$'))
    app.add_handler(CallbackQueryHandler(tienda_armeria, pattern='^tienda_armeria$'))
    app.add_handler(CallbackQueryHandler(armeria_categoria, pattern='^armeria_'))
    app.add_handler(CallbackQueryHandler(tienda_cajas, pattern='^tienda_cajas$'))
    app.add_handler(CallbackQueryHandler(tienda_bendiciones, pattern='^tienda_bendiciones$'))
    app.add_handler(CallbackQueryHandler(comprar, pattern='^comprar_'))
    app.add_handler(CallbackQueryHandler(equipar_arma, pattern='^equipar_'))
    app.add_handler(CallbackQueryHandler(volver_menu, pattern='^volver_menu$'))
    app.add_handler(CallbackQueryHandler(tienda, pattern='^menu_tienda$'))
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
