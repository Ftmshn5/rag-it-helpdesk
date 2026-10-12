// Seçili kullanıcı (kimlik doğrulama kapsam dışı: üst menüden seçilir, X-User-Id olarak gönderilir).
// Seçim tarayıcıda saklanır; sayfa yenilendiğinde aynı kullanıcıyla devam edilir.

import { useCallback, useState, type ReactNode } from 'react'

import { CurrentUserContext } from '@/auth/currentUser'

const STORAGE_KEY = 'currentUserId'

function readStoredUserId(): number | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value ? Number(value) : null
  } catch {
    return null // gizli pencere vb. durumlarda depolama kapalı olabilir
  }
}

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const [userId, setUserIdState] = useState<number | null>(readStoredUserId)

  const setUserId = useCallback((next: number | null) => {
    setUserIdState(next)
    try {
      if (next === null) localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, String(next))
    } catch {
      // depolama yoksa seçim yalnızca bu oturumda geçerli olur
    }
  }, [])

  return (
    <CurrentUserContext.Provider value={{ userId, setUserId }}>
      {children}
    </CurrentUserContext.Provider>
  )
}
