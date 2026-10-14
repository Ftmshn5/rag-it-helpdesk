// Bildirim okuması (backend: GET /notifications/mine). Her kullanıcı yalnızca kendisininkini görür.

import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { MyNotifications } from '@/types/api'

/**
 * Bildirimler başka kullanıcıların işlemleriyle (veya arka plandaki AI ile) oluşur;
 * sunucu tarafı itme (WebSocket) olmadığı için düzenli yoklanır. Sekme arka
 * plandayken TanStack Query yoklamayı kendiliğinden durdurur.
 */
const NOTIFICATION_POLL_INTERVAL_MS = 15_000

export function useMyNotifications() {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.notifications.mine(userId ?? 0),
    queryFn: () => apiRequest<MyNotifications>('/notifications/mine', { userId: userId! }),
    enabled: userId !== null,
    refetchInterval: NOTIFICATION_POLL_INTERVAL_MS,
  })
}
