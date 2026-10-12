# Frontend (React + TypeScript + Vite)

Backend'den tamamen ayrı bir uygulamadır; aralarındaki tek bağ REST API'dir.

## Çalıştırma

```powershell
cd frontend
Copy-Item .env.example .env   # ilk seferde
npm install
npm run dev                   # http://localhost:5173
```

Backend'in de çalışıyor olması gerekir: `uvicorn app.main:app --reload` (proje kökünde).
