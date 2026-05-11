# TTS API — XTTS v2

API Text-to-Speech basée sur **FastAPI** et **Coqui XTTS v2** avec **clonage de voix**.

## Prérequis

- Python 3.10+
- GPU NVIDIA recommandé (fonctionne aussi en CPU, mais plus lent)

## Installation

```bash
pip install -r requirements.txt
```

> Le premier lancement télécharge automatiquement le modèle XTTS v2 (~1.8 GB).

## Lancement

```bash
python main.py
```

Le serveur démarre sur `http://localhost:8000`. Documentation interactive :

- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

## Endpoints

| Méthode | Route        | Description                              |
| ------- | ------------ | ---------------------------------------- |
| POST    | `/tts`       | Synthèse vocale avec clonage de voix     |
| GET     | `/languages` | Liste les langues supportées             |
| GET     | `/speakers`  | Liste les voix de référence stockées     |
| POST    | `/speakers`  | Upload d'une voix de référence (WAV)     |
| GET     | `/health`    | Health check                             |

## Utilisation

### 1. Uploader une voix de référence

```bash
curl -X POST http://localhost:8000/speakers \
  -F "name=ma_voix" \
  -F "file=@reference.wav"
```

> Le WAV de référence doit durer **6 à 30 secondes** pour un bon clonage.

### 2. Synthèse vocale

**Avec un speaker stocké :**
```bash
curl -X POST http://localhost:8000/tts \
  -F "text=Bonjour le monde" \
  -F "language=fr" \
  -F "speaker=ma_voix" \
  --output output.wav
```

**Avec un WAV uploadé directement :**
```bash
curl -X POST http://localhost:8000/tts \
  -F "text=Hello world" \
  -F "language=en" \
  -F "speaker_wav=@reference.wav" \
  --output output.wav
```

### Paramètres TTS

| Paramètre     | Défaut     | Description                                         |
| ------------- | ---------- | --------------------------------------------------- |
| `text`        | *(requis)* | Texte à convertir                                   |
| `language`    | `fr`       | Code langue (`en`, `fr`, `ja`, `de`, etc.)          |
| `speaker`     | *(aucun)*  | Nom d'un speaker stocké                             |
| `speaker_wav` | *(aucun)*  | Fichier WAV de référence uploadé dans la requête    |

### Langues supportées

`en`, `es`, `fr`, `de`, `it`, `pt`, `pl`, `tr`, `ru`, `nl`, `cs`, `ar`, `zh-cn`, `ja`, `hu`, `ko`, `hi`
