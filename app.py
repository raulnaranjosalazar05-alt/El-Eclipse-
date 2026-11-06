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
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
PORT = int(os.environ.get("PORT", 8080))
ID_CREADOR = 6985217869
ID_GRUPO = -1004347230537
LINK_GRUPO = "https://t.me/ElRefugio_Eclipse"

GRUPO_A = ["Ejecutor", "Asesino", "Arquero"]
GRUPO_B = ["Mago", "Guardián", "Clérigo"]

ARMAS = {
    "ejecutor": [{"nombre": "Espada Corta", "tier": 1, "stat": 5, "precio": 15}, {"nombre": "Filo del Eclipse", "tier": 2, "stat": 10, "precio": 40}, {"nombre": "Mandoble del Vacío", "tier": 3, "stat": 15, "precio": 100}],
    "mago": [{"nombre": "Bastón Astillado", "tier": 1, "stat": 5, "precio": 15}, {"nombre": "Cetro del Registro", "tier": 2, "stat": 10, "precio": 40}, {"nombre": "Vara de la Creación", "tier": 3, "stat": 15, "precio": 100}],
    "guardian": [{"nombre": "Escudo de Madera", "tier": 1, "stat": 5, "precio": 15}, {"nombre": "Muro de Obsidiana", "tier": 2, "stat": 10, "precio": 40}, {"nombre": "Baluarte del Sistema", "tier": 3, "stat": 15, "precio": 100}],
    "asesino": [{"nombre": "Daga de Óxido", "tier": 1, "stat": 5, "precio": 15}, {"nombre": "Colmillos Gemelos", "tier": 2, "stat": 10, "precio": 40}, {"nombre": "Filos del Silencio", "tier": 3, "stat": 15, "precio": 100}],
    "arquero": [{"nombre": "Arco Corto", "tier": 1, "stat": 5, "precio": 15}, {"nombre": "Arco de Energía", "tier": 2, "stat": 10, "precio": 40}, {"nombre": "Ballesta del Eclipse", "tier": 3, "stat": 15, "precio": 100}],
    "clerigo": [{"nombre": "Símbolo Menor", "tier": 1, "stat": 5, "precio": 15}, {"nombre": "Reliquia del Alba", "tier": 2, "stat": 10, "precio": 40}, {"nombre": "Cetro de Fe", "tier": 3, "stat": 15, "precio": 100}]
}

MONSTRUOS = {
    "E": [{"nombre": "Karu, el Registrado", "hp": 100, "atk": 25, "grupo": "A", "exp": 100}, {"nombre": "Vex, Sujeto 07", "hp": 120, "atk": 28, "grupo": "B", "exp": 100}, {"nombre": "Kael, Eco del Portal", "hp": 90, "atk": 30, "grupo": "A", "exp": 100}, {"nombre": "Zeth, Larva del Umbral", "hp": 80, "atk": 22, "grupo": "B", "exp": 100}, {"nombre": "Rakan, Colmillo Rojo", "hp": 130, "atk": 32, "grupo": "A", "exp": 100}],
    "D": [{"nombre": "Draven, el que Espera", "hp": 200, "atk": 40, "grupo": "A", "exp": 250}, {"nombre": "Sirak, Tres Bocas", "hp": 180, "atk": 45, "grupo": "B", "exp": 240}, {"nombre": "Nox, el Silencioso", "hp": 150, "atk": 50, "grupo": "A", "exp": 260}, {"nombre": "Thane, Piel de Piedra", "hp": 300, "atk": 35, "grupo": "B", "exp": 280}, {"nombre": "Vorkan, el que Devora", "hp": 220, "atk": 42, "grupo": "A", "exp": 270}],
    "C": [{"nombre": "Malakar, el que Renace", "hp": 450, "atk": 60, "grupo": "B", "exp": 500}, {"nombre": "Senn, la Grieta", "hp": 380, "atk": 65, "grupo": "A", "exp": 480}, {"nombre": "Orun, el Coro", "hp": 350, "atk": 70, "grupo": "B", "exp": 490}, {"nombre": "Vesper, la Mano", "hp": 400, "atk": 55, "grupo": "A", "exp": 510}, {"nombre": "Krag, el Hambriento", "hp": 420, "atk": 62, "grupo": "B", "exp": 520}, {"nombre": "Lyra, la que Canta", "hp": 360, "atk": 68, "grupo": "A", "exp": 495}],
    "B": [{"nombre": "Dorn, el Ancla", "hp": 600, "atk": 75, "grupo": "A", "exp": 800}, {"nombre": "Sylas, Dos Caras", "hp": 550, "atk": 80, "grupo": "B", "exp": 820}, {"nombre": "Mork, el que Copia", "hp": 580, "atk": 78, "grupo": "A", "exp": 810}, {"nombre": "Tessa, la Niebla", "hp": 520, "atk": 85, "grupo": "B", "exp": 830}, {"nombre": "Brann, el Quebrado", "hp": 650, "atk": 72, "grupo": "A", "exp": 790}, {"nombre": "Ulric, el Silencio", "hp": 570, "atk": 82, "grupo": "B", "exp": 840}],
    "A": [{"nombre": "Vareth, el Rey Roto", "hp": 800, "atk": 95, "grupo": "B", "exp": 1200}, {"nombre": "Nihilus, el Vacío", "hp": 750, "atk": 100, "grupo": "A", "exp": 1150}, {"nombre": "Seraph, el Caído", "hp": 780, "atk": 98, "grupo": "B", "exp": 1180}, {"nombre": "Gorrath, el Montaña", "hp": 950, "atk": 90, "grupo": "A", "exp": 1220}, {"nombre": "Yvaine, la Última", "hp": 820, "atk": 96, "grupo": "B", "exp": 1210}],
    "S": [{"nombre": "Zero, el que No Fue", "hp": 1200, "atk": 120, "grupo": "A", "exp": 2000}, {"nombre": "Theia, la que Ve", "hp": 1100, "atk": 125, "grupo": "B", "exp": 2100}, {"nombre": "Abel, el Primero", "hp": 1300, "atk": 118, "grupo": "A", "exp": 2200}],
    "JEFE_E": {"nombre": "Guardián del Umbral", "hp": 300, "atk": 40, "grupo": "C", "exp": 0},
    "JEFE_D": {"nombre": "El Coloso de Hierro", "hp": 600, "atk": 60, "grupo": "C", "exp": 0},
    "JEFE_C": {"nombre": "El Ojo del Eclipse", "hp": 1200, "atk": 85, "grupo": "C", "exp": 0},
    "JEFE_B": {"nombre": "El Sepulturero de Almas", "hp": 2000, "atk": 110, "grupo": "C", "exp": 0},
    "JEFE_A": {"nombre": "El Titán del Eclipse", "hp": 3500, "atk": 150, "grupo": "C", "exp": 0}
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
                arma_equipada VARCHAR(50) DEFAULT 'Ninguna', maestro_id BIGINT DEFAULT NULL
            )
        """)
        cur.execute("DROP TABLE IF EXISTS inventario;")
        cur.execute("CREATE TABLE IF NOT EXISTS inventario (id_telegram BIGINT, item VARCHAR(50), tipo VARCHAR(20), stat_bonus INT, clase_original VARCHAR(20), cantidad INT DEFAULT 1, PRIMARY KEY (id_telegram, item));")
        cur.execute("DROP TABLE IF EXISTS derrotados;")
        cur.execute("CREATE TABLE IF NOT EXISTS derrotados (id_telegram BIGINT, nombre VARCHAR(100), PRIMARY KEY (id_telegram, nombre));")
        cur.execute("DROP TABLE IF EXISTS bestiario_imagenes;")
        cur.execute("CREATE TABLE IF NOT EXISTS bestiario_imagenes (nombre VARCHAR(100) PRIMARY KEY, imagen BYTEA);")
        cur.execute("DROP TABLE IF EXISTS pagos;")
        cur.execute("CREATE TABLE IF NOT EXISTS pagos (id SERIAL PRIMARY KEY, id_telegram BIGINT, monto INT, fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
        cur.execute("DROP TABLE IF EXISTS jefe_supremo;")
        cur.execute("CREATE TABLE IF NOT EXISTS jefe_supremo (id INT PRIMARY KEY, nombre VARCHAR(100), vida INT, vida_max INT, activo BOOLEAN);")
        cur.execute("DROP TABLE IF EXISTS leyendas;")
        cur.execute("CREATE TABLE IF NOT EXISTS leyendas (temporada INT, nombre VARCHAR(50), clase VARCHAR(20), logro TEXT);")
        cur.execute("DROP TABLE IF EXISTS config;")
        cur.execute("CREATE TABLE IF NOT EXISTS config (clave VARCHAR(20) PRIMARY KEY, valor INT);")
        cur.execute("INSERT INTO config (clave, valor) VALUES ('temporada', 1) ON CONFLICT (clave) DO NOTHING;")
        conn.commit(); cur.close(); conn.close()
        print("✅ Base de datos lista.")
    except Exception as e: print(f"❌ ERROR BD: {e}")

async def narrar_con_ia(prompt_sistema, contexto):
    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ACCOUNT_ID:
        print("⚠️ Faltan credenciales de Cloudflare en Render.")
        return None
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/meta/llama-3-8b-instruct"
    
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": contexto}
        ],
        "max_tokens": 120,
        "temperature": 0.8
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    texto = data.get('result', {}).get('response', '')
                    return texto.strip().replace('*', '').replace('_', '')
                else:
                    error_text = await response.text()
                    print(f"❌ Error Cloudflare IA: {response.status} - {error_text}")
                    return None
    except Exception as e:
        print(f"❌ Error de conexión con Cloudflare: {e}")
        return None

async def generar_imagen_sistema(prompt, es_monstruo=False):
    if es_monstruo: prompt_mejorado = f"epic fantasy monster concept art, {prompt}, glowing eyes, cinematic lighting, masterpiece"
    else: prompt_mejorado = f"anime style portrait of a {prompt}, beautiful detailed eyes, dark fantasy aesthetic, masterpiece"
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt_mejorado)}?width=512&height=512&nologo=true&model=turbo"
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
    for clave in ['msg_bienvenida', 'msg_error', 'msg_perfil', 'msg_combate', 'msg_tienda', 'msg_creador', 'msg_pregunta_sexo', 'msg_pregunta_clase', 'msg_transicion', 'msg_duelo']:
        msg_id = context.user_data.get(clave)
        if msg_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except: pass
    if update.message:
        try: await update.message.delete()
        except: pass

def obtener_menu_fijo():
    return ReplyKeyboardMarkup([
        [KeyboardButton("👤 Perfil"), KeyboardButton("🩸 Portal")], 
        [KeyboardButton("🛒 Tienda"), KeyboardButton("🎒 Inventario")],
        [KeyboardButton("🍻 La Taberna"), KeyboardButton("⚔️ Arena PvP")]
    ], resize_keyboard=True)

async def enviar_factura(update: Update, context: ContextTypes.DEFAULT_TYPE, item_nombre, item_precio, item_callback):
    try: await update.callback_query.message.delete()
    except: pass
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id, title=f"El Eclipse - {item_nombre}",
        description=f"Compra de {item_nombre} en el Mercado del Sistema.", payload=item_callback,
        provider_token="", currency="XTR", prices=[{"label": item_nombre, "amount": item_precio}]
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def pago_exitoso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pago = update.message.successful_payment
    payload = pago.invoice_payload; user_id = update.effective_user.id
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("INSERT INTO pagos (id_telegram, monto) VALUES (%s, %s)", (user_id, pago.total_amount))
    if payload == 'pocion_vida':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Poción de Vida', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,)); msg = "✅ Poción de Vida añadida."
    elif payload == 'pocion_mana':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Poción de Maná', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,)); msg = "✅ Poción de Maná añadida."
    elif payload == 'elixir':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Elixir Completo', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,)); msg = "✅ Elixir añadido."
    elif payload.startswith("arma_"):
        partes = payload.split("_"); nombre_arma = partes[1]; clase_original = partes[2]
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, stat_bonus, clase_original, cantidad) VALUES (%s, %s, 'arma', 5, %s, 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id, nombre_arma, clase_original)); msg = f"✅ {nombre_arma} añadida."
    else: msg = "✅ Pago recibido."
    conn.commit(); cur.close(); conn.close()
    keyboard = [[InlineKeyboardButton("🔙 Volver a la Tienda", callback_data='menu_tienda')]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; await limpiar_chat(update, context)
    maestro_id = None
    if context.args:
        try: maestro_id = int(context.args[0])
        except: pass
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    if resultado and resultado[0] is not None:
        cur.close(); conn.close()
        msg = await update.message.reply_text("🌑 *Regreso detectado.*", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
        context.user_data['msg_bienvenida'] = msg.message_id; return
    context.user_data['maestro_id'] = maestro_id; context.user_data['estado'] = 'esperando_nombre'
    msg = await update.message.reply_text("🌑 *El Sistema te ha detectado.*\n\n**¿Cuál es tu nombre, Sujeto?**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    context.user_data['msg_bienvenida'] = msg.message_id; cur.close(); conn.close()

async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text; estado = context.user_data.get('estado')
    if texto == "👤 Perfil": await perfil(update, context); return
    elif texto == "🩸 Portal": await portal(update, context); return
    elif texto == "🛒 Tienda": await tienda(update, context); return
    elif texto == "🎒 Inventario": await inventario(update, context); return
    elif texto == "🍻 La Taberna":
        await limpiar_chat(update, context)
        await update.message.reply_text(f"🍻 *LA TABERNA*\n\nReúnete con otros Cazadores, presume tus trofeos y conspira contra el Sistema.\n\n👉 [Entrar a La Taberna]({LINK_GRUPO})", parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif texto == "⚔️ Arena PvP":
        await limpiar_chat(update, context)
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("SELECT nivel, nombre FROM usuarios WHERE id_telegram = %s", (update.effective_user.id,))
        mi_nivel, mi_nombre = cur.fetchone()
        
        cur.execute("SELECT id_telegram, nombre, nivel, clase FROM usuarios WHERE id_telegram != %s AND nivel BETWEEN %s AND %s ORDER BY RANDOM() LIMIT 1", (update.effective_user.id, mi_nivel - 5, mi_nivel + 5))
        rival = cur.fetchone()
        
        if not rival:
            await update.message.reply_text("🌑 *El Sistema no encuentra rivales de tu nivel en este momento.*\nIntenta más tarde.", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
            cur.close(); conn.close(); return
            
        rival_id, rival_nombre, rival_nivel, rival_clase = rival
        
        texto_reto = (
            f"🩸 *RETO DE SANGRE EN LA ARENA*\n\n"
            f"El Sujeto **{mi_nombre}** (Nivel {mi_nivel}) te ha desafiado.\n\n"
            f"🏅 *Recompensa:* 5 Estrellas ⭐ al ganador.\n"
            f"💀 *Castigo:* El perdedor pierde 1 Energía y queda al 50% de Vida.\n\n"
            f"*El Sistema espera tu respuesta.*"
        )
        keyboard = [[InlineKeyboardButton("⚔️ Aceptar Duelo", callback_data=f"aceptar_duelo_{update.effective_user.id}")]]
        
        try:
            await context.bot.send_message(chat_id=rival_id, text=texto_reto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            await update.message.reply_text(f"✅ Reto enviado a **{rival_nombre}** (Nivel {rival_nivel}).\n\n*Si ganas: +5 Estrellas ⭐. Si pierdes: -1 Energía y quedas al 50% de vida.*", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
        except:
            await update.message.reply_text("🌑 El rival no tiene el bot abierto.", reply_markup=obtener_menu_fijo())
        
        cur.close(); conn.close(); return
    
    if texto in ["⚔️ Ejecutor", "🔮 Mago", "🛡️ Guardián", "🗡️ Asesino", "🏹 Arquero", "✨ Clérigo"]:
        context.user_data['clase_temp'] = texto; await procesar_clase_final(update, context); return
    if estado == 'esperando_nombre':
        if not texto:
            try: await update.message.delete() 
            except: pass
            msg = await update.message.reply_text("⚠️ Escribe tu nombre con letras.", parse_mode="Markdown"); context.user_data['msg_error'] = msg.message_id; return
        try: await update.message.delete()
        except: pass
        await limpiar_chat(update, context)
        context.user_data['nombre_temp'] = texto; context.user_data['estado'] = 'esperando_sexo'
        keyboard = [[InlineKeyboardButton("♂️ Masculino", callback_data='sexo_m')], [InlineKeyboardButton("♀️ Femenino", callback_data='sexo_f')]]
        msg = await update.message.reply_text(f"Registro aceptado, **{texto}**.\n\nSelecciona tu sexo:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data['msg_pregunta_sexo'] = msg.message_id; return
    if estado == 'regalar_estrellas':
        try:
            partes = texto.split(); target_id, cantidad = int(partes[0]), int(partes[1])
            conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
            cur.execute("UPDATE usuarios SET estrellas = estrellas + %s WHERE id_telegram = %s", (cantidad, target_id))
            conn.commit(); cur.close(); conn.close()
            await update.message.reply_text(f"⭐ Has regalado {cantidad} Estrellas al ID {target_id}.")
        except: await update.message.reply_text("❌ Formato incorrecto.", parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'; return
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
    keyboard = [[KeyboardButton("⚔️ Ejecutor"), KeyboardButton("🔮 Mago"), KeyboardButton("🛡️ Guardián")], [KeyboardButton("🗡️ Asesino"), KeyboardButton("🏹 Arquero"), KeyboardButton("✨ Clérigo")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    try: await query.message.delete()
    except: pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Sexo registrado.\n\n**Elige tu clase:**", reply_markup=reply_markup, parse_mode="Markdown")

async def procesar_clase_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; clase_emoji = context.user_data.get('clase_temp', "⚔️ Ejecutor")
    nombre_elegido = context.user_data.get('nombre_temp', 'Desconocido'); sexo_elegido = context.user_data.get('sexo_temp', 'M')
    maestro_id = context.user_data.get('maestro_id', None)
    mapa_clases = {"⚔️ Ejecutor": "ejecutor", "🔮 Mago": "mago", "🛡️ Guardián": "guardian", "🗡️ Asesino": "asesino", "🏹 Arquero": "arquero", "✨ Clérigo": "clerigo"}
    clase_base = mapa_clases.get(clase_emoji, "ejecutor")
    nombres_clases = {'ejecutor': {'M': 'Ejecutor', 'F': 'Ejecutora'}, 'mago': {'M': 'Mago', 'F': 'Maga'}, 'guardian': {'M': 'Guardián', 'F': 'Guardiana'}, 'asesino': {'M': 'Asesino', 'F': 'Asesina'}, 'arquero': {'M': 'Arquero', 'F': 'Arquera'}, 'clerigo': {'M': 'Clérigo', 'F': 'Clériga'}}
    clase_final = nombres_clases.get(clase_base, nombres_clases['ejecutor'])[sexo_elegido]
    stats = {'ejecutor': {'vida': 120, 'mana': 30, 'atq': 25, 'mov': 15, 'intel': 5,  'res': 15, 'tac': 15}, 'mago': {'vida': 80,  'mana': 100,'atq': 5,  'mov': 10, 'intel': 25, 'res': 10, 'tac': 25}, 'guardian': {'vida': 180, 'mana': 40, 'atq': 10, 'mov': 5,  'intel': 10, 'res': 25, 'tac': 25}, 'asesino': {'vida': 90,  'mana': 50, 'atq': 20, 'mov': 25, 'intel': 5,  'res': 5,  'tac': 20}, 'arquero': {'vida': 100, 'mana': 60, 'atq': 15, 'mov': 20, 'intel': 10, 'res': 10, 'tac': 20}, 'clerigo': {'vida': 110, 'mana': 80, 'atq': 10, 'mov': 10, 'intel': 20, 'res': 15, 'tac': 20}}
    s = stats.get(clase_base, stats['ejecutor'])
    try: await update.message.delete()
    except: pass

    msg_trans = await context.bot.send_message(chat_id=update.effective_chat.id, text="🔮 *El Oráculo de Pollinations está forjando tu registro visual...*", parse_mode="Markdown")

    async def guardar_y_generar():
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        
        prompt_historia = (
            f"Eres 'El Sistema', una entidad fría y cruel. Escribe una historia de origen épica y oscura (máximo 3 líneas) "
            f"para un personaje llamado {nombre_elegido}, que es un {clase_final} en un mundo post-apocalíptico llamado 'El Eclipse'. "
            f"Termina con una frase del Sistema entre corchetes."
        )
        historia_ia = await narrar_con_ia(prompt_historia, f"Genera la historia para {nombre_elegido}.")
        historia_final = historia_ia if historia_ia else f"El día que el cielo se tiñó de violeta, {nombre_elegido} despertó con el poder de un {clase_final}. [Sistema: Otro más en la lista.]"
        
        cur.execute("INSERT INTO usuarios (id_telegram, nombre, clase, sexo, rango, historia, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, estrellas, maestro_id) VALUES (%s, %s, %s, %s, 'E', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s) ON CONFLICT (id_telegram) DO NOTHING", 
                    (user_id, nombre_elegido, clase_final, sexo_elegido, historia_final, s['vida'], s['vida'], s['mana'], s['mana'], s['atq'], s['mov'], s['intel'], s['res'], s['tac'], maestro_id))
        conn.commit(); cur.close(); conn.close()
        
        genero_ingles = "man" if sexo_elegido == 'M' else "woman"
        detalles_clase = {'ejecutor': "massive greatsword, dark heavy armor", 'mago': "floating crystal staff, dark robes", 'guardian': "massive spiked armor, giant shield", 'asesino': "dark hooded cloak, dual daggers", 'arquero': "glowing energy bow", 'clerigo': "ornate dark robes, glowing holy symbol"}
        detalle = detalles_clase.get(clase_base, "dark fantasy armor")
        prompt = f"{genero_ingles} {clase_final}, {detalle}"
        image_bytes = await generar_imagen_sistema(prompt, es_monstruo=False)

        texto_final = (
            f"🌑 *REGISTRO COMPLETADO*\n\n👤 Sujeto: **{nombre_elegido}**\n⚔️ Clase: **{clase_final}**\n🏅 Rango: **E** | 📊 Nivel: **1**\n\n"
            f"📖 *Historia:*\n{historia_final}\n\n❤️ Vida: {s['vida']} | 🔮 Maná: {s['mana']}\n⚔️ ATQ: {s['atq']} | 💨 MOV: {s['mov']}\n"
            f"🧠 INT: {s['intel']} | 🛡️ RES: {s['res']} | 🎯 TAC: {s['tac']}"
        )

        try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_trans.message_id)
        except: pass

        if image_bytes:
            try: await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=texto_final, parse_mode="Markdown")
            except: pass
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=texto_final, parse_mode="Markdown")

        await context.bot.send_message(chat_id=update.effective_chat.id, text="🌑 *El Sistema está listo.*", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")

    asyncio.create_task(guardar_y_generar())
    context.user_data['estado'] = 'en_menu'

async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; await limpiar_chat(update, context) 
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
        msg = await update.message.reply_text(texto, parse_mode="Markdown"); context.user_data['msg_perfil'] = msg.message_id

async def portal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT vida, energia, rango, bloqueo_hasta, nivel, clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    if user[3] and user[3] > datetime.datetime.now():
        cur.close(); conn.close()
        msg = await update.message.reply_text(f"☠️ *Estás herido.* Bloqueado.", parse_mode="Markdown"); context.user_data['msg_error'] = msg.message_id; return
    if user[1] <= 0:
        cur.close(); conn.close()
        msg = await update.message.reply_text("⚡ *Sin Energía.*", parse_mode="Markdown"); context.user_data['msg_error'] = msg.message_id; return
    nivel, clase = user[4], user[5]; rango_jugador = user[2]
    cur.execute("SELECT COUNT(*) FROM derrotados WHERE id_telegram = %s", (user_id,))
    derrotados_count = cur.fetchone()[0]
    es_jefe = False
    if rango_jugador == "E" and derrotados_count >= 5 and nivel >= 10:
        monstruo = MONSTRUOS["JEFE_E"]; es_jefe = True
    elif rango_jugador == "D" and derrotados_count >= 10 and nivel >= 20:
        monstruo = MONSTRUOS["JEFE_D"]; es_jefe = True
    elif rango_jugador == "C" and derrotados_count >= 16 and nivel >= 35:
        monstruo = MONSTRUOS["JEFE_C"]; es_jefe = True
    elif rango_jugador == "B" and derrotados_count >= 22 and nivel >= 50:
        monstruo = MONSTRUOS["JEFE_B"]; es_jefe = True
    elif rango_jugador == "A" and derrotados_count >= 27 and nivel >= 70:
        monstruo = MONSTRUOS["JEFE_A"]; es_jefe = True
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
    context.user_data['monstruo'] = monstruo; context.user_data['es_jefe'] = es_jefe
    msg_trans = await update.message.reply_text("🌀 *Abriendo portal...*", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")
    async def transicion_y_combate():
        conn_img = psycopg2.connect(DATABASE_URL, sslmode='require'); cur_img = conn_img.cursor()
        cur_img.execute("SELECT imagen FROM bestiario_imagenes WHERE nombre = %s", (monstruo['nombre'],))
        row = cur_img.fetchone()
        if row: image_bytes = bytes(row[0])
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
        keyboard = [[InlineKeyboardButton("⚔️ Atacar", callback_data='pvp_atacar_monstruo'), InlineKeyboardButton("💨 Esquivar", callback_data='pvp_esquivar_monstruo')], [InlineKeyboardButton("🔮 Habilidad", callback_data='pvp_habilidad_monstruo'), InlineKeyboardButton("🏃 Huir", callback_data='pvp_huir_monstruo')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        titulo = "👑 *JEFE FINAL*" if es_jefe else "🩸 *PORTAL ABIERTO*"
        texto = f"{titulo}\n\n**{monstruo['nombre']}** ha aparecido.\n❤️ Vida: {monstruo['hp']}\n\n*¿Qué harás?*"
        if image_bytes:
            texto_foto = f"🩸 *ENTIDAD DETECTADA*\n\n{texto}"
            try: 
                msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=texto_foto, reply_markup=reply_markup, parse_mode="Markdown")
                context.user_data['msg_combate'] = msg.message_id; context.user_data['estado'] = 'en_combate'
            except: pass
        else:
            msg = await context.bot.send_message(chat_id=update.effective_chat.id, text=texto, reply_markup=reply_markup, parse_mode="Markdown")
            context.user_data['msg_combate'] = msg.message_id; context.user_data['estado'] = 'en_combate'
    asyncio.create_task(transicion_y_combate())

async def boton_monstruo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'en_combate': return
    accion = query.data.replace('pvp_', '').replace('_monstruo', '')
    
    user_id = update.effective_user.id
    monstruo = context.user_data.get('monstruo', {"nombre": "Karu", "hp": 100, "exp": 100, "atk": 10, "grupo": "A"})
    es_jefe = context.user_data.get('es_jefe', False); msg_combate_id = context.user_data.get('msg_combate')
    
    try: await query.edit_message_caption(caption="⏳ *Calculando destino...*", parse_mode="Markdown")
    except: 
        try: await query.edit_message_text(text="⏳ *Calculando destino...*", parse_mode="Markdown")
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
            narr = "🌑 *Has escapado.* La oscuridad del portal se cierra tras de ti. No hay recompensa, pero vives."
            try: await query.edit_message_caption(caption=narr, parse_mode="Markdown")
            except: await query.edit_message_text(text=narr, parse_mode="Markdown")
            if msg_combate_id:
                try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_combate_id)
                except: pass
            context.user_data['estado'] = 'en_menu'; await context.bot.send_message(chat_id=update.effective_chat.id, text="🌑 *Has vuelto al Refugio.*", reply_markup=obtener_menu_fijo()); return
        else:
            dano_recibido = monstruo['atk'] + random.randint(1, 5); vida -= dano_recibido
            accion_texto = f"{nombre} intenta huir."; result_texto = f"Falla. {dano_recibido} de daño."
    elif accion == 'esquivar':
        if random.randint(1, 100) <= (mov * 3): accion_texto = f"{nombre} esquiva."; result_texto = "Sin daño."
        else:
            dano_recibido = monstruo['atk'] - random.randint(1, 5)
            if dano_recibido < 1: dano_recibido = 1
            vida -= dano_recibido; accion_texto = f"{nombre} intenta esquivar."; result_texto = f"Falla. {dano_recibido} de daño."
    else:
        if accion == 'atacar': dano = atq + random.randint(1, 10); accion_texto = f"{nombre} ataca."
        else:
            costo_mana = 10
            if mana >= costo_mana:
                mana -= costo_mana; stat = intel if clase in ['Mago', 'Maga'] else atq
                dano = int((stat * 1.5) + random.randint(5, 15)); accion_texto = f"{nombre} usa su habilidad."
            else: dano = 0; accion_texto = f"{nombre} intenta usar su habilidad."; result_texto = "MANÁ INSUFICIENTE."
        if dano > 0:
            mult = calcular_dano_faccion(clase, monstruo['grupo']); dano = int(dano * mult)
            if mult == 1.5: accion_texto += " ¡Debilidad detectada! "
            elif mult == 0.5: accion_texto += " Ataque resistido. "
        hp_monstruo -= dano
        if hp_monstruo < 0: hp_monstruo = 0
        if dano > 0:
            result_texto = f"{dano} de daño infligido."
            if hp_monstruo > 0:
                dano_recibido = monstruo['atk'] + random.randint(1, 5); vida -= dano_recibido; result_texto += f" {dano_recibido} de daño recibido."
    if vida < 0: vida = 0
    
    prompt_sistema = (
        "Eres 'El Sistema', una entidad fría, calculadora y sádica de un RPG oscuro. "
        "Narra la acción del jugador y el contraataque del monstruo en un párrafo corto (máximo 3 líneas). "
        "Describe el dolor, la sangre y el sonido de los huesos. No seas amable. "
        "Habla como si el jugador fuera un insecto. Si el jugador falla, búrlate de él. "
        "Termina siempre con una frase corta del Sistema entre corchetes."
    )
    contexto_ia = f"Acción: {accion_texto}. Resultado: {result_texto}."
    narracion_epica = await narrar_con_ia(prompt_sistema, contexto_ia)
    if not narracion_epica: narracion_epica = "El Sistema registra el impacto en silencio. [Sistema: Patético.]"
    
    if hp_monstruo <= 0:
        if es_jefe:
            narracion_epica += f"\n\n👑 **HAS DERROTADO AL JEFE FINAL.**\nEl Sistema te permite ascender al siguiente Rango."
            nuevo_rango = 'D'
            if rango == 'D': nuevo_rango = 'C'
            elif rango == 'C': nuevo_rango = 'B'
            elif rango == 'B': nuevo_rango = 'A'
            elif rango == 'A': nuevo_rango = 'S'
            cur.execute("UPDATE usuarios SET rango = %s, vida = %s, mana = %s, en_combate = FALSE, energia = 5 WHERE id_telegram = %s", (nuevo_rango, vida, mana, user_id))
        else:
            mult_exp = calcular_multiplicador_exp(clase, monstruo['grupo'])
            exp_ganada = int(monstruo['exp'] * mult_exp)
            narracion_epica += f"\n\n💀 **{monstruo['nombre']} ha muerto.**\n🌟 *+{exp_ganada} EXP.*"
            exp += exp_ganada; nuevo_rango = rango
            exp_necesaria = nivel * 100
            if exp >= exp_necesaria:
                exp -= exp_necesaria; nivel += 1; vida_max += 20; vida = vida_max; atq += 2; mov += 1; intel += 2
                narracion_epica += f"\n\n⬆️ **¡NIVEL {nivel}!**"
                cur.execute("SELECT maestro_id FROM usuarios WHERE id_telegram = %s", (user_id,))
                maestro = cur.fetchone()[0]
                if maestro: cur.execute("UPDATE usuarios SET estrellas = estrellas + 5 WHERE id_telegram = %s", (maestro,))
            cur.execute("INSERT INTO derrotados (id_telegram, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, monstruo['nombre']))
            cur.execute("UPDATE usuarios SET vida = %s, vida_max = %s, mana = %s, atq = %s, mov = %s, intel = %s, exp = %s, nivel = %s, rango = %s, en_combate = FALSE, energia = 5 WHERE id_telegram = %s", (vida, vida_max, mana, atq, mov, intel, exp, nivel, nuevo_rango, user_id))
        conn.commit(); cur.close(); conn.close()
        if msg_combate_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_combate_id)
            except: pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{narracion_epica}\n\n🌑 *El Sistema te devuelve al Refugio.*", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'; return
    if vida <= 0:
        narracion_epica += f"\n\n☠️ **Has muerto.** El Sistema te castiga con 1 hora de bloqueo."
        bloqueo = datetime.datetime.now() + datetime.timedelta(hours=1)
        cur.execute("UPDATE usuarios SET vida = 0, en_combate = FALSE, bloqueo_hasta = %s WHERE id_telegram = %s", (bloqueo, user_id))
        conn.commit(); cur.close(); conn.close()
        if msg_combate_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_combate_id)
            except: pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{narracion_epica}\n\n🌑 *Castigo del Sistema.*", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'; return
    cur.execute("UPDATE usuarios SET vida = %s, mana = %s, monstruo_hp = %s WHERE id_telegram = %s", (vida, mana, hp_monstruo, user_id))
    conn.commit(); cur.close(); conn.close()
    texto_combate = f"{narracion_epica}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}\n🩸 {monstruo['nombre']}: {hp_monstruo}"
    keyboard = [[InlineKeyboardButton("⚔️ Atacar", callback_data='pvp_atacar_monstruo'), InlineKeyboardButton("💨 Esquivar", callback_data='pvp_esquivar_monstruo')], [InlineKeyboardButton("🔮 Habilidad", callback_data='pvp_habilidad_monstruo'), InlineKeyboardButton("🏃 Huir", callback_data='pvp_huir_monstruo')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if msg_combate_id:
        try: await query.edit_message_caption(caption=texto_combate, reply_markup=reply_markup, parse_mode="Markdown")
        except: 
            try: await query.edit_message_text(text=texto_combate, reply_markup=reply_markup, parse_mode="Markdown")
            except: pass

async def tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        msg = query.message
    else:
        msg = await update.message.reply_text("Cargando...")
        
    user_id = update.effective_user.id
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    estrellas = cur.fetchone()[0]; cur.close(); conn.close()
    
    keyboard = [
        [InlineKeyboardButton("🧪 POCIONES", callback_data='tienda_pociones')],
        [InlineKeyboardButton("⚔️ ARMERÍA", callback_data='tienda_armeria')],
        [InlineKeyboardButton("🎁 CAJAS MISTERIOSAS", callback_data='tienda_cajas')],
        [InlineKeyboardButton("🔙 VOLVER AL MENÚ", callback_data='volver_menu')]
    ]
    texto = f"🛒 *MERCADO DEL SISTEMA*\n⭐ Estrellas: **{estrellas}**\n\nElige una categoría:"
    
    try:
        await msg.edit_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except: pass

async def tienda_pociones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    texto = ("🧪 *POCIONES*\n\n• *Poción de Vida (5⭐):* Restaura 50 HP.\n• *Poción de Maná (5⭐):* Restaura 50 MP.\n• *Elixir Completo (15⭐):* Restaura todo.")
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
    texto = ("🎁 *CAJAS MISTERIOSAS*\n\n• *Caja Común (10⭐):* 80% Poción | 20% Estrellas de vuelta.\n• *Cofre Épico (30⭐):* 100% Elixir Completo (vale 15⭐).")
    keyboard = [[InlineKeyboardButton("📦 Comprar Caja Común - 10⭐", callback_data='comprar_caja_comun')], [InlineKeyboardButton("🎁 Comprar Cofre Épico - 30⭐", callback_data='comprar_cofre_epico')], [InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    try: await query.message.delete()
    except: pass
    
    item = query.data.replace('comprar_', '')
    user_id = update.effective_user.id
    
    precios = {'pocion_vida': 5, 'pocion_mana': 5, 'elixir': 15, 'caja_comun': 10, 'cofre_epico': 30}
    
    if item.startswith("arma_"):
        partes = item.split("_")
        nombre_arma = partes[1]
        clase_original = partes[2]
        precio = 15
        for c, armas_lista in ARMAS.items():
            for a in armas_lista:
                if a['nombre'] == nombre_arma:
                    precio = a['precio']
                    break
        item_nombre = nombre_arma
        es_arma = True
    else:
        precio = precios.get(item, 0)
        item_nombre = item.replace('_', ' ').title()
        es_arma = False

    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    estrellas_virtuales = cur.fetchone()[0]
    
    if estrellas_virtuales < precio:
        cur.close(); conn.close()
        keyboard = [
            [InlineKeyboardButton("⭐ Pagar con Telegram (Reales)", callback_data=f"pago_real_{item}")],
            [InlineKeyboardButton("🔙 Volver a la Tienda", callback_data='menu_tienda')]
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ *Estrellas del Sistema insuficientes.*\n\nNecesitas **{precio}⭐** para comprar **{item_nombre}**.\nSolo tienes **{estrellas_virtuales}⭐** en tu cuenta.\n\n¿Quieres usar Estrellas Reales de Telegram para pagar?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

    cur.execute("UPDATE usuarios SET estrellas = estrellas - %s WHERE id_telegram = %s", (precio, user_id))
    
    if es_arma:
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, stat_bonus, clase_original, cantidad) VALUES (%s, %s, 'arma', 5, %s, 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id, nombre_arma, clase_original))
        msg = f"✅ Has comprado **{nombre_arma}** con Estrellas del Sistema."
    elif item == 'pocion_vida':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Poción de Vida', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,))
        msg = "✅ Has comprado **Poción de Vida**."
    elif item == 'pocion_mana':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Poción de Maná', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,))
        msg = "✅ Has comprado **Poción de Maná**."
    elif item == 'elixir':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Elixir Completo', 'pocion', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,))
        msg = "✅ Has comprado **Elixir Completo**."
    elif item == 'caja_comun':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Caja Común', 'caja', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,))
        msg = "✅ Has comprado **Caja Común**."
    elif item == 'cofre_epico':
        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) VALUES (%s, 'Cofre Épico', 'caja', 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id,))
        msg = "✅ Has comprado **Cofre Épico**."
    
    conn.commit(); cur.close(); conn.close()
    
    keyboard = [[InlineKeyboardButton("🔙 Volver a la Tienda", callback_data='menu_tienda')]]
    await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def pago_real(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    try: await query.message.delete()
    except: pass
    
    item = query.data.replace('pago_real_', '')
    precios = {'pocion_vida': 5, 'pocion_mana': 5, 'elixir': 15, 'caja_comun': 10, 'cofre_epico': 30}
    if item.startswith("arma_"):
        partes = item.split("_")
        nombre_arma = partes[1]
        precio = 15
        for c, armas_lista in ARMAS.items():
            for a in armas_lista:
                if a['nombre'] == nombre_arma:
                    precio = a['precio']
                    break
        item_nombre = nombre_arma
    else:
        precio = precios.get(item, 0)
        item_nombre = item.replace('_', ' ').title()

    await enviar_factura(update, context, item_nombre, precio, item)

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
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🌑 *El Sistema está listo.*", reply_markup=obtener_menu_fijo())

async def creador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ID_CREADOR: return
    keyboard = [
        [InlineKeyboardButton("👑 Invocar Jefe Supremo", callback_data='admin_jefe')],
        [InlineKeyboardButton("🏆 Ver Ranking (Grupo)", callback_data='admin_ranking')],
        [InlineKeyboardButton("🔄 Resetear Temporada", callback_data='admin_reset')],
        [InlineKeyboardButton("⭐ Regalar Estrellas", callback_data='admin_regalar_estrellas')]
    ]
    await update.message.reply_text("👑 *PANEL DEL CREADOR*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def boton_creador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if update.effective_user.id != ID_CREADOR: return
    if query.data == 'admin_jefe':
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("INSERT INTO jefe_supremo (id, nombre, vida, vida_max, activo) VALUES (1, 'El Devorador', 100000, 100000, TRUE) ON CONFLICT (id) DO UPDATE SET vida = 100000, activo = TRUE")
        conn.commit(); cur.close(); conn.close()
        try:
            await context.bot.send_message(chat_id=ID_GRUPO, text="👑 *ALERTA MÁXIMA*\n\nEl Jefe Supremo ha despertado. **El Devorador** tiene 100,000 de Vida.\nEntra a tu privado con el bot. Un botón de ataque aparecerá en tu menú.", parse_mode="Markdown")
        except: pass
        await query.edit_message_text("👑 Jefe invocado en el grupo.")
    elif query.data == 'admin_ranking':
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("SELECT nombre, clase, nivel, rango FROM usuarios ORDER BY nivel DESC, exp DESC LIMIT 10")
        top = cur.fetchall(); cur.close(); conn.close()
        if not top: await query.edit_message_text("No hay registros."); return
        texto = "🏆 *RANKING DE LA TEMPORADA*\n\n"
        for i, user in enumerate(top): texto += f"{i+1}. **{user[0]}** - {user[1]} (Nv. {user[2]} | Rango {user[3]})\n"
        try:
            await context.bot.send_message(chat_id=ID_GRUPO, text=texto, parse_mode="Markdown")
            await query.edit_message_text("🏆 Ranking enviado al grupo.")
        except: await query.edit_message_text("❌ Error: Revisa que el bot sea administrador del grupo.")
    elif query.data == 'admin_reset':
        keyboard = [[InlineKeyboardButton("☠️ CONFIRMAR BORRADO", callback_data='admin_reset_confirm')]]
        await query.edit_message_text("⚠️ ¿Estás seguro de que quieres borrar a TODOS los jugadores y empezar la Temporada 2?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif query.data == 'admin_reset_confirm':
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("SELECT valor FROM config WHERE clave = 'temporada'")
        temporada_actual = cur.fetchone()[0]
        
        cur.execute("SELECT nombre, clase, nivel FROM usuarios ORDER BY nivel DESC, exp DESC LIMIT 3")
        top3 = cur.fetchall()
        for i, user in enumerate(top3):
            logro = f"Top {i+1} de la Temporada {temporada_actual}"
            cur.execute("INSERT INTO leyendas (temporada, nombre, clase, logro) VALUES (%s, %s, %s, %s)", (temporada_actual, user[0], user[1], logro))
        
        cur.execute("SELECT id_telegram FROM usuarios ORDER BY nivel DESC, exp DESC LIMIT 3")
        ids_top3 = cur.fetchall()
        if len(ids_top3) >= 1: cur.execute("UPDATE usuarios SET estrellas = estrellas + 50 WHERE id_telegram = %s", (ids_top3[0][0],))
        if len(ids_top3) >= 2: cur.execute("UPDATE usuarios SET estrellas = estrellas + 30 WHERE id_telegram = %s", (ids_top3[1][0],))
        if len(ids_top3) >= 3: cur.execute("UPDATE usuarios SET estrellas = estrellas + 20 WHERE id_telegram = %s", (ids_top3[2][0],))

        cur.execute("INSERT INTO inventario (id_telegram, item, tipo, cantidad) SELECT id_telegram, 'Caja Común', 'caja', 1 FROM usuarios ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1")
        
        cur.execute("TRUNCATE TABLE usuarios;")
        cur.execute("TRUNCATE TABLE derrotados;")
        cur.execute("UPDATE jefe_supremo SET activo = FALSE")
        cur.execute("UPDATE config SET valor = valor + 1 WHERE clave = 'temporada'")
        
        conn.commit(); cur.close(); conn.close()
        
        nueva_temp = temporada_actual + 1
        try: 
            await context.bot.send_message(
                chat_id=ID_GRUPO, 
                text=f"🌑 *EL ECLIPSE HA TERMINADO*\n\nEl Jefe Supremo ha caído. Los registros han sido borrados.\n\nLa Temporada {nueva_temp} comienza ahora. Todos los Cazadores han recibido una Caja Misteriosa de despedida.", 
                parse_mode="Markdown"
            )
        except: pass
        
        await query.edit_message_text(f"✅ Temporada {nueva_temp} reiniciada y recompensas entregadas.")
    elif query.data == 'admin_regalar_estrellas':
        await query.edit_message_text("Escribe ID y cantidad (ej: `6985217869 100`).", parse_mode="Markdown")
        context.user_data['estado'] = 'regalar_estrellas'

async def atacar_jefe_boton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user_id = update.effective_user.id
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT vida, activo FROM jefe_supremo WHERE id = 1")
    jefe = cur.fetchone()
    if not jefe or not jefe[1] or jefe[0] <= 0:
        cur.close(); conn.close()
        await query.edit_message_text("🌑 El Jefe Supremo ya ha sido derrotado o no está activo.", parse_mode="Markdown"); return
    cur.execute("SELECT clase, atq, intel, nombre FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    if not user: cur.close(); conn.close(); return
    clase, atq, intel, nombre = user
    dano = intel * 2 if 'Mago' in clase else atq * 2
    dano = int(dano * random.uniform(1.0, 1.5))
    nueva_vida_jefe = max(0, jefe[0] - dano)
    cur.execute("UPDATE jefe_supremo SET vida = %s WHERE id = 1", (nueva_vida_jefe,))
    conn.commit(); cur.close(); conn.close()
    keyboard = [[InlineKeyboardButton("⚔️ Atacar de nuevo", callback_data='atacar_jefe_btn')]]
    texto = (f"🩸 *ATAQUE AL JEFE SUPREMO*\n\nEl Sujeto **{nombre}** ha infligido **{dano} de daño** al Devorador.\n"
             f"❤️ Vida Global del Jefe: **{nueva_vida_jefe} / 100,000**\n\n")
    if nueva_vida_jefe <= 0:
        texto += "💀 **¡EL JEFE SUPREMO HA SIDO ERRADICADO!**\nEl Eclipse ha terminado. Prepárense para el reset."
        keyboard = []
        
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("SELECT nombre FROM usuarios WHERE id_telegram = %s", (user_id,))
        nombre_mvp = cur.fetchone()[0]
        
        cur.execute("INSERT INTO leyendas (temporada, nombre, clase, logro) VALUES (1, %s, 'Cazador', 'Asestó el golpe final al Jefe Supremo')", (nombre_mvp,))
        cur.execute("UPDATE usuarios SET estrellas = estrellas + 100 WHERE id_telegram = %s", (user_id,))
        conn.commit(); cur.close(); conn.close()
        
        try:
            await context.bot.send_message(chat_id=user_id, text=f"👑 *EL SISTEMA TE RECONOCE*\n\nHas asestado el golpe final al Jefe Supremo. La gloria es tuya.\n\n⭐ *Recompensa:* +100 Estrellas virtuales.\n🏆 *Título:* MVP de la Temporada 1.\n\n*El Creador se contactará contigo para tu regalo real.*", parse_mode="Markdown")
        except: pass
        
        try:
            await context.bot.send_message(chat_id=ID_GRUPO, text=f"👑 *EL JEFE SUPREMO HA CAÍDO*\n\nEl golpe final fue asestado por **{nombre_mvp}**.\nEl Sistema lo reconoce como el MVP de la temporada.\n\n*Prepárense. El mundo se reiniciará pronto.*", parse_mode="Markdown")
        except: pass
    else: texto += "*El Sistema registra tu ataque. Sigue peleando.*"
    await query.edit_message_text(texto, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="Markdown")

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
    app.add_handler(CommandHandler("atacar_jefe", atacar_jefe_boton))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, pago_exitoso))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Sticker.ALL | filters.AUDIO) & ~filters.COMMAND, manejar_mensajes))
    app.add_handler(CallbackQueryHandler(boton_sexo, pattern='^sexo_'))
    app.add_handler(CallbackQueryHandler(boton_creador, pattern='^admin_'))
    app.add_handler(CallbackQueryHandler(atacar_jefe_boton, pattern='^atacar_jefe_btn$'))
    app.add_handler(CallbackQueryHandler(boton_monstruo, pattern='^pvp_'))
    app.add_handler(CallbackQueryHandler(tienda_pociones, pattern='^tienda_pociones$'))
    app.add_handler(CallbackQueryHandler(tienda_armeria, pattern='^tienda_armeria$'))
    app.add_handler(CallbackQueryHandler(armeria_categoria, pattern='^armeria_'))
    app.add_handler(CallbackQueryHandler(tienda_cajas, pattern='^tienda_cajas$'))
    app.add_handler(CallbackQueryHandler(comprar, pattern='^comprar_'))
    app.add_handler(CallbackQueryHandler(pago_real, pattern='^pago_real_'))
    app.add_handler(CallbackQueryHandler(equipar_arma, pattern='^equipar_'))
    app.add_handler(CallbackQueryHandler(volver_menu, pattern='^volver_menu$'))
    app.add_handler(CallbackQueryHandler(tienda, pattern='^menu_tienda$'))
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
