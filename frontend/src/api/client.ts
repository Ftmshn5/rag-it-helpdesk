// Backend ile konuşan tek yer. Bileşenler bu dosyayı doğrudan kullanmaz;
// yalnızca api/queries ve api/commands altındaki hook'lar kullanır.

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

/** Backend'in döndürdüğü hata; `message` Türkçe ve kullanıcıya gösterilebilir. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions {
  /** İşlemi yapan kullanıcı (X-User-Id). Kimlik doğrulama kapsam dışı. */
  userId?: number
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH'
  /** JSON gövde ya da dosya yüklemesi için FormData */
  body?: unknown
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { userId, method = 'GET', body } = options
  const headers: Record<string, string> = {}
  if (userId !== undefined) headers['X-User-Id'] = String(userId)

  let payload: BodyInit | undefined
  if (body instanceof FormData) {
    payload = body // Content-Type'ı (sınır bilgisiyle) tarayıcı kendisi ayarlar
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { method, headers, body: payload })
  } catch {
    throw new ApiError(0, 'Sunucuya ulaşılamadı. Backend çalışıyor mu?')
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  if (response.status === 204) return undefined as T // command'ların "içerik yok" yanıtı
  return (await response.json()) as T
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') return data.detail // backend'in Türkçe mesajı
  } catch {
    // gövde JSON değil
  }
  return `Beklenmeyen bir hata oluştu (HTTP ${response.status}).`
}
