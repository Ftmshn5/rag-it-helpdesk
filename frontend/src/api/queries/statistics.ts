// Arıza istatistikleri okuması (backend: GET /statistics/failures). Yalnızca yönetici.

import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { FailureStatistics } from '@/types/api'

/** UC-12: kategori, haftalık eğilim, SLA ve AI başarısı. */
export function useFailureStatistics(weeks: number) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.tickets.statistics(weeks),
    queryFn: () => apiRequest<FailureStatistics>(`/statistics/failures?weeks=${weeks}`, { userId: userId! }),
    enabled: userId !== null,
  })
}
