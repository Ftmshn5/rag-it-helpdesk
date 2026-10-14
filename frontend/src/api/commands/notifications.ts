// Bildirim yazmaları (backend: POST /notifications/read).

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'

/** Seçilen bildirimleri okundu işaretler; liste boşsa tüm okunmamışları. */
export function useMarkNotificationsRead() {
  const { userId } = useCurrentUserId()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (notificationIds: number[]) =>
      apiRequest<void>('/notifications/read', {
        method: 'POST',
        body: { notification_ids: notificationIds },
        userId: userId!,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all }),
  })
}
