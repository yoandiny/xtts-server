FROM pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV COQUI_TOS_AGREED=1

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY main.py .

# Volumes: model cache + speakers
RUN mkdir -p /app/speakers /root/.local/share/tts
VOLUME /app/speakers
VOLUME /root/.local/share/tts

EXPOSE 8000

CMD ["python", "main.py"]
