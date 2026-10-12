import { useEffect, useState } from 'react'

// Geçici sayfa (9a): frontend'in backend'e CORS üzerinden ulaşabildiğini doğrular.
// 9b'de API istemcisi ve TanStack Query, 9c'de rol seçici ve sayfalar gelecek.

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

type Health = { status: string; database: string }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((response) => response.json())
      .then(setHealth)
      .catch(() => setError('Backend’e ulaşılamadı.'))
  }, [])

  return (
    <main className="mx-auto max-w-xl p-8">
      <h1 className="text-2xl font-semibold text-slate-900">BT Destek ve Envanter</h1>
      <p className="mt-4 text-slate-600">
        Backend durumu:{' '}
        {error ? (
          <span className="font-medium text-red-600">{error}</span>
        ) : health ? (
          <span className="font-medium text-emerald-600">
            {health.status} (veritabanı: {health.database})
          </span>
        ) : (
          'kontrol ediliyor…'
        )}
      </p>
    </main>
  )
}
