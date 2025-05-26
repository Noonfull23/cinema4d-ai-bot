# استخدم صورة بايثون رسمية مع إصدار حديث (مثلاً 3.11)
FROM python:3.11-slim

# ضبط متغير البيئة لمنع buffering في اللوجات (اختياري)
ENV PYTHONUNBUFFERED=1

# إنشاء مجلد العمل داخل الحاوية
WORKDIR /app

# نسخ ملفات المتطلبات (requirements.txt) أولاً لتسريع بناء الصورة إذا لم تتغير
COPY requirements.txt .

# تثبيت المتطلبات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تعريف متغيرات البيئة (يمكن تعديلها أو إضافتها لاحقًا من لوحة HuggingFace)
ENV BOT_TOKEN=""
ENV HF_API_TOKEN=""

# الأمر لتشغيل البوت
CMD ["python", "bot.py"]