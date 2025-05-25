import os
import logging
import requests
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

# إعداد التوكنات من متغيرات البيئة
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# المستخدمون المسموح لهم فقط
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "").split(",")  # ضع معرفات المستخدمين مفصولة بفاصلة

# سجل الأخطاء والتتبع
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
user_languages = {}

# رسائل واجهة المستخدم
WELCOME_MSG = "Welcome! Please choose your language.\n\nمرحبًا! يرجى اختيار لغتك."
LANG_BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("English", callback_data="lang_en"),
     InlineKeyboardButton("العربية", callback_data="lang_ar")]
])

REPLIES = {
    "en": {
        "loading": "Thinking...",
        "error": "Something went wrong. Try again.",
        "ready": "Now you can ask your Cinema 4D question!",
        "blocked": "❌ You are not authorized to use this bot.",
        "rejected": "⚠️ Your message is too long or contains unsafe content."
    },
    "ar": {
        "loading": "جارٍ التفكير...",
        "error": "حدث خطأ ما. حاول مرة أخرى.",
        "ready": "الآن يمكنك طرح سؤالك في مجال Cinema 4D!",
        "blocked": "❌ غير مسموح لك باستخدام هذا البوت.",
        "rejected": "⚠️ تم رفض الرسالة لطولها أو لمحتواها."
    }
}

BAD_WORDS = ["hack", "porn", "api abuse", "token", "attack"]

def query_huggingface(prompt, lang_code):
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    full_prompt = f"Answer in {lang_code}. You are a helpful assistant for 3D Design, especially Cinema 4D.\nUser: {prompt}\nAssistant:"
    response = requests.post("https://api-inference.huggingface.co/models/mistralai/Mixtral-8x7B-Instruct-v0.1",
                             headers=headers, json={"inputs": full_prompt})
    if response.status_code == 200:
        return response.json()[0]['generated_text'].split("Assistant:")[-1].strip()
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, reply_markup=LANG_BUTTONS)

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    lang = "en" if query.data == "lang_en" else "ar"
    user_languages[user_id] = lang
    await query.edit_message_text(REPLIES[lang]["ready"])

async def respond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    lang = user_languages.get(user_id, "en")
    user_input = update.message.text.strip()

    # تحقق من الصلاحيات
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(REPLIES[lang]["blocked"])
        logging.warning(f"Unauthorized user tried: {user_id}")
        return

    # تحقق من طول الرسالة والكلمات المحظورة
    if len(user_input) > 500 or any(bad in user_input.lower() for bad in BAD_WORDS):
        await update.message.reply_text(REPLIES[lang]["rejected"])
        return

    await update.message.reply_text(REPLIES[lang]["loading"])
    logging.info(f"User {user_id} asked: {user_input}")

    answer = query_huggingface(user_input, "English" if lang == "en" else "Arabic")
    if answer:
        await update.message.reply_text(answer)
    else:
        await update.message.reply_text(REPLIES[lang]["error"])

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(select_language))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, respond))
    app.run_polling()
