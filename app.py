import os
import threading
import psycopg2
import urllib.parse
import random
import asyncio
import datetime
import aiohttp
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))
ID_CREADOR = 6985217869

# --- BESTIARIO ---
MONSTRUOS = {
    "E": [
        {"nombre": "Karu, el Registrado", "hp": 100, "atk": 10, "exp": 100, "debilidad": "Mago", "resistencia": "Ejecutor"},
        {"nombre": "Vex, Sujeto 07", "hp": 120, "atk": 12, "exp": 120, "debilidad": "Arquero", "resistencia": "Asesino"},
        {"nombre": "Kael, Eco del Portal", "hp": 90, "atk": 15, "exp": 110, "debilidad": "Clérigo", "resistencia": "Mago"},
        {"nombre": "Zeth, Larva del Umbral", "hp": 80, "atk": 8, "exp": 90, "debilidad": "Ejecutor", "resistencia": "Arquero"},
        {"nombre": "Rakan, Colmillo Rojo", "hp": 130, "atk": 14, "exp": 130, "debilidad": "Guardián", "resistencia": "Clérigo"}
    ]
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
        cur.execute("CREATE TABLE IF NOT EXISTS inventario (id_telegram BIGINT, item VARCHAR(50), tipo VARCHAR(20), stat_bonus INT, cantidad INT DEFAULT 1, PRIMARY KEY (id_telegram, item));")
        cur.execute("DROP TABLE IF EXISTS derrotados;")
        cur.execute("CREATE TABLE IF NOT EXISTS derrotados (id_telegram BIGINT, nombre VARCHAR(100), PRIMARY KEY (id_telegram, nombre));")
        conn.commit(); cur.close(); conn.close()
        print("✅ Base de datos lista.")
    except Exception as e: print(f"❌ ERROR BD: {e}")

# --- NARRADOR (POLLINATIONS TEXTO) ---
async def narrar_con_ia(prompt_sistema, contexto):
    url = "https://text.pollinations.ai/openai"
    payload = {"model": "openai", "messages": [{"role": "system", "content": prompt_sistema}, {"role": "user", "content": contexto}], "max_tokens": 100}
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content'].strip().replace('*', '').replace('_', '')
                return None
    except: return None

# --- GENERADOR DE IMAGEN (CON SELLO DE POLLINATIONS) ---
async def generar_imagen_sistema(prompt):
    # URL pública (sale con la marca del Consejo)
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=512&height=512&nologo=false&model=flux"
    try:
        timeout = aiohttp.ClientTimeout(total=40)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                return None
    except Exception as e: 
        print(f"❌ Error Imagen: {e}")
        return None

# --- LIMPIAR CHAT ---
async def limpiar_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for clave in ['msg_bienvenida', 'msg_error', 'msg_perfil', 'msg_combate', 'msg_tienda', 'msg_creador', 'msg_pregunta_sexo', 'msg_pregunta_clase']:
        msg_id = context.user_data.get(clave)
        if msg_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except: pass
    if update.message:
        try: await update.message.delete()
        except: pass

def obtener_menu_fijo():
    return ReplyKeyboardMarkup([[KeyboardButton("👤 Perfil"), KeyboardButton("🩸 Portal")], [KeyboardButton("🛒 Tienda"), KeyboardButton("🎒 Inventario")]], resize_keyboard=True)

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    if resultado and resultado[0] is not None:
        cur.close(); conn.close()
        msg = await update.message.reply_text("🌑 *Regreso detectado.*\nUsa los botones de abajo.", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
        context.user_data['msg_bienvenida'] = msg.message_id
        return
    context.user_data['estado'] = 'esperando_nombre'
    msg = await update.message.reply_text("🌑 *El Sistema te ha detectado.*\n\n**¿Cuál es tu nombre, Sujeto?**", parse_mode="Markdown")
    context.user_data['msg_bienvenida'] = msg.message_id
    cur.close(); conn.close()

# --- MANEJADOR DE MENSAJES ---
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
        except: await update.message.reply_text("❌ Formato incorrecto. Usa: `ID CANTIDAD`", parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'
        return

    if estado == 'en_combate' and texto:
        context.user_data['frase_epica'] = texto
        try: await update.message.delete()
        except: pass
        return

# --- BOTONES DE SEXO Y CLASE ---
async def boton_sexo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'esperando_sexo': return
    context.user_data['sexo_temp'] = "M" if query.data == 'sexo_m' else "F"
    context.user_data['estado'] = 'esperando_clase'
    keyboard = [[InlineKeyboardButton("⚔️ Ejecutor/a", callback_data='clase_ejecutor')], [InlineKeyboardButton("🔮 Mago/a", callback_data='clase_mago')], [InlineKeyboardButton("🛡️ Guardián/na", callback_data='clase_guardian')], [InlineKeyboardButton("🗡️ Asesino/a", callback_data='clase_asesino')], [InlineKeyboardButton("🏹 Arquero/a", callback_data='clase_arquero')], [InlineKeyboardButton("✨ Clérigo/a", callback_data='clase_clerigo')]]
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
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Usa los botones de abajo.", reply_markup=obtener_menu_fijo())
    context.user_data['estado'] = 'en_menu'

    async def guardar_y_generar():
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        prompt_historia = f"Eres 'El Sistema'. Escribe una historia de origen épica y oscura (máximo 3 líneas) para un personaje llamado {nombre_elegido}, que es un {clase_final} en un mundo post-apocalíptico llamado 'El Eclipse'."
        historia_ia = await narrar_con_ia(prompt_historia, f"Genera la historia para {nombre_elegido}.")
        historia_final = historia_ia if historia_ia else f"El día que el cielo se tiñó de violeta, {nombre_elegido} despertó con el poder de un {clase_final}."
        
        cur.execute("INSERT INTO usuarios (id_telegram, nombre, clase, sexo, rango, historia, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, estrellas) VALUES (%s, %s, %s, %s, 'E', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0) ON CONFLICT (id_telegram) DO NOTHING", 
                    (user_id, nombre_elegido, clase_final, sexo_elegido, historia_final, s['vida'], s['vida'], s['mana'], s['mana'], s['atq'], s['mov'], s['intel'], s['res'], s['tac']))
        conn.commit(); cur.close(); conn.close()

        genero_ingles = "man" if sexo_elegido == 'M' else "woman"
        detalles_clase = {'ejecutor': "massive greatsword, dark heavy armor, neon purple accents", 'mago': "floating crystal staff, dark robes, glowing runes", 'guardian': "massive spiked armor, giant shield", 'asesino': "dark hooded cloak, dual daggers", 'arquero': "glowing energy bow, light leather armor", 'clerigo': "ornate dark robes, glowing holy symbol"}
        detalle = detalles_clase.get(clase_base, "dark fantasy armor")
        prompt = f"Epic dark fantasy portrait of a {genero_ingles} {clase_final}, {detalle}, dark atmosphere, neon purple glow"
        
        image_bytes = await generar_imagen_sistema(prompt)
        
        # --- LORE POLLINATIONS ---
        texto_foto = (
            f"🌑 *REGISTRO VISUAL - FACCIÓN POLLINATIONS*\n\n"
            f"👤 Sujeto: **{nombre_elegido}**\n\n"
            f"📖 *Historia:*\n{historia_final}\n\n"
            f"⚠️ *Marca de Pollinations:* El sello en la imagen es la firma del Consejo de Naciones. Significa que tu forma física ha sido escaneada y que tus actos serán juzgados."
        )
        
        if image_bytes:
            try: await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=texto_foto, parse_mode="Markdown")
            except: pass

    asyncio.create_task(guardar_y_generar())

# --- PERFIL ---
async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context) 
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, historia, energia, estrellas, arma_equipada FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone(); cur.close(); conn.close()
    if user:
        (nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, historia, energia, estrellas, arma_equipada) = user
        icono_sexo = "♂️" if sexo == 'M' else "♀️"
        texto = (f"🌑 *FICHA DEL SISTEMA*\n\n👤 Sujeto: **{nombre}**\n⚔️ Clase: **{clase}**\n{icono_sexo} Sexo: **{'Masculino' if sexo == 'M' else 'Femenino'}**\n"
            f"🏅 Rango: **{rango}** | 📊 Nivel: **{nivel}** (EXP: {exp}/{nivel*100})\n\n📖 *Historia:*\n{historia}\n\n"
            f"🗡️ Arma: **{arma_equipada}**\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}/{mana_max}\n"
            f"⚔️ ATQ: {atq} | 💨 MOV: {mov} | 🧠 INT: {intel}\n🛡️ RES: {res} | 🎯 TAC: {tac}\n\n⚡ *Energía:* {energia}/5 | ⭐ *Estrellas:* {estrellas}")
        msg = await update.message.reply_text(texto, parse_mode="Markdown")
        context.user_data['msg_perfil'] = msg.message_id

# --- PORTAL ---
async def portal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT vida, energia, rango, bloqueo_hasta FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    if user[3] and user[3] > datetime.datetime.now():
        cur.close(); conn.close()
        msg = await update.message.reply_text(f"☠️ *Estás herido.* Bloqueado.", parse_mode="Markdown"); context.user_data['msg_error'] = msg.message_id; return
    if user[1] <= 0:
        cur.close(); conn.close()
        msg = await update.message.reply_text("⚡ *Sin Energía.*", parse_mode="Markdown"); context.user_data['msg_error'] = msg.message_id; return
    rango_jugador = user[2]
    enemigos_rango = MONSTRUOS.get(rango_jugador, MONSTRUOS["E"])
    cur.execute("SELECT nombre FROM derrotados WHERE id_telegram = %s", (user_id,))
    derrotados = [row[0] for row in cur.fetchall()]
    disponibles = [e for e in enemigos_rango if e['nombre'] not in derrotados]
    if not disponibles:
        msg = await update.message.reply_text("🌑 *Has derrotado a todos.*", parse_mode="Markdown"); cur.close(); conn.close(); return
    monstruo = random.choice(disponibles)
    cur.execute("UPDATE usuarios SET en_combate = TRUE, monstruo_hp = %s, monstruo_nombre = %s, energia = energia - 1 WHERE id_telegram = %s", (monstruo['hp'], monstruo['nombre'], user_id))
    conn.commit(); cur.close(); conn.close()
    context.user_data['estado'] = 'en_combate'; context.user_data['monstruo'] = monstruo
    
    keyboard = [[InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar'), InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')], [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad'), InlineKeyboardButton("🏃 Huir", callback_data='combate_huir')]]
    
    msg = await update.message.reply_text(f"🩸 *PORTAL ABIERTO*\n\n**{monstruo['nombre']}** ha aparecido.\n❤️ Vida: {monstruo['hp']}\n\n*¿Qué harás?*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    context.user_data['msg_combate'] = msg.message_id
    
    async def enviar_foto_monstruo():
        prompt_m = f"epic dark fantasy monster {monstruo['nombre']}, purple neon portal background, cinematic"
        image_bytes = await generar_imagen_sistema(prompt_m)
        if image_bytes:
            texto_foto = f"🩸 *ENTIDAD DETECTADA POR POLLINATIONS*\n\n*El Consejo de Naciones ha escaneado a esta criatura. La marca en la imagen es el código de barras de su existencia.*"
            try: await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_bytes, caption=texto_foto, parse_mode="Markdown")
            except: pass
    asyncio.create_task(enviar_foto_monstruo())

async def boton_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'en_combate': return
    accion = query.data.replace('combate_', '')
    user_id = update.effective_user.id
    frase = context.user_data.get('frase_epica', ''); context.user_data['frase_epica'] = ''
    monstruo = context.user_data.get('monstruo', {"nombre": "Karu", "hp": 100, "exp": 100, "atk": 10, "debilidad": "Mago", "resistencia": "Ejecutor"})
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
            await query.edit_message_text("🌑 *Has vuelto al Refugio.*", parse_mode="Markdown")
            context.user_data['estado'] = 'en_menu'; await context.bot.send_message(chat_id=update.effective_chat.id, text="Usa los botones de abajo.", reply_markup=obtener_menu_fijo()); return
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
        if accion == 'atacar': dano = atq + random.randint(1, 10); accion_texto = f"{nombre} ataca."
        else:
            costo_mana = 10
            if mana >= costo_mana:
                mana -= costo_mana; stat = intel if clase in ['Mago', 'Maga'] else atq
                dano = int((stat * 1.5) + random.randint(5, 15)); accion_texto = f"{nombre} usa su habilidad."
            else: 
                dano = 0
                accion_texto = f"{nombre} intenta usar su habilidad."
                result_texto = "El Sistema bloquea el ataque: MANÁ INSUFICIENTE. El Sujeto debe atacar físicamente o usar una poción."
        if dano > 0:
            clase_limpia = clase.replace("a", "").replace("á", "").capitalize()
            if monstruo['debilidad'] in clase_limpia or clase_limpia in monstruo['debilidad']: dano = int(dano * 1.5)
            elif monstruo['resistencia'] in clase_limpia or clase_limpia in monstruo['resistencia']: dano = int(dano * 0.5)
        hp_monstruo -= dano
        if hp_monstruo < 0: hp_monstruo = 0
        if dano > 0:
            result_texto = f"{dano} de daño infligido."
            if hp_monstruo > 0:
                dano_recibido = monstruo['atk'] + random.randint(1, 5); vida -= dano_recibido; result_texto += f" {dano_recibido} de daño recibido."
    if vida < 0: vida = 0
    contexto_ia = f"Acción: {accion_texto}. Resultado: {result_texto}." + (f" Gritó: '{frase}'." if frase else "")
    narracion_epica = await narrar_con_ia("Eres 'El Sistema', frío y brutal. Narra la acción en 3 líneas.", contexto_ia)
    if not narracion_epica: narracion_epica = "El Sistema registra el impacto en silencio."
    if hp_monstruo <= 0:
        exp_ganada = int(monstruo['exp'] * (1 / nivel)) if nivel > 1 else monstruo['exp']
        narracion_epica += f"\n\n💀 **{monstruo['nombre']} ha muerto.**\n🌟 *+{exp_ganada} EXP.*"
        exp += exp_ganada; nuevo_rango = rango
        if exp >= nivel * 100:
            exp -= nivel * 100; nivel += 1; vida_max += 20; vida = vida_max; atq += 2; mov += 1; intel += 2
            if nivel == 11: nuevo_rango = 'D'
            narracion_epica += f"\n\n⬆️ **¡NIVEL {nivel}!**"
        cur.execute("INSERT INTO derrotados (id_telegram, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, monstruo['nombre']))
        cur.execute("UPDATE usuarios SET vida = %s, vida_max = %s, mana = %s, atq = %s, mov = %s, intel = %s, exp = %s, nivel = %s, rango = %s, en_combate = FALSE, energia = 5 WHERE id_telegram = %s", (vida, vida_max, mana, atq, mov, intel, exp, nivel, nuevo_rango, user_id))
        conn.commit(); cur.close(); conn.close()
        await query.edit_message_text(f"{narracion_epica}\n\n🌑 *Refugio.*", parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'; await context.bot.send_message(chat_id=update.effective_chat.id, text="Menú activado.", reply_markup=obtener_menu_fijo()); return
    if vida <= 0:
        narracion_epica += f"\n\n☠️ **Has muerto.** Bloqueado 1 hora."
        bloqueo = datetime.datetime.now() + datetime.timedelta(hours=1)
        cur.execute("UPDATE usuarios SET vida = 0, en_combate = FALSE, bloqueo_hasta = %s WHERE id_telegram = %s", (bloqueo, user_id))
        conn.commit(); cur.close(); conn.close()
        await query.edit_message_text(f"{narracion_epica}\n\n🌑 *Castigo.*", parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'; await context.bot.send_message(chat_id=update.effective_chat.id, text="Menú activado.", reply_markup=obtener_menu_fijo()); return
    cur.execute("UPDATE usuarios SET vida = %s, mana = %s, monstruo_hp = %s WHERE id_telegram = %s", (vida, mana, hp_monstruo, user_id))
    conn.commit(); cur.close(); conn.close()
    keyboard = [[InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar'), InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')], [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad'), InlineKeyboardButton("🏃 Huir", callback_data='combate_huir')]]
    await query.edit_message_text(f"{narracion_epica}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}\n🩸 {monstruo['nombre']}: {hp_monstruo}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- TIENDA, INVENTARIO Y CREADOR (Iguales, sin cambios) ---
async def tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    estrellas = cur.fetchone()[0]; cur.close(); conn.close()
    keyboard = [[InlineKeyboardButton("🧪 Pociones", callback_data='tienda_pociones'), InlineKeyboardButton("🎁 Cajas", callback_data='tienda_cajas')], [InlineKeyboardButton("💍 Pactos", callback_data='tienda_pactos'), InlineKeyboardButton("👑 Bendiciones", callback_data='tienda_bendiciones')], [InlineKeyboardButton("🔙 Volver al Menú", callback_data='volver_menu')]]
    msg = await update.message.reply_text(f"🛒 *MERCADO*\n⭐ Estrellas: **{estrellas}**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    context.user_data['msg_tienda'] = msg.message_id

async def tienda_pociones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton("🧪 Poción Vida (50 HP) - 5⭐", callback_data='comprar_pocion_vida')], [InlineKeyboardButton("🔮 Poción Maná (50 MP) - 5⭐", callback_data='comprar_pocion_mana')], [InlineKeyboardButton("🧪 Elixir Completo - 15⭐", callback_data='comprar_elixir')], [InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]
    await query.edit_message_text("🧪 *POCIONES*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def tienda_cajas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton("📦 Caja Común - 10⭐", callback_data='comprar_caja_comun')], [InlineKeyboardButton("🎁 Cofre Épico - 30⭐", callback_data='comprar_cofre_epico')], [InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]
    await query.edit_message_text("🎁 *CAJAS*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); user_id = update.effective_user.id
    item = query.data.replace('comprar_', ''); precios = {'pocion_vida': 5, 'pocion_mana': 5, 'elixir': 15, 'caja_comun': 10, 'cofre_epico': 30}
    precio = precios.get(item, 0); conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
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
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Menú activado.", reply_markup=obtener_menu_fijo())

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
    app.add_handler(CallbackQueryHandler(tienda_cajas, pattern='^tienda_cajas$'))
    app.add_handler(CallbackQueryHandler(comprar, pattern='^comprar_'))
    app.add_handler(CallbackQueryHandler(equipar_arma, pattern='^equipar_'))
    app.add_handler(CallbackQueryHandler(volver_menu, pattern='^volver_menu$'))
    app.add_handler(CallbackQueryHandler(tienda, pattern='^menu_tienda$'))
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
