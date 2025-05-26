import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from huggingface_hub import InferenceClient
from langdetect import detect, LangDetectException

# --- إعداد Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- متغيرات البيئة ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_API_TOKEN = os.environ.get("HF_API_TOKEN")

# --- إعداد خدمات Inference متعددة (يمكن إضافة خدمات أخرى بسهولة) ---
services = [
    InferenceClient(token=HF_API_TOKEN, repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1"),
    InferenceClient(token=HF_API_TOKEN, repo_id="TheBloke/Mistral-7B-Claude-Chat-GGUF"),
]

# --- تخزين المحادثات مؤقتًا في الذاكرة {user_id: [ {role:"user|assistant", content:".."}, ... ]} ---
user_contexts = {}

# --- تتبع خدمة الـInference المستخدمة لكل مستخدم لتبديل ذكي ---
user_service_idx = {}

# --- إعدادات ---
MAX_CONTEXT_LENGTH = 3000  # تقريبياً عدد الحروف (يمكن تعديل حسب الحاجة)

# --- دوال مساعدة ---

def trim_context(context):
    """
    تقليص سياق المحادثة ليظل في حدود MAX_CONTEXT_LENGTH
    """
    total_len = 0
    trimmed = []
    # نبدأ من آخر الرسائل للخلف (للحفاظ على آخر المحادثات)
    for msg in reversed(context):
        total_len += len(msg["content"])
        if total_len > MAX_CONTEXT_LENGTH:
            break
        trimmed.insert(0, msg)
    return trimmed

async def build_prompt(context_list):
    """
    بناء البرومبت للنموذج مع فواصل أدوار المحادثة.
    """
    prompt = ""
    for msg in context_list:
        role = "User" if msg["role"] == "user" else "Assistant"
        prompt += f"{role}: {msg['content']}\n"
    prompt += "Assistant: "
    return prompt

def get_user_service(user_id):
    """
    استرجاع رقم خدمة Inference المستخدمة حاليًا للمستخدم، أو 0 افتراضياً.
    """
    return user_service_idx.get(user_id, 0)

def switch_user_service(user_id):
    """
    تبديل الخدمة المستخدمة (تدور بين الخدمات المتوفرة)
    """
    current_idx = user_service_idx.get(user_id, 0)
    next_idx = (current_idx + 1) % len(services)
    user_service_idx[user_id] = next_idx
    return next_idx

def get_language(text):
    """
    كشف لغة النص مع معالجة الأخطاء
    """
    try:
        lang = detect(text)
    except LangDetectException:
        lang = "en"
    return lang

# --- أوامر التليجرام ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "مرحبًا بك في بوت دعم Cinema 4D الذكي!\n\n"
        "يمكنك سؤالي أي شيء، وسأجيبك بأفضل ما أستطيع.\n"
        "للبدء، فقط اكتب سؤالك.\n\n"
        "أوامر مفيدة:\n"
        "/reset - إعادة تعيين المحادثة\n"
        "/help - عرض المساعدة\n"
    )
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "البوت يدعم المحادثة الذكية مع حفظ سياق المحادثة.\n"
        "يمكنك استخدام:\n"
        "/reset - لمسح المحادثة الحالية\n"
        "يمكنك كتابة أي سؤال أو طلب وسيتم الرد عليك.\n"
        "أيضًا يمكنك استخدام الأزرار في أسفل الرسالة للتفاعل بشكل أسرع."
    )
    await update.message.reply_text(help_text)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_contexts[user_id] = []
    user_service_idx[user_id] = 0
    await update.message.reply_text("تم إعادة تعيين المحادثة، يمكنك البدء من جديد.")

async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # تحديث السياق
    ctx = user_contexts.get(user_id, [])
    ctx.append({"role": "user", "content": text})
    ctx = trim_context(ctx)

    prompt = await build_prompt(ctx)
    user_contexts[user_id] = ctx

    # اختيار خدمة inference
    service_idx = get_user_service(user_id)
    client = services[service_idx]

    try:
        # طلب الرد من النموذج
        response = client.text_generation(prompt, max_new_tokens=256, do_sample=True)
        answer = response.generated_text[len(prompt):].strip()

        # إضافة رد المساعد للسياق
        ctx.append({"role": "assistant", "content": answer})
        user_contexts[user_id] = ctx

        # أزرار تفاعلية
        keyboard = [
            [
                InlineKeyboardButton("إعادة صياغة", callback_data="rephrase"),
                InlineKeyboardButton("إعادة تعيين", callback_data="reset"),
                InlineKeyboardButton("تغيير اللغة", callback_data="change_lang"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(answer, reply_markup=reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in text_generation: {e}")
        # التبديل لخدمة أخرى تلقائيًا
        new_idx = switch_user_service(user_id)
        await update.message.reply_text(
            f"حدث خطأ في الخدمة الحالية. أحاول التبديل لخدمة أخرى... (الخدمة {new_idx + 1})"
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    data = query.data
    if data == "reset":
        user_contexts[user_id] = []
        user_service_idx[user_id] = 0
        await query.edit_message_text("تمت إعادة تعيين المحادثة بنجاح. يمكنك البدء من جديد.")
    elif data == "rephrase":
        ctx = user_contexts.get(user_id, [])
        if not ctx:
            await query.edit_message_text("لا يوجد سياق لإعادة الصياغة، ابدأ بالسؤال أولًا.")
            return

        # خذ آخر سؤال فقط لإعادة الصياغة
        last_user_msg = None
        for msg in reversed(ctx):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if not last_user_msg:
            await query.edit_message_text("لم أجد سؤالًا لإعادة صياغته.")
            return

        # بناء برومبت خاص لإعادة الصياغة
        rephrase_prompt = f"أعد صياغة السؤال التالي بطريقة أبسط وأكثر وضوحًا:\n{last_user_msg}"

        # استخدم نفس خدمة المستخدم الحالية
        service_idx = get_user_service(user_id)
        client = services[service_idx]

        try:
            response = client.text_generation(rephrase_prompt, max_new_tokens=128)
            new_question = response.generated_text[len(rephrase_prompt):].strip()
            # استبدل آخر سؤال بالسؤال الجديد
            for i in range(len(ctx) - 1, -1, -1):
                if ctx[i]["role"] == "user":
                    ctx[i]["content"] = new_question
                    break
            user_contexts[user_id] = ctx
            await query.edit_message_text(f"تمت إعادة صياغة السؤال:\n\n{new_question}")
        except Exception as e:
            logger.error(f"Error in rephrase: {e}")
            await query.edit_message_text("حدث خطأ أثناء إعادة الصياغة، حاول لاحقًا.")

    elif data == "change_lang":
        # فقط مثال: إعادة تعيين المحادثة مع رسالة بالإنجليزية أو العربية
        user_contexts[user_id] = []
        user_service_idx[user_id] = 0
        await query.edit_message_text(
            "تمت إعادة تعيين المحادثة.\nيرجى كتابة سؤالك باللغة التي تفضلها الآن."
        )
    else:
        await query.edit_message_text("الزر غير معروف.")

# --- نقطة بداية البوت ---
def main():
    if not BOT_TOKEN or not HF_API_TOKEN:
        logger.error("BOT_TOKEN أو HF_API_TOKEN غير معرفين في متغيرات البيئة.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_query))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("البوت بدأ العمل...")
    app.run_polling()

if __name__ == "__main__":
    main()
