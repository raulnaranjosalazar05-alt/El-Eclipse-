import os
import threading
import psycopg2
import urllib.parse
import random
import asyncio
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

TOKEN = os.environ.get("TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
PORT = int(os.environ.get("PORT", 8080))
ID_CREADOR = 6985217869

# --- BASE DE DATOS ---
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS usuarios;")
        cur.execute("DROP TABLE IF EXISTS inventario;")
        cur.execute("DROP TABLE IF EXISTS jefe_supremo;")
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id_telegram BIGINT PRIMARY KEY,
                nombre VARCHAR(50),
                clase VARCHAR(20),
                sexo VARCHAR(10),
                rango VARCHAR(5) DEFAULT 'E',
                historia TEXT,
                foto_url TEXT,
                nivel INT DEFAULT 1,
                exp INT DEFAULT 0,
                vida INT DEFAULT 100,
                vida_max INT DEFAULT 100,
                mana INT DEFAULT 50,
                mana_max INT DEFAULT 50,
                atq INT DEFAULT 10,
                mov INT DEFAULT 10,
                intel INT DEFAULT 10,
                res INT DEFAULT 10,
                tac INT DEFAULT 10,
                energia INT DEFAULT 5,
                estrellas INT DEFAULT 0,
                en_combate BOOLEAN DEFAULT FALSE,
                monstruo_hp INT DEFAULT 0,
                bloqueo_hasta TIMESTAMP
            )
        """)
        cur.execute("CREATE TABLE IF NOT EXISTS inventario (id_telegram BIGINT, item VARCHAR(50), cantidad INT DEFAULT 1, PRIMARY KEY (id_telegram, item));")
        cur.execute("CREATE TABLE IF NOT EXISTS jefe_supremo (id INT PRIMARY KEY, nombre VARCHAR(50), vida INT, activo BOOLEAN);")
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Base de datos lista.")
    except Exception as e:
        print(f"❌ ERROR DE BD: {e}")

# --- LIMPIAR CHAT ---
async def limpiar_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for clave in ['msg_bienvenida', 'msg_error', 'msg_perfil', 'msg_combate', 'msg_tienda', 'msg_creador']:
        msg_id = context.user_data.get(clave)
        if msg_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except: pass
    if update.message:
        try: await update.message.delete()
        except: pass

# --- MENÚ FIJO DE ABAJO ---
def obtener_menu_fijo():
    keyboard = [
        [KeyboardButton("👤 Perfil"), KeyboardButton("🩸 Portal")],
        [KeyboardButton("🛒 Tienda"), KeyboardButton("🎒 Inventario")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- COMANDO /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    resultado = cur.fetchone()
    
    if resultado and resultado[0] is not None:
        cur.close(); conn.close()
        msg = await update.message.reply_text("🌑 *Regreso detectado.*\nUsa los botones de abajo para navegar.", reply_markup=obtener_menu_fijo(), parse_mode="Markdown")
        context.user_data['msg_bienvenida'] = msg.message_id
        return

    context.user_data['estado'] = 'esperando_nombre'
    msg = await update.message.reply_text("🌑 *El Sistema te ha detectado.*\n\n**¿Cuál es tu nombre, Sujeto?**", parse_mode="Markdown")
    context.user_data['msg_bienvenida'] = msg.message_id
    cur.close(); conn.close()

# --- MANEJADOR DE MENSAJES (Texto y Botones Fijos) ---
async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    estado = context.user_data.get('estado')

    # Si está en el menú y toca un botón fijo
    if texto == "👤 Perfil":
        await perfil(update, context)
        return
    elif texto == "🩸 Portal":
        await portal(update, context)
        return
    elif texto == "🛒 Tienda":
        await tienda(update, context)
        return
    elif texto == "🎒 Inventario":
        await inventario(update, context)
        return

    # Flujo de creación de personaje
    if estado == 'esperando_nombre':
        if not texto:
            try: await update.message.delete() 
            except: pass
            msg = await update.message.reply_text("⚠️ El Sistema no procesa imágenes. **Escribe tu nombre.**", parse_mode="Markdown")
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
    keyboard = [
        [InlineKeyboardButton("⚔️ Ejecutor/a", callback_data='clase_ejecutor')],
        [InlineKeyboardButton("🔮 Mago/a", callback_data='clase_mago')],
        [InlineKeyboardButton("🛡️ Guardián/na", callback_data='clase_guardian')],
        [InlineKeyboardButton("🗡️ Asesino/a", callback_data='clase_asesino')],
        [InlineKeyboardButton("🏹 Arquero/a", callback_data='clase_arquero')],
        [InlineKeyboardButton("✨ Clérigo/a", callback_data='clase_clerigo')]
    ]
    await query.edit_message_text("Sexo registrado.\n\n**Elige tu clase:**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def boton_clase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer() 
    if context.user_data.get('estado') != 'esperando_clase': return
    user_id = update.effective_user.id
    clase_base = query.data.replace('clase_', '') 
    nombre_elegido = context.user_data.get('nombre_temp', 'Desconocido')
    sexo_elegido = context.user_data.get('sexo_temp', 'M')
    
    nombres_clases = {
        'ejecutor': {'M': 'Ejecutor', 'F': 'Ejecutora'}, 'mago': {'M': 'Mago', 'F': 'Maga'},
        'guardian': {'M': 'Guardián', 'F': 'Guardiana'}, 'asesino': {'M': 'Asesino', 'F': 'Asesina'},
        'arquero': {'M': 'Arquero', 'F': 'Arquera'}, 'clerigo': {'M': 'Clérigo', 'F': 'Clériga'}
    }
    clase_final = nombres_clases.get(clase_base, nombres_clases['ejecutor'])[sexo_elegido]
    
    stats = {
        'ejecutor': {'vida': 120, 'mana': 30, 'atq': 25, 'mov': 15, 'intel': 5,  'res': 15, 'tac': 15},
        'mago':     {'vida': 80,  'mana': 100,'atq': 5,  'mov': 10, 'intel': 25, 'res': 10, 'tac': 25},
        'guardian': {'vida': 180, 'mana': 40, 'atq': 10, 'mov': 5,  'intel': 10, 'res': 25, 'tac': 25},
        'asesino':  {'vida': 90,  'mana': 50, 'atq': 20, 'mov': 25, 'intel': 5,  'res': 5,  'tac': 20},
        'arquero':  {'vida': 100, 'mana': 60, 'atq': 15, 'mov': 20, 'intel': 10, 'res': 10, 'tac': 20},
        'clerigo':  {'vida': 110, 'mana': 80, 'atq': 10, 'mov': 10, 'intel': 20, 'res': 15, 'tac': 20}
    }
    s = stats.get(clase_base, stats['ejecutor'])
    
    genero_ingles = "man" if sexo_elegido == 'M' else "woman"
    prompt = urllib.parse.quote(f"portrait of a {genero_ingles} {clase_final}, dark fantasy RPG, neon purple glow, highly detailed")
    foto_url = f"https://image.pollinations.ai/prompt/{prompt}?width=512&height=512&nologo=true&model=flux&seed={random.randint(1, 9999)}"
    
    historia = f"El día que el cielo se tiñó de violeta, {nombre_elegido} despertó con el poder de un {clase_final}."

    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (id_telegram, nombre, clase, sexo, rango, historia, foto_url, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, estrellas)
        VALUES (%s, %s, %s, %s, 'E', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
    """, (user_id, nombre_elegido, clase_final, sexo_elegido, historia, foto_url, s['vida'], s['vida'], s['mana'], s['mana'], s['atq'], s['mov'], s['intel'], s['res'], s['tac']))
    conn.commit(); cur.close(); conn.close()
    
    icono_sexo = "♂️" if sexo_elegido == 'M' else "♀️"
    texto_final = (
        f"✅ *REGISTRO COMPLETADO*\n\n👤 Sujeto: **{nombre_elegido}**\n⚔️ Clase: **{clase_final}**\n{icono_sexo} Sexo: **{'Masculino' if sexo_elegido == 'M' else 'Femenino'}**\n"
        f"🏅 Rango: **E** | 📊 Nivel: **1**\n\n📖 *Historia:* {historia}\n\n❤️ Vida: {s['vida']} | 🔮 Maná: {s['mana']}\n"
        f"⭐ Estrellas: 0"
    )
    try: await query.message.delete()
    except: pass
    
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=foto_url, caption=texto_final, parse_mode="Markdown")
    
    msg = await update.message.reply_text("🌑 El Sistema ha registrado tu ficha. Usa los botones de abajo.", reply_markup=obtener_menu_fijo())
    context.user_data['msg_perfil'] = msg.message_id
    context.user_data['estado'] = 'en_menu'

# --- PERFIL ---
async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context) 
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, historia, foto_url, energia, estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone(); cur.close(); conn.close()

    if user:
        nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, mana_max, atq, mov, intel, res, tac, historia, foto_url, energia, estrellas = user
        icono_sexo = "♂️" if sexo == 'M' else "♀️"
        texto = (
            f"🌑 *FICHA DEL SISTEMA*\n\n👤 Sujeto: **{nombre}**\n⚔️ Clase: **{clase}**\n{icono_sexo} Sexo: **{'Masculino' if sexo == 'M' else 'Femenino'}**\n"
            f"🏅 Rango: **{rango}** | 📊 Nivel: **{nivel}** (EXP: {exp}/{nivel*100})\n\n📖 *Historia:* {historia}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}/{mana_max}\n"
            f"⚔️ ATQ: {atq} | 💨 MOV: {mov} | 🧠 INT: {intel}\n🛡️ RES: {res} | 🎯 TAC: {tac}\n\n⚡ *Energía:* {energia}/5 | ⭐ *Estrellas:* {estrellas}"
        )
        msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=foto_url, caption=texto, parse_mode="Markdown")
        context.user_data['msg_perfil'] = msg.message_id

# --- PORTAL (COMBATE) ---
async def portal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT vida, energia, bloqueo_hasta FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    
    if user[2] and user[2] > datetime.datetime.now():
        minutos = int((user[2] - datetime.datetime.now()).total_seconds() // 60)
        cur.close(); conn.close()
        msg = await update.message.reply_text(f"☠️ *Estás herido.* Bloqueado por {minutos} minutos.", parse_mode="Markdown")
        context.user_data['msg_error'] = msg.message_id
        return

    if user[1] <= 0:
        cur.close(); conn.close()
        msg = await update.message.reply_text("⚡ *Sin Energía.* Espera a recuperarte.", parse_mode="Markdown")
        context.user_data['msg_error'] = msg.message_id
        return

    hp_monstruo = 100
    cur.execute("UPDATE usuarios SET en_combate = TRUE, monstruo_hp = %s, energia = energia - 1 WHERE id_telegram = %s", (hp_monstruo, user_id))
    conn.commit(); cur.close(); conn.close()

    context.user_data['estado'] = 'en_combate'
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar'), InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')],
        [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad'), InlineKeyboardButton("🏃 Huir", callback_data='combate_huir')]
    ]
    msg = await update.message.reply_text(
        f"🩸 *PORTAL ABIERTO*\n\n**Karu, el Registrado** (Rango E).\n❤️ Vida: {hp_monstruo}/100\n\n*¿Qué harás?*", 
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    context.user_data['msg_combate'] = msg.message_id

# --- LÓGICA DE COMBATE ---
async def boton_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'en_combate': return

    accion = query.data.replace('combate_', '')
    user_id = update.effective_user.id
    frase = context.user_data.get('frase_epica', '')
    context.user_data['frase_epica'] = ''

    await query.edit_message_text("⏳ *Calculando destino...*", parse_mode="Markdown")
    await asyncio.sleep(2) 

    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, vida, vida_max, mana, atq, mov, intel, exp, nivel, rango, monstruo_hp FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    nombre, clase, vida, vida_max, mana, atq, mov, intel, exp, nivel, rango, hp_monstruo = user

    narracion = f"El Sujeto {nombre} "
    if frase: narracion = f"*\"{frase}\"*\n\n" + narracion

    if accion == 'huir':
        if random.randint(1, 100) <= (mov * 2):
            narracion += "logra escapar. No hay recompensa."
            cur.execute("UPDATE usuarios SET en_combate = FALSE WHERE id_telegram = %s", (user_id,))
            conn.commit(); cur.close(); conn.close()
            await query.edit_message_text(narracion + "\n\n🌑 *Has vuelto al Refugio.*", parse_mode="Markdown")
            context.user_data['estado'] = 'en_menu'
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Menú activado.", reply_markup=obtener_menu_fijo())
            return
        else:
            dano_recibido = random.randint(10, 20)
            vida -= dano_recibido
            narracion += f"intenta huir, pero es alcanzado. **{dano_recibido} de daño.**"
    elif accion == 'esquivar':
        if random.randint(1, 100) <= (mov * 3):
            narracion += "esquiva perfectamente. **¡Sin daño!**"
        else:
            dano_recibido = random.randint(5, 10)
            vida -= dano_recibido
            narracion += f"falla al esquivar. **{dano_recibido} de daño.**"
    else:
        if accion == 'atacar': dano = atq + random.randint(1, 10)
        else:
            if mana >= 20:
                mana -= 20
                stat = intel if clase in ['Mago', 'Maga'] else atq
                dano = int((stat * 1.5) + random.randint(5, 15))
                if accion == 'habilidad' and clase in ['Mago', 'Maga']:
                    dano = int(dano * 2)
                    narracion += "usa magia. Karu es débil a esto. "
                else:
                    narracion += "usa su habilidad. "
            else:
                dano = 0
                narracion += "no tiene maná. El ataque falla. "
        
        hp_monstruo -= dano
        if hp_monstruo < 0: hp_monstruo = 0
        if dano > 0: narracion += f"**{dano} de daño.** "
        if hp_monstruo > 0:
            dano_recibido = random.randint(5, 15)
            vida -= dano_recibido
            narracion += f"El monstruo responde. **{dano_recibido} de daño recibido.**"

    if vida < 0: vida = 0

    if hp_monstruo <= 0:
        narracion += f"\n\n💀 **Karu ha muerto.**\n🌟 *+100 EXP.*"
        exp += 100
        nuevo_rango = rango
        if exp >= nivel * 100:
            exp -= nivel * 100
            nivel += 1
            vida_max += 20; vida = vida_max
            atq += 2; mov += 1; intel += 2
            if nivel == 11: nuevo_rango = 'D'
            narracion += f"\n\n⬆️ **¡NIVEL {nivel}!** (Rango {nuevo_rango})"
        
        cur.execute("UPDATE usuarios SET vida = %s, vida_max = %s, mana = %s, atq = %s, mov = %s, intel = %s, exp = %s, nivel = %s, rango = %s, en_combate = FALSE, energia = 5 WHERE id_telegram = %s", 
                    (vida, vida_max, mana, atq, mov, intel, exp, nivel, nuevo_rango, user_id))
        conn.commit(); cur.close(); conn.close()
        
        await query.edit_message_text(narracion, parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Menú activado.", reply_markup=obtener_menu_fijo())
        return

    if vida <= 0:
        narracion += f"\n\n☠️ **Has muerto.** Bloqueado 1 hora."
        bloqueo = datetime.datetime.now() + datetime.timedelta(hours=1)
        cur.execute("UPDATE usuarios SET vida = 0, en_combate = FALSE, bloqueo_hasta = %s WHERE id_telegram = %s", (bloqueo, user_id))
        conn.commit(); cur.close(); conn.close()
        await query.edit_message_text(narracion, parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Menú activado.", reply_markup=obtener_menu_fijo())
        return

    cur.execute("UPDATE usuarios SET vida = %s, mana = %s, monstruo_hp = %s WHERE id_telegram = %s", (vida, mana, hp_monstruo, user_id))
    conn.commit(); cur.close(); conn.close()

    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar'), InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')],
        [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad'), InlineKeyboardButton("🏃 Huir", callback_data='combate_huir')]
    ]
    await query.edit_message_text(
        f"{narracion}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}\n🩸 Karu: {hp_monstruo}/100", 
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )

# --- TIENDA ---
async def tienda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    estrellas = cur.fetchone()[0]
    cur.close(); conn.close()

    keyboard = [
        [InlineKeyboardButton("🧪 Pociones", callback_data='tienda_pociones'), InlineKeyboardButton("🎁 Cajas", callback_data='tienda_cajas')],
        [InlineKeyboardButton("💍 Pactos", callback_data='tienda_pactos'), InlineKeyboardButton("👑 Bendiciones", callback_data='tienda_bendiciones')]
    ]
    msg = await update.message.reply_text(
        f"🛒 *MERCADO DEL SISTEMA*\n\n⭐ Tus Estrellas: **{estrellas}**\n\nElige una categoría:", 
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    context.user_data['msg_tienda'] = msg.message_id

async def tienda_pociones(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [
        [InlineKeyboardButton("🧪 Poción Vida (50 HP) - 5⭐", callback_data='comprar_pocion_vida')],
        [InlineKeyboardButton("🔮 Poción Maná (50 MP) - 5⭐", callback_data='comprar_pocion_mana')],
        [InlineKeyboardButton("🧪 Elixir Completo - 15⭐", callback_data='comprar_elixir')]
    ]
    await query.edit_message_text("🧪 *POCIONES*\nRestaura tu salud o maná.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def tienda_cajas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [
        [InlineKeyboardButton("📦 Caja Común - 10⭐", callback_data='comprar_caja_comun')],
        [InlineKeyboardButton("🎁 Cofre Épico - 30⭐", callback_data='comprar_cofre_epico')]
    ]
    await query.edit_message_text("🎁 *CAJAS*\nPrueba tu suerte.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user_id = update.effective_user.id
    item = query.data.replace('comprar_', '')
    
    precios = {'pocion_vida': 5, 'pocion_mana': 5, 'elixir': 15, 'caja_comun': 10, 'cofre_epico': 30}
    precio = precios.get(item, 0)
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT estrellas FROM usuarios WHERE id_telegram = %s", (user_id,))
    estrellas = cur.fetchone()[0]
    
    if estrellas < precio:
        await query.answer("❌ No tienes suficientes Estrellas ⭐.", show_alert=True)
        return
        
    cur.execute("UPDATE usuarios SET estrellas = estrellas - %s WHERE id_telegram = %s", (precio, user_id))
    
    if item in ['pocion_vida', 'pocion_mana', 'elixir']:
        cur.execute("INSERT INTO inventario (id_telegram, item, cantidad) VALUES (%s, %s, 1) ON CONFLICT (id_telegram, item) DO UPDATE SET cantidad = inventario.cantidad + 1", (user_id, item))
        await query.edit_message_text(f"✅ Has comprado **{item.replace('_', ' ').title()}**.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]), parse_mode="Markdown")
    else:
        await query.edit_message_text(f"📦 Abriste **{item.replace('_', ' ').title()}**.\nGanaste 10 Estrellas ficticias.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Volver", callback_data='menu_tienda')]]), parse_mode="Markdown")
    
    conn.commit(); cur.close(); conn.close()

# --- INVENTARIO ---
async def inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT item, cantidad FROM inventario WHERE id_telegram = %s", (user_id,))
    items = cur.fetchall(); cur.close(); conn.close()

    if not items:
        msg = await update.message.reply_text("🎒 Tu inventario está vacío. Compra algo en la tienda.")
        context.user_data['msg_bienvenida'] = msg.message_id
        return

    texto = "🎒 *INVENTARIO*\n\n"
    for item, cant in items:
        texto += f"- {item.replace('_', ' ').title()} x{cant}\n"
    msg = await update.message.reply_text(texto, parse_mode="Markdown")
    context.user_data['msg_bienvenida'] = msg.message_id

# --- CREADOR (CON REGALO DE ESTRELLAS) ---
async def creador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ID_CREADOR: return
    keyboard = [
        [InlineKeyboardButton("👑 Invocar Jefe Supremo", callback_data='admin_jefe')],
        [InlineKeyboardButton("⭐ Regalar Estrellas", callback_data='admin_regalar_estrellas')]
    ]
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
        await query.edit_message_text("Escribe el ID del jugador y la cantidad (ej: `6985217869 100`) en el chat.", parse_mode="Markdown")
        context.user_data['estado'] = 'regalar_estrellas'

# --- MANEJADOR DE TEXTO PARA REGALAR ESTRELLAS ---
async def manejar_regalo_estrellas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ID_CREADOR: return
    try:
        partes = update.message.text.split()
        target_id = int(partes[0])
        cantidad = int(partes[1])
        
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("UPDATE usuarios SET estrellas = estrellas + %s WHERE id_telegram = %s", (cantidad, target_id))
        conn.commit(); cur.close(); conn.close()
        
        await update.message.reply_text(f"⭐ Has regalado {cantidad} Estrellas al ID {target_id}.")
    except:
        await update.message.reply_text("❌ Formato incorrecto. Usa: `ID CANTIDAD`", parse_mode="Markdown")

# --- SERVIDOR WEB Y MAIN ---
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
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensajes))
    # Añadimos el manejador para el regalo de estrellas (solo actúa si el estado es correcto)
    
    app.add_handler(CallbackQueryHandler(boton_sexo, pattern='^sexo_'))
    app.add_handler(CallbackQueryHandler(boton_clase, pattern='^clase_'))
    app.add_handler(CallbackQueryHandler(boton_combate, pattern='^combate_'))
    app.add_handler(CallbackQueryHandler(boton_creador, pattern='^admin_'))
    app.add_handler(CallbackQueryHandler(tienda_pociones, pattern='^tienda_pociones$'))
    app.add_handler(CallbackQueryHandler(tienda_cajas, pattern='^tienda_cajas$'))
    app.add_handler(CallbackQueryHandler(comprar, pattern='^comprar_'))
    app.add_handler(CallbackQueryHandler(tienda, pattern='^menu_tienda$'))
    
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
