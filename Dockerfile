# Используем стабильный Python
FROM python:3.11-slim

# Устанавливаем зависимости ОС
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git wget build-essential \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Скопировать файлы проекта
COPY . /app

# Обновить pip и поставить Python-зависимости
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Запуск бота
CMD ["python", "bot_minus.py"]
