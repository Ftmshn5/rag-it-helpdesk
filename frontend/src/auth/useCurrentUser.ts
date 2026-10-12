// Seçili kullanıcının tam bilgisi (rol, VIP): seçili id + kullanıcı listesi.

import { useUsers } from '@/api/queries/users'
import { useCurrentUserId } from '@/auth/currentUser'
import type { User } from '@/types/api'

export function useCurrentUser(): { user: User | null; isLoading: boolean } {
  const { userId } = useCurrentUserId()
  const users = useUsers()
  const user = users.data?.find((candidate) => candidate.id === userId) ?? null
  return { user, isLoading: users.isPending }
}
