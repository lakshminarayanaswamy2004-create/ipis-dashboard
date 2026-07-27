FROM python:3.11-slim

WORKDIR /app

# ffmpeg is required by pydub for mp3 -> wav conversion
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000
EXPOSE 10000

CMD gunicorn -w 2 -b 0.0.0.0:$PORT --chdir backend app:app
