import os
import threading
import psycopg2
import urllib.parse
import random
import asyncio
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        # Borramos tablas para actualizar
        cur.execute("DROP TABLE IF EXISTS usuarios;")
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
                atq INT DEFAULT 10,
                mov INT DEFAULT 10,
                intel INT DEFAULT 10,
                res INT DEFAULT 10,
                tac INT DEFAULT 10,
                energia INT DEFAULT 5,
                en_combate BOOLEAN DEFAULT FALSE,
                monstruo_hp INT DEFAULT 0,
                bloqueo_hasta TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS jefe_supremo (
                id INT PRIMARY KEY,
                nombre VARCHAR(50),
                vida INT,
                activo BOOLEAN
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
    for clave in ['msg_bienvenida', 'msg_error', 'msg_perfil', 'msg_combate']:
        msg_id = context.user_data.get(clave)
        if msg_id:
            try: await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_id)
            except: pass
    if update.message:
        try: await update.message.delete()
        except: pass

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
        msg = await update.message.reply_text("🌑 *Regreso detectado.*\n\nUsa /perfil, /portal o /ranking.", parse_mode="Markdown")
        context.user_data['msg_bienvenida'] = msg.message_id
        return

    context.user_data['estado'] = 'esperando_nombre'
    msg = await update.message.reply_text("🌑 *El Sistema te ha detectado.*\n\n**¿Cuál es tu nombre, Sujeto?**", parse_mode="Markdown")
    context.user_data['msg_bienvenida'] = msg.message_id
    cur.close(); conn.close()

# --- MANEJADOR DE MENSAJES ---
async def manejar_mensajes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    estado = context.user_data.get('estado')
    if estado == 'esperando_nombre':
        if not update.message.text:
            try: await update.message.delete() 
            except: pass
            msg = await update.message.reply_text("⚠️ El Sistema no procesa imágenes. **Escribe tu nombre.**", parse_mode="Markdown")
            context.user_data['msg_error'] = msg.message_id
            return
        nombre_elegido = update.message.text
        try: await update.message.delete()
        except: pass
        await limpiar_chat(update, context)
        context.user_data['nombre_temp'] = nombre_elegido
        context.user_data['estado'] = 'esperando_sexo'
        keyboard = [[InlineKeyboardButton("♂️ Masculino", callback_data='sexo_m')], [InlineKeyboardButton("♀️ Femenino", callback_data='sexo_f')]]
        msg = await update.message.reply_text(f"Registro aceptado, **{nombre_elegido}**.\n\nSelecciona tu sexo:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data['msg_pregunta_sexo'] = msg.message_id
        return

    if estado == 'en_combate' and update.message.text:
        context.user_data['frase_epica'] = update.message.text
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
    
    # Stats: Vida, Mana, ATQ, MOV, INT, RES, TAC
    stats = {
        'ejecutor': {'vida': 120, 'mana': 20, 'atq': 25, 'mov': 15, 'intel': 5,  'res': 15, 'tac': 15},
        'mago':     {'vida': 80,  'mana': 100,'atq': 5,  'mov': 10, 'intel': 25, 'res': 10, 'tac': 25},
        'guardian': {'vida': 180, 'mana': 30, 'atq': 10, 'mov': 5,  'intel': 10, 'res': 25, 'tac': 25},
        'asesino':  {'vida': 90,  'mana': 40, 'atq': 20, 'mov': 25, 'intel': 5,  'res': 5,  'tac': 20},
        'arquero':  {'vida': 100, 'mana': 50, 'atq': 15, 'mov': 20, 'intel': 10, 'res': 10, 'tac': 20},
        'clerigo':  {'vida': 110, 'mana': 80, 'atq': 10, 'mov': 10, 'intel': 20, 'res': 15, 'tac': 20}
    }
    s = stats.get(clase_base, stats['ejecutor'])
    
    prompt = urllib.parse.quote(f"A {sexo_elegido} {clase_final} in a dark futuristic RPG, glowing portal, portrait")
    foto_url = f"https://image.pollinations.ai/prompt/{prompt}?width=512&height=512&nologo=true&model=flux"
    historia = f"El día que el cielo se tiñó de violeta, {nombre_elegido} despertó con el poder de un {clase_final}."

    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (id_telegram, nombre, clase, sexo, rango, historia, foto_url, vida, vida_max, mana, atq, mov, intel, res, tac)
        VALUES (%s, %s, %s, %s, 'E', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (user_id, nombre_elegido, clase_final, sexo_elegido, historia, foto_url, s['vida'], s['vida'], s['mana'], s['atq'], s['mov'], s['intel'], s['res'], s['tac']))
    conn.commit(); cur.close(); conn.close()
    
    icono_sexo = "♂️" if sexo_elegido == 'M' else "♀️"
    texto_final = (
        f"✅ *REGISTRO COMPLETADO*\n\n👤 Sujeto: **{nombre_elegido}**\n⚔️ Clase: **{clase_final}**\n{icono_sexo} Sexo: **{'Masculino' if sexo_elegido == 'M' else 'Femenino'}**\n"
        f"🏅 Rango: **E** | 📊 Nivel: **1**\n\n📖 *Historia:* {historia}\n\n❤️ Vida: {s['vida']} | 🔮 Maná: {s['mana']}\n⚔️ ATQ: {s['atq']} | 💨 MOV: {s['mov']} | 🧠 INT: {s['intel']}\n"
        f"🛡️ RES: {s['res']} | 🎯 TAC: {s['tac']}\n\n*Usa /portal para buscar tu primera mazmorra.*"
    )
    try: await query.message.delete()
    except: pass
    msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=foto_url, caption=texto_final, parse_mode="Markdown")
    context.user_data['msg_perfil'] = msg.message_id
    context.user_data['estado'] = 'en_menu'

# --- COMANDO /perfil ---
async def perfil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context) 
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, atq, mov, intel, res, tac, historia, foto_url, energia FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone(); cur.close(); conn.close()

    if user:
        nombre, clase, sexo, rango, nivel, exp, vida, vida_max, mana, atq, mov, intel, res, tac, historia, foto_url, energia = user
        icono_sexo = "♂️" if sexo == 'M' else "♀️"
        texto = (
            f"🌑 *FICHA DEL SISTEMA*\n\n👤 Sujeto: **{nombre}**\n⚔️ Clase: **{clase}**\n{icono_sexo} Sexo: **{'Masculino' if sexo == 'M' else 'Femenino'}**\n"
            f"🏅 Rango: **{rango}** | 📊 Nivel: **{nivel}** (EXP: {exp}/{nivel*100})\n\n📖 *Historia:* {historia}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}\n"
            f"⚔️ ATQ: {atq} | 💨 MOV: {mov} | 🧠 INT: {intel}\n🛡️ RES: {res} | 🎯 TAC: {tac}\n\n⚡ *Energía:* {energia}/5"
        )
        msg = await context.bot.send_photo(chat_id=update.effective_chat.id, photo=foto_url, caption=texto, parse_mode="Markdown")
        context.user_data['msg_perfil'] = msg.message_id

# --- COMANDO /ranking ---
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, nivel, rango FROM usuarios ORDER BY nivel DESC, exp DESC LIMIT 10")
    top = cur.fetchall(); cur.close(); conn.close()
    
    if not top:
        msg = await update.message.reply_text("🌑 El Sistema aún no tiene registros de esta temporada.")
        context.user_data['msg_bienvenida'] = msg.message_id
        return

    texto = "🏆 *RANKING DE LA TEMPORADA*\n\n"
    for i, user in enumerate(top):
        texto += f"{i+1}. **{user[0]}** - {user[1]} (Nv. {user[2]} | Rango {user[3]})\n"
    msg = await update.message.reply_text(texto, parse_mode="Markdown")
    context.user_data['msg_bienvenida'] = msg.message_id

# --- COMANDO /portal ---
async def portal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT clase, vida, energia, bloqueo_hasta FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    
    if not user:
        cur.close(); conn.close()
        msg = await update.message.reply_text("⚠️ Escribe /start primero.")
        context.user_data['msg_error'] = msg.message_id
        return

    if user[3] and user[3] > datetime.datetime.now():
        tiempo_restante = user[3] - datetime.datetime.now()
        minutos = int(tiempo_restante.total_seconds() // 60)
        cur.close(); conn.close()
        msg = await update.message.reply_text(f"☠️ *Estás herido.* El Sistema te bloquea por {minutos} minutos más.", parse_mode="Markdown")
        context.user_data['msg_error'] = msg.message_id
        return

    if user[2] <= 0:
        cur.close(); conn.close()
        msg = await update.message.reply_text("⚡ *Sin Energía.* Debes esperar a que tu cuerpo se recupere o comprar más.", parse_mode="Markdown")
        context.user_data['msg_error'] = msg.message_id
        return

    hp_monstruo = 100
    nueva_energia = user[2] - 1
    cur.execute("UPDATE usuarios SET en_combate = TRUE, monstruo_hp = %s, energia = %s WHERE id_telegram = %s", (hp_monstruo, nueva_energia, user_id))
    conn.commit(); cur.close(); conn.close()

    context.user_data['estado'] = 'en_combate'
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar'), InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')],
        [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad'), InlineKeyboardButton("🏃 Huir", callback_data='combate_huir')]
    ]
    
    texto = (
        f"🩸 *PORTAL ABIERTO*\n\nUna figura se arrastra desde las sombras...\nEs **Karu, el Registrado** (Rango E).\n\n"
        f"❤️ Vida del Monstruo: {hp_monstruo}/100\n\n*El Sistema está calculando tu destino...*"
    )
    msg = await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    context.user_data['msg_combate'] = msg.message_id

# --- LÓGICA DE COMBATE (CON MANÁ Y DEBILIDADES) ---
async def boton_combate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    if context.user_data.get('estado') != 'en_combate': return

    accion = query.data.replace('combate_', '')
    user_id = update.effective_user.id
    frase = context.user_data.get('frase_epica', '')
    context.user_data['frase_epica'] = ''

    await query.edit_message_text("⏳ *El Sistema está calculando tu destino...*", parse_mode="Markdown")
    await asyncio.sleep(3) 

    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT nombre, clase, vida, vida_max, mana, atq, mov, intel, exp, nivel, rango, monstruo_hp FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    nombre, clase, vida, vida_max, mana, atq, mov, intel, exp, nivel, rango, hp_monstruo = user

    narracion = f"El Sujeto {nombre} "
    if frase: narracion = f"*\"{frase}\"*\n\n" + narracion

    # MANÁ: El Mago usa INT, el resto usa ATQ. Habilidad gasta 20 de maná.
    costo_mana = 0
    dano_extra = 0

    if accion == 'huir':
        if random.randint(1, 100) <= (mov * 2):
            narracion += "logra escapar del portal. La oscuridad se cierra tras de ti. No hay recompensa."
            cur.execute("UPDATE usuarios SET en_combate = FALSE WHERE id_telegram = %s", (user_id,))
            conn.commit(); cur.close(); conn.close()
            keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data='volver_menu')]]
            await query.edit_message_text(narracion, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            context.user_data['estado'] = 'en_menu'
            return
        else:
            dano_recibido = random.randint(10, 20)
            vida -= dano_recibido
            narracion += f"intenta huir, pero es demasiado lento. El monstruo te ataca por la espalda. **{dano_recibido} de daño recibido.**"
    
    elif accion == 'esquivar':
        if random.randint(1, 100) <= (mov * 3):
            narracion += "se mueve con una agilidad sobrenatural. El ataque del monstruo pasa rozando el aire. **¡Esquivar perfecto!**"
        else:
            dano_recibido = random.randint(5, 10)
            vida -= dano_recibido
            narracion += f"intenta esquivar, pero el monstruo es más rápido. **{dano_recibido} de daño recibido.**"
    
    else:
        if accion == 'atacar':
            dano = atq + random.randint(1, 10)
        elif accion == 'habilidad':
            if mana >= 20:
                mana -= 20
                # Si es Mago, usa INT (25). Si no, usa ATQ.
                stat_usado = intel if clase in ['Mago', 'Maga'] else atq
                dano = int((stat_usado * 1.5) + random.randint(5, 15))
                narracion += "canaliza su energía. "
            else:
                narracion += "intenta usar su habilidad, pero no tiene maná. El Sistema bloquea su ataque. "
                dano = 0
        
        # DEBILIDAD DE KARU: Es débil a la magia (Habilidad hace x2 de daño)
        if accion == 'habilidad' and dano > 0:
            dano = int(dano * 2)
            narracion += f"La magia desgarra su piel de ceniza. "

        hp_monstruo -= dano
        if hp_monstruo < 0: hp_monstruo = 0
        if dano > 0: narracion += f"**{dano} de daño** infligido. "
        
        if hp_monstruo > 0:
            dano_recibido = random.randint(5, 15)
            vida -= dano_recibido
            narracion += f"El monstruo responde. **{dano_recibido} de daño recibido.**"

    if vida < 0: vida = 0

    # VICTORIA Y SUBIDA DE NIVEL
    if hp_monstruo <= 0:
        exp_ganada = 100
        nueva_exp = exp + exp_ganada
        nueva_energia = 5
        subio_nivel = False
        nuevo_rango = rango
        
        while nueva_exp >= (nivel * 100):
            nueva_exp -= (nivel * 100)
            nivel += 1
            subio_nivel = True
            
        if 1 <= nivel <= 10: nuevo_rango = 'E'
        elif 11 <= nivel <= 20: nuevo_rango = 'D'
        elif 21 <= nivel <= 35: nuevo_rango = 'C'
        elif 36 <= nivel <= 50: nuevo_rango = 'B'
        elif 51 <= nivel <= 70: nuevo_rango = 'A'
        else: nuevo_rango = 'S'

        narracion += f"\n\n💀 **Karu ha sido erradicado.**\n🌟 *Has ganado **{exp_ganada} de EXP**.*\n⚡ *Energía restaurada.*"
        
        if subio_nivel:
            vida_max += 20
            vida = vida_max
            atq += 2
            mov += 1
            intel += 2
            narracion += f"\n\n⬆️ **¡HAS SUBIDO AL NIVEL {nivel}!**\n*El Sistema ha reescrito tu código.*"
            if rango != nuevo_rango:
                narracion += f"\n👑 **¡ASCENSO DE RANGO! Ahora eres Rango {nuevo_rango}.**"

        cur.execute("UPDATE usuarios SET vida = %s, vida_max = %s, mana = %s, atq = %s, mov = %s, intel = %s, exp = %s, nivel = %s, rango = %s, en_combate = FALSE, energia = %s WHERE id_telegram = %s", 
                    (vida, vida_max, mana, atq, mov, intel, nueva_exp, nivel, nuevo_rango, nueva_energia, user_id))
        conn.commit(); cur.close(); conn.close()
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data='volver_menu')]]
        await query.edit_message_text(narracion, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'
        return

    # MUERTE
    if vida <= 0:
        narracion += f"\n\n☠️ **Has caído.** El Sistema te castiga con 1 hora de bloqueo y pierdes el 10% de tu EXP."
        exp_perdida = int(exp * 0.10)
        nueva_exp = exp - exp_perdida
        bloqueo = datetime.datetime.now() + datetime.timedelta(hours=1)
        cur.execute("UPDATE usuarios SET vida = 0, exp = %s, en_combate = FALSE, bloqueo_hasta = %s WHERE id_telegram = %s", (nueva_exp, bloqueo, user_id))
        conn.commit(); cur.close(); conn.close()
        keyboard = [[InlineKeyboardButton("🔙 Volver al menú", callback_data='volver_menu')]]
        await query.edit_message_text(narracion, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        context.user_data['estado'] = 'en_menu'
        return

    cur.execute("UPDATE usuarios SET vida = %s, mana = %s, monstruo_hp = %s WHERE id_telegram = %s", (vida, mana, hp_monstruo, user_id))
    conn.commit(); cur.close(); conn.close()

    keyboard = [
        [InlineKeyboardButton("⚔️ Atacar", callback_data='combate_atacar'), InlineKeyboardButton("💨 Esquivar", callback_data='combate_esquivar')],
        [InlineKeyboardButton("🔮 Habilidad", callback_data='combate_habilidad'), InlineKeyboardButton("🏃 Huir", callback_data='combate_huir')]
    ]
    texto_turno = (
        f"{narracion}\n\n❤️ Vida: {vida}/{vida_max} | 🔮 Maná: {mana}\n🩸 Vida de Karu: {hp_monstruo}/100\n\n*¿Cuál es tu siguiente movimiento?*"
    )
    await query.edit_message_text(texto_turno, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def volver_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    context.user_data['estado'] = 'en_menu'
    await query.edit_message_text("🌑 *Has vuelto al Refugio.*\nUsa /perfil, /portal o /ranking.", parse_mode="Markdown")

# --- COMANDO /creador ---
async def creador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ID_CREADOR:
        await update.message.reply_text("⛔ *Acceso denegado.*")
        return

    keyboard = [
        [InlineKeyboardButton("👑 Invocar Jefe Supremo", callback_data='admin_jefe')],
        [InlineKeyboardButton("🔄 Reiniciar Temporada", callback_data='admin_reset')]
    ]
    await update.message.reply_text(
        "👑 *PANEL DEL CREADOR*\n\nControl absoluto del Sistema.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def boton_creador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user_id = update.effective_user.id
    if user_id != ID_CREADOR: return

    if query.data == 'admin_jefe':
        # Invocar Jefe Supremo
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("INSERT INTO jefe_supremo (id, nombre, vida, activo) VALUES (1, 'El Devorador', 100000, TRUE) ON CONFLICT (id) DO UPDATE SET vida = 100000, activo = TRUE")
        conn.commit(); cur.close(); conn.close()
        await query.edit_message_text("👑 *JEFE SUPREMO INVOCADO.*\n\nEscribe /atacar_jefe para unirte a la batalla global. Vida: 100,000 HP.", parse_mode="Markdown")
        
    elif query.data == 'admin_reset':
        cur_reset = [[InlineKeyboardButton("☠️ CONFIRMAR RESET", callback_data='admin_reset_confirmar')]]
        await query.edit_message_text("⚠️ ¿Borrar a TODOS los usuarios?", reply_markup=InlineKeyboardMarkup(cur_reset), parse_mode="Markdown")

    elif query.data == 'admin_reset_confirmar':
        conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
        cur.execute("TRUNCATE TABLE usuarios;")
        cur.execute("UPDATE jefe_supremo SET activo = FALSE")
        conn.commit(); cur.close(); conn.close()
        await query.edit_message_text("✅ *Temporada reiniciada.*", parse_mode="Markdown")

# --- COMBATE CONTRA EL JEFE SUPREMO (GLOBAL) ---
async def atacar_jefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await limpiar_chat(update, context)
    
    conn = psycopg2.connect(DATABASE_URL, sslmode='require'); cur = conn.cursor()
    cur.execute("SELECT vida, activo FROM jefe_supremo WHERE id = 1")
    jefe = cur.fetchone()
    
    if not jefe or not jefe[1] or jefe[0] <= 0:
        cur.close(); conn.close()
        msg = await update.message.reply_text("🌑 El Jefe Supremo no está activo.")
        context.user_data['msg_error'] = msg.message_id
        return

    # Por ahora, simula un ataque directo para probar el sistema
    cur.execute("SELECT nombre, atq, mana, intel, clase FROM usuarios WHERE id_telegram = %s", (user_id,))
    user = cur.fetchone()
    if not user:
        cur.close(); conn.close()
        return

    nombre, atq, mana, intel, clase = user
    dano = intel * 2 if 'Mago' in clase else atq * 2
    nueva_vida_jefe = jefe[0] - dano
    if nueva_vida_jefe < 0: nueva_vida_jefe = 0
    
    cur.execute("UPDATE jefe_supremo SET vida = %s WHERE id = 1", (nueva_vida_jefe,))
    conn.commit(); cur.close(); conn.close()

    texto = (
        f"🩸 *ATAQUE AL JEFE SUPREMO*\n\n"
        f"Has infligido **{dano} de daño** al Jefe Supremo.\n"
        f"❤️ Vida Global del Jefe: **{nueva_vida_jefe} / 100,000**\n\n"
        f"*El Sistema registra tu ataque.*"
    )
    if nueva_vida_jefe <= 0:
        texto += "\n\n💀 **¡EL JEFE SUPREMO HA SIDO ERRADICADO!**"
    
    msg = await update.message.reply_text(texto, parse_mode="Markdown")
    context.user_data['msg_error'] = msg.message_id

# --- SERVIDOR WEB ---
class WebServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"El Sistema esta vivo.")

def main():
    server = HTTPServer(("0.0.0.0", PORT), WebServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    init_db()

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("perfil", perfil))
    app.add_handler(CommandHandler("ranking", ranking))
    app.add_handler(CommandHandler("portal", portal))
    app.add_handler(CommandHandler("creador", creador))
    app.add_handler(CommandHandler("atacar_jefe", atacar_jefe)) # Prueba del Jefe Supremo
    
    app.add_handler(MessageHandler(~filters.COMMAND, manejar_mensajes))
    
    app.add_handler(CallbackQueryHandler(boton_sexo, pattern='^sexo_'))
    app.add_handler(CallbackQueryHandler(boton_clase, pattern='^clase_'))
    app.add_handler(CallbackQueryHandler(boton_combate, pattern='^combate_'))
    app.add_handler(CallbackQueryHandler(boton_creador, pattern='^admin_'))
    app.add_handler(CallbackQueryHandler(volver_menu, pattern='^volver_menu$'))
    
    print("El Sistema ha despertado. Escuchando...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
