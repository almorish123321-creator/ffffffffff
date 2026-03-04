import asyncio
import re
import os
import random
import threading
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- خادم ويب بسيط جداً لإرضاء Render Health Check ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- الإعدادات (تأكد من صحتها) ---
API_ID = 33957094
API_HASH = "35e04f65846f09700aac0696a59f1a37"
BOT_TOKEN = "8568132127:AAG-4Mxkj7WxpQcVwUcX6GdGHRAfEMjQs_8"
ADMIN_ID = 7853478744

USER_CLIENTS = {}
MESSAGES = {}
SETTINGS = {'interval': 3, 'encryption': True}
TEMP = {}
is_posting = False

bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# دالة التشفير لمنع الحظر
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

# أزرار التحكم
def main_buttons():
    enc_status = "✅ مفعل" if SETTINGS['encryption'] else "❌ معطل"
    return [
        [Button.inline("➕ إضافة حساب", "add"), Button.inline("🗑 حذف حساب", "del_list")],
        [Button.inline("📝 ضبط الرسالة", "msg"), Button.inline("⏱ ضبط الوقت", "time")],
        [Button.inline("🚀 بدء النشر", "start_p"), Button.inline("🛑 إيقاف النشر", "stop_p")],
        [Button.inline(f"🛡 التشفير: {enc_status}", "toggle_enc"), Button.inline("📊 الحالة", "status")]
    ]

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    if event.sender_id == ADMIN_ID:
        await event.respond("👋 **مرحباً بك في لوحة تحكم almorish_2000 المحدثة!**", buttons=main_buttons())

@bot.on(events.CallbackQuery())
async def cb_handler(event):
    if event.sender_id != ADMIN_ID: return
    global is_posting
    data = event.data.decode()
    
    if data == "status":
        s = "✅ يعمل" if is_posting else "🛑 متوقف"
        await event.edit(f"📊 **الحالة:** {s}\nحسابات: {len(USER_CLIENTS)}\nوقت: {SETTINGS['interval']}ث", buttons=main_buttons())
    elif data == "add":
        await event.edit("📱 أرسل الرقم مع رمز الدولة (مثال: +966...):")
        TEMP[ADMIN_ID] = "phone"
    elif data == "start_p":
        if not USER_CLIENTS or "1" not in MESSAGES:
            return await event.answer("❌ أضف حساباً ورسالة أولاً!", alert=True)
        is_posting = True
        asyncio.create_task(poster())
        await event.edit("🚀 تم بدء عملية النشر..", buttons=main_buttons())
    elif data == "stop_p":
        is_posting = False
        await event.edit("🛑 تم إيقاف النشر.", buttons=main_buttons())

# معالج النصوص والرسائل
@bot.on(events.NewMessage())
async def text_handler(event):
    if event.sender_id != ADMIN_ID: return
    state = TEMP.get(ADMIN_ID)
    
    if state == "phone":
        phone = event.text.strip()
        client = TelegramClient(phone, API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)
        TEMP[ADMIN_ID] = {"s": "code", "p": phone, "c": client}
        await event.respond(f"📩 أرسل الكود الوارد للحساب {phone}:")
    elif isinstance(state, dict) and state.get("s") == "code":
        try:
            await state["c"].sign_in(state["p"], event.text.strip())
            USER_CLIENTS[state["p"]] = state["c"]
            await event.respond(f"✅ تم ربط الحساب {state['p']}!")
            TEMP.pop(ADMIN_ID)
        except Exception as e: await event.respond(f"❌ خطأ: {e}")
    elif state == "msg":
        MESSAGES["1"] = event.text
        TEMP.pop(ADMIN_ID)
        await event.respond("✅ تم حفظ الرسالة!", buttons=main_buttons())

# دالة النشر الدوري
async def poster():
    global is_posting
    while is_posting:
        txt = MESSAGES.get("1")
        for phone, client in list(USER_CLIENTS.items()):
            if not is_posting: break
            async for dialog in client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    try:
                        await client.send_message(dialog.id, encrypt_text(txt))
                        await asyncio.sleep(SETTINGS['interval'])
                    except FloodWaitError as e: await asyncio.sleep(e.seconds)
                    except: pass
        await asyncio.sleep(10)

if __name__ == "__main__":
    # تشغيل خادم الويب في الخلفية فوراً
    threading.Thread(target=run_health_server, daemon=True).start()
    print("🚀 البوت يعمل الآن..")
    bot.run_until_disconnected()
