# bistlab web

bistlab API'sinin (FastAPI) Next.js arayüzü. Tasarım: koyu tema, Inter + JetBrains Mono.

```bash
# 1. terminal: API (repo kökünde)
uv run uvicorn bistlab.api.main:app --reload        # http://127.0.0.1:8000

# 2. terminal: arayüz
cd app && npm install && npm run dev                 # http://localhost:3000
```

API adresi `BISTLAB_API_URL` ile değiştirilebilir (varsayılan `http://127.0.0.1:8000`).
Sunucu bileşenleri API'yi sunucu tarafında çağırır. Eğitim amaçlıdır; yatırım tavsiyesi değildir.
