import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from huggingface_hub import InferenceClient

# إعداد المفاتيح
bot_token = os.environ.get("BOT_TOKEN")
hf_api_token = os.environ.get("HF_API_TOKEN")
client = InferenceClient(model="mistralai/Mixtral-8x7B-Instruct-v0.1", token=hf_api_token)

# تخزين اللغة لكل مستخدم وسجل الأسئلة
user_lang = {}
user_logs = []  # مؤقتًا نستخدم قائمة في الذاكرة. يمكن نقلها إلى قاعدة بيانات لاحقًا.

languages = {
    "🇬🇧 English": "en",
    "🇸🇦 العربية": "ar"
}

texts = {
    "welcome": {
        "en": "Welcome to the Cinema 4D Assistant Bot!\nChoose your language:",
        "ar": "مرحبًا بك في مساعد Cinema 4D!\nيرجى اختيار لغتك:"
    },
    "help": {
        "en": "Ask me anything about Cinema 4D!",
        "ar": "اسألني عن Cinema 4D!"
    },
    "error": {
        "en": "\u274c Something went wrong. Please try again.",
        "ar": "\u274c حدث خطأ. حاول مرة أخرى."
    },
    "about": {
        "en": "I'm a bot powered by AI to help you learn Cinema 4D step by step.",
        "ar": "أنا بوت مدعوم بذكاء صناعي لمساعدتك في تعلم Cinema 4D خطوة بخطوة."
    },
    "feedback": {
        "en": "You can send suggestions anytime. Just type your message.",
        "ar": "يمكنك إرسال اقتراحاتك في أي وقت. فقط اكتب رسالتك."
    }
}

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[k] for k in languages.keys()]
    await update.message.reply_text(
        texts["welcome"]["en"] + "\n" + texts["welcome"]["ar"],
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    )

# اختيار اللغة
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang_key = update.message.text
    if lang_key in languages:
        lang = languages[lang_key]
        user_lang[update.effective_user.id] = lang
        await update.message.reply_text(texts["help"][lang])
    else:
        await update.message.reply_text("Invalid choice / اختيار غير صالح")

# الرد على الأسئلة
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_lang.get(user_id, "en")
    query = update.message.text
    prompt = f"Answer this question about Cinema 4D in {lang}: {query}"

    try:
        response = client.text_generation(prompt)
        answer = response.strip()
        await update.message.reply_text(answer)
        user_logs.append({
            "user_id": user_id,
            "lang": lang,
            "question": query,
            "answer": answer,
            "time": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text(texts["error"][lang])

# /about
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_lang.get(update.effective_user.id, "en")
    await update.message.reply_text(texts["about"][lang])

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_lang.get(update.effective_user.id, "en")
    await update.message.reply_text(texts["help"][lang])

# /feedback
async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = user_lang.get(update.effective_user.id, "en")
    await update.message.reply_text(texts["feedback"][lang])

if __name__ == "__main__":
    app = ApplicationBuilder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("feedback", feedback))

    app.add_handler(MessageHandler(filters.Regex("^(\ud83c\uddec\ud83c\udde7 English|\ud83c\uddf8\ud83c\udde6 العربية)$"), set_language))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_user))

    app.run_polling()
