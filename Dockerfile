FROM python:3.11-slim

# OS darajasidagi kerakli paketlarni o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Ishchi katalogni yaratish
WORKDIR /app

# Loyiha fayllarini nusxalash
COPY requirements.txt .

# Python kutubxonalarini o'rnatish
RUN pip install --no-cache-dir -r requirements.txt

# Barcha kodlarni nusxalash
COPY src/ /app/src/

# Environment parametrlarini nastroyka qilish (Northflank UI orqali kiritiladi)
# Northflank'da papka permission muammolari bo'lmasligi uchun
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Ishga tushirish buyrug'i
CMD ["python", "src/bot/main.py"]
