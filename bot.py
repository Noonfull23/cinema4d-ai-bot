import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from huggingface_hub import InferenceClient

# إعداد المفاتيح من المتغيرات البيئية
BOT_TOKEN = os.environ.get('BOT_TOKEN')
HF_API_TOKEN = os.environ.get('HF_API_TOKEN')

MODEL_ID = "mistralai/Mixtral-8x7B-Instruct-v0.1"

# إنشاء عميل InferenceClient
client = InferenceClient(token=HF_API_TOKEN)

# تخزين لغة كل مستخدم مؤقتاً في الذاكرة
user_lang = {}

languages = {
    "🇬🇧 English": "en",
    "🇸🇦 العربية": "ar"
}

welcome_text = {
    "en": "Welcome to the Cinema 4D Assistant Bot!\nChoose your language:",
    "ar": "مرحبًا بك في مساعد Cinema 4D!\nيرجى اختيار لغتك:"
}

help_text = {
    "en": "Ask me anything related to Cinema 4D, and I’ll try to help!",
    "ar": "اسألني عن أي شيء يخص Cinema 4D وسأحاول مساعدتك!"
}

error_text = {
    "en": "❌ Something went wrong. Please try again.",
    "ar": "❌ حدث خطأ ما. حاول مرة أخرى."
}

# دالة retry ذكية مع exponential backoff لتفادي الأخطاء المؤقتة
def async_retry(retries=3, delay=2, backoff=2):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            m_retries = retries
            m_delay = delay
            for attempt in range(m_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == m_retries - 1:
                        raise
                    await asyncio.sleep(m_delay)
                    m_delay *= backoff
        return wrapper
    return decorator

# دالة استدعاء النموذج مع retry و timeout
@async_retry(retries=3, delay=2, backoff=2)
async def query_model(prompt: str, timeout: int = 15) -> str:
    loop = asyncio.get_event_loop()
    # استدعاء blocking function في executor
    result = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: client.text_generation(MODEL_ID, prompt)
        ),
        timeout=timeout
    )
    # النتيجة تكون قائمة من dicts
    if isinstance(result, list) and len(result) > 0:
        return result[0].get("generated_text", "")
    return ""

# بدء المحادثة مع اختيار اللغة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[k] for k in languages.keys()]
    await update.message.reply_text(
        welcome_text["en"] + "\n" + welcome_text["ar"],
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

# حفظ اللغة التي اختارها المستخدم
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang_key = update.message.text
    if lang_key in languages:
        user_lang[update.effective_user.id] = languages[lang_key]
        await update.message.reply_text(help_text[languages[lang_key]])
    else:
        await update.message.reply_text("Invalid choice / اختيار غير صالح.")

# الرد على استفسارات المستخدمين
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, "en")
    query = update.message.text

    prompt = f"Answer this question about Cinema 4D in {lang}:\n{query}"

    try:
        answer = await query_model(prompt)
        if answer.strip():
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(help_text[lang])
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text(error_text[lang])

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(🇬🇧 English|🇸🇦 العربية)$"), set_language))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_user))

    print("Bot is running...")
    app.run_polling()
