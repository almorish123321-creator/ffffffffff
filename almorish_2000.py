import asyncio
import re
import os
import random
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# --- إعدادات خادم الويب للاستضافة على Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- الإعدادات الأساسية ---
API_ID = 33957094
API_HASH = "35e04f65846f09700aac0696a59f1a37"
BOT_TOKEN = "8568132127:AAG-4Mxkj7WxpQcVwUcX6GdGHRAfEMjQs_8"
ADMIN_ID = 7853478744

# --- المتغيرات ---
USER_CLIENTS = {}
MESSAGES = {}
SETTINGS = {'interval': 3, 'encryption': True}
TEMP = {}
is_posting = False

# --- البوت الرئيسي ---
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

def encrypt_text(text):
    if not SETTINGS.get('encryption'): return text
    zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
    words = text.split()
    encrypted_words = []
    for word in words:
        char_to_add = random.choice(zero_width_chars)
        pos = random.randint(0, len(word))
        encrypted_words.append(word[:pos] + char_to_add + word[pos:])
    return " ".join(encrypted_words)

def main_buttons():
    enc_status = "✅ مفعل" if SETTINGS['encryption'] else "❌ معطل"
    return [
        [Button.inline("➕ إضافة حساب", "add"), Button.inline("🗑 حذف حساب", "del_list")],
        [Button.inline("📝 ضبط الرسالة", "msg"), Button.inline("⏱ ضبط الوقت", "time")],
        [Button.inline("🚀 بدء النشر", "start_p"), Button.inline("🛑 إيقاف النشر", "stop_p")],
        [Button.inline(f"🛡 التشفير: {enc_status}", "toggle_enc"), Button.inline("📊 الحالة", "status")],
        [Button.inline("📢 المجموعات المشتركة", "view_chats")]
    ]

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    if event.sender_id != ADMIN_ID: return
    await event.respond("👋 **أهلاً بك في النسخة النهائية من بوت النشر (almorish_2000)!**\n\nيمكنك التحكم الكامل من هنا:", buttons=main_buttons())

@bot.on(events.CallbackQuery())
async def cb_handler(event):
    if event.sender_id != ADMIN_ID: return
    global is_posting
    data = event.data.decode()
    
    if data == "status":
        s = "✅ يعمل" if is_posting else "🛑 متوقف"
        await event.edit(f"📊 **حالة البوت:**\n\n• النشر: {s}\n• الحسابات النشطة: {len(USER_CLIENTS)}\n• الفاصل الزمني: {SETTINGS['interval']} ثانية", buttons=main_buttons())
    
    elif data == "add":
        await event.edit("📱 أرسل رقم الهاتف مع رمز الدولة (مثال: +967...):")
        TEMP[ADMIN_ID] = "phone"
    
    elif data == "del_list":
        if not USER_CLIENTS: return await event.answer("❌ لا توجد حسابات لحذفها.", alert=True)
        btns = [[Button.inline(f"❌ حذف {p}", f"rm_{p}")] for p in USER_CLIENTS.keys()]
        btns.append([Button.inline("⬅️ عودة", "back")])
        await event.edit("🗑 اختر الحساب الذي تريد حذفه:", buttons=btns)
    
    elif data.startswith("rm_"):
        p = data.replace("rm_", "")
        if p in USER_CLIENTS:
            await USER_CLIENTS[p].disconnect()
            del USER_CLIENTS[p]
            if os.path.exists(f"{p}.session"): os.remove(f"{p}.session")
            await event.answer(f"✅ تم حذف الحساب {p}", alert=True)
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())

    elif data == "msg":
        await event.edit("📩 أرسل نص الإعلان الجديد:")
        TEMP[ADMIN_ID] = "msg"
    
    elif data == "time":
        await event.edit("⏱ أرسل الفاصل الزمني بالثواني:")
        TEMP[ADMIN_ID] = "time"
        
    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS['encryption']
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())

    elif data == "view_chats":
        if not USER_CLIENTS: return await event.answer("❌ لا توجد حسابات.", alert=True)
        await event.answer("جاري جلب المجموعات...", alert=False)
        count = 0
        for client in USER_CLIENTS.values():
            async for dialog in client.iter_dialogs():
                if dialog.is_group or dialog.is_channel: count += 1
        await event.edit(f"📢 **المجموعات المشتركة:**\n\n✅ الإجمالي: {count} مجموعة.", buttons=main_buttons())

    elif data == "start_p":
        if not USER_CLIENTS or "1" not in MESSAGES:
            return await event.answer("❌ أضف حساباً ورسالة أولاً!", alert=True)
        is_posting = True
        asyncio.create_task(poster())
        await event.edit("🚀 بدأ النشر بنجاح.", buttons=main_buttons())
        
    elif data == "stop_p":
        is_posting = False
        await event.edit("🛑 تم إيقاف النشر.", buttons=main_buttons())
    
    elif data == "back":
        await event.edit("👋 لوحة التحكم الرئيسية:", buttons=main_buttons())

@bot.on(events.NewMessage())
async def text_handler(event):
    if event.sender_id != ADMIN_ID: return
    state = TEMP.get(ADMIN_ID)
    text = event.text

    # الانضمام التلقائي للروابط
    links = re.findall(r"(https?://t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+|https?://t\.me/[a-zA-Z0-9_]+)", text)
    if links:
        if not USER_CLIENTS: return await event.respond("❌ أضف حساباً أولاً.")
        await event.respond(f"⏳ جاري الانضمام لـ {len(links)} مجموعة...")
        for link in links:
            for phone, client in list(USER_CLIENTS.items()):
                try:
                    from telethon.tl.functions.messages import ImportChatInviteRequest
                    from telethon.tl.functions.channels import JoinChannelRequest
                    if "joinchat" in link or "+" in link:
                        h = link.split('/')[-1].replace('+', '')
                        await client(ImportChatInviteRequest(h))
                    else:
                        await client(JoinChannelRequest(link))
                    await event.respond(f"✅ {phone} انضم بنجاح.")
                except Exception as e: await event.respond(f"❌ {phone} فشل: {str(e)[:50]}")
        return

    if state == "msg":
        MESSAGES["1"] = text
        TEMP.pop(ADMIN_ID)
        await event.respond("✅ تم حفظ الإعلان!", buttons=main_buttons())
    
    elif state == "time":
        try:
            SETTINGS['interval'] = int(text)
            TEMP.pop(ADMIN_ID)
            await event.respond(f"✅ تم ضبط الوقت لـ {text} ثوانٍ.", buttons=main_buttons())
        except: await event.respond("❌ أرسل رقماً فقط.")
        
    elif state == "phone":
        phone = text.strip()
        client = TelegramClient(phone, API_ID, API_HASH)
        await client.connect()
        try:
            await client.send_code_request(phone)
            TEMP[ADMIN_ID] = {"s": "code", "p": phone, "c": client}
            await event.respond(f"📩 أرسل كود التحقق لـ {phone}:")
        except Exception as e: await event.respond(f"❌ خطأ: {e}")

    elif isinstance(state, dict) and state.get("s") == "code":
        try:
            await state["c"].sign_in(state["p"], text.strip())
            USER_CLIENTS[state["p"]] = state["c"]
            await event.respond(f"✅ تم تفعيل الحساب {state['p']} بنجاح!")
            TEMP.pop(ADMIN_ID)
        except SessionPasswordNeededError:
            TEMP[ADMIN_ID]["s"] = "pass"
            await event.respond("🔐 هذا الحساب محمي بكلمة سر. يرجى إرسالها:")
        except Exception as e: await event.respond(f"❌ فشل: {e}")

    elif isinstance(state, dict) and state.get("s") == "pass":
        try:
            await state["c"].sign_in(password=text.strip())
            USER_CLIENTS[state["p"]] = state["c"]
            await event.respond("✅ تم التفعيل بنجاح!")
            TEMP.pop(ADMIN_ID)
        except Exception as e: await event.respond(f"❌ خطأ: {e}")

async def poster():
    global is_posting
    while is_posting:
        txt = MESSAGES.get("1")
        if not txt or not USER_CLIENTS: break
        for phone, client in list(USER_CLIENTS.items()):
            if not is_posting: break
            try:
                async for dialog in client.iter_dialogs():
                    if dialog.is_group or dialog.is_channel:
                        try:
                            await client.send_message(dialog.id, encrypt_text(txt))
                            await asyncio.sleep(SETTINGS['interval'])
                        except FloodWaitError as e: await asyncio.sleep(e.seconds)
                        except: pass
            except: pass
        await asyncio.sleep(5)

if __name__ == "__main__":
    # تشغيل خادم الويب في خيط منفصل للاستضافة
    threading.Thread(target=run_health_server, daemon=True).start()
    print("🚀 البوت يعمل بكامل ميزاته... أرسل /start")
    bot.run_until_disconnected()
