import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import type { User } from '@/types/api'

/** Kullanıcı seçme kutusu ve atama ekranı için tüm kullanıcılar. */
export function useUsers() {
  return useQuery({
    queryKey: queryKeys.users,
    queryFn: () => apiRequest<User[]>('/users'),
    staleTime: 5 * 60 * 1000, // kullanıcı listesi nadiren değişir
  })
}
