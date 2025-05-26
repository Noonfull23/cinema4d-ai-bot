import os
import logging
import asyncio
from typing import Optional

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from huggingface_hub import InferenceClient
from functools import wraps

# --- إعداد السجلات (Logging) ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- إعداد المتغيرات البيئية ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
MODEL_ID = "mistralai/Mixtral-8x7B-Instruct-v0.1"

# --- إعداد عميل Huggingface ---
client = InferenceClient(token=HF_API_TOKEN)

# --- دعم لغات متعددة + رسائل مرنة ---
languages = {
    "🇬🇧 English": "en",
    "🇸🇦 العربية": "ar",
}

messages = {
    "welcome": {
        "en": "Welcome to the Cinema 4D Assistant Bot!\nChoose your language:",
        "ar": "مرحبًا بك في مساعد Cinema 4D!\nيرجى اختيار لغتك:",
    },
    "help": {
        "en": "Ask me anything related to Cinema 4D, and I’ll try to help!",
        "ar": "اسألني عن أي شيء يخص Cinema 4D وسأحاول مساعدتك!",
    },
    "error": {
        "en": "❌ Something went wrong. Please try again later.",
        "ar": "❌ حدث خطأ ما. حاول مرة أخرى لاحقًا.",
    },
    "timeout": {
        "en": "⏳ The request timed out. Please try again.",
        "ar": "⏳ انتهى وقت الانتظار. يرجى المحاولة مرة أخرى.",
    },
    "invalid_language": {
        "en": "Invalid choice. Please select a language from the keyboard.",
        "ar": "اختيار غير صالح. يرجى اختيار اللغة من لوحة المفاتيح.",
    }
}

# --- تخزين لغة المستخدم بشكل دائم (في الذاكرة فقط حالياً) ---
user_languages = {}

# --- دالة retry مع تأخير متزايد ---
def async_retry(retries=3, delay=2, backoff=2):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Attempt {attempt} failed: {e}")
                    if attempt == retries:
                        logger.error(f"All {retries} attempts failed.")
                        raise
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

# --- دالة منفصلة لاستدعاء API مع retry و timeout ---
@async_retry(retries=3, delay=2, backoff=2)
async def query_model(prompt: str, timeout: int = 15) -> str:
    loop = asyncio.get_event_loop()
    # استدعاء blocking API داخل ThreadPoolExecutor باستخدام run_in_executor
    result = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: client.text_generation(MODEL_ID, inputs=prompt)
        ),
        timeout=timeout,
    )
    if isinstance(result, list) and len(result) > 0:
        return result[0].get("generated_text", "")
    return ""

# --- أوامر البوت --- 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[k] for k in languages.keys()]
    await update.message.reply_text(
        messages["welcome"]["en"] + "\n" + messages["welcome"]["ar"],
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True),
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang_key = update.message.text
    user_id = update.effective_user.id
    if lang_key in languages:
        user_languages[user_id] = languages[lang_key]
        await update.message.reply_text(
            messages["help"][languages[lang_key]],
            reply_markup=ReplyKeyboardRemove(),
        )
        logger.info(f"User {user_id} set language to {languages[lang_key]}")
    else:
        await update.message.reply_text(messages["invalid_language"]["en"] + " / " + messages["invalid_language"]["ar"])

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_languages.get(user_id, "en")
    query = update.message.text

    prompt = f"Answer this question about Cinema 4D in {lang}:\n{query}"

    try:
        response = await query_model(prompt)
        if not response.strip():
            response = messages["error"][lang]
        await update.message.reply_text(response)
    except asyncio.TimeoutError:
        await update.message.reply_text(messages["timeout"][lang])
    except Exception as e:
        logger.error(f"Unexpected error for user {user_id}: {e}")
        await update.message.reply_text(messages["error"][lang])

# --- نقطة الدخول ---

def main():
    if not BOT_TOKEN or not HF_API_TOKEN:
        logger.error("Missing BOT_TOKEN or HF_API_TOKEN environment variables!")
        exit(1)

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(🇬🇧 English|🇸🇦 العربية)$"), set_language))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_user))

    logger.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
