// Seçili kullanıcının context'i ve okuma hook'u (sağlayıcı bileşen: CurrentUserProvider.tsx).

import { createContext, useContext } from 'react'

export interface CurrentUserState {
  userId: number | null
  setUserId: (userId: number | null) => void
}

export const CurrentUserContext = createContext<CurrentUserState | null>(null)

export function useCurrentUserId(): CurrentUserState {
  const context = useContext(CurrentUserContext)
  if (!context) throw new Error('useCurrentUserId, CurrentUserProvider içinde kullanılmalı')
  return context
}
