import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from huggingface_hub import InferenceClient

# إعداد المفاتيح
bot_token = os.environ.get('BOT_TOKEN')
hf_api_token = os.environ.get('HF_API_TOKEN')

# إنشاء عميل استدعاء النموذج
client = InferenceClient(token=hf_api_token)

# تخزين لغة كل مستخدم
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

# دالة بدء المحادثة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[k] for k in languages.keys()]
    await update.message.reply_text(
        welcome_text["en"] + "\n" + welcome_text["ar"],
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

# حفظ اللغة المختارة
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang_key = update.message.text
    if lang_key in languages:
        user_lang[update.effective_user.id] = languages[lang_key]
        await update.message.reply_text(help_text[languages[lang_key]])
    else:
        await update.message.reply_text("Invalid choice / اختيار غير صالح.")

# الرد على الرسائل
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, "en")
    query = update.message.text

    prompt = f"Answer this question about Cinema 4D in {lang}:\n{query}"

    try:
        response = client.text_generation(
            model="mistralai/Mixtral-8x7B-Instruct-v0.1",
            inputs=prompt,
            parameters={"max_new_tokens": 150}
        )
        # response هي قائمة، نأخذ النص من العنصر الأول
        generated_text = response[0].get("generated_text", help_text[lang])
        await update.message.reply_text(generated_text)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text(error_text[lang])

# تشغيل البوت
if __name__ == "__main__":
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(🇬🇧 English|🇸🇦 العربية)$"), set_language))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_user))

    app.run_polling()
