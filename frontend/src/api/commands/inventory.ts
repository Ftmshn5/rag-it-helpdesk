// Envanter yazmaları (backend: cihaz, zimmet ve bakım command'ları). Hepsi useMutation.
// Başarılı olunca tüm envanter sorguları (cihaz listesi, rapor, bakım geçmişi) yenilenir.
//
// Yönetici command'ları (cihaz ekle/güncelle/hurdaya ayır, zimmetle/iade) 10c'de eklenecek.

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { Created, MaintenanceType } from '@/types/api'

function useInventoryCommand<TInput, TResult = void>(
  request: (input: TInput) => { path: string; method?: 'POST' | 'PATCH'; body?: unknown },
) {
  const { userId } = useCurrentUserId()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: TInput) => {
      const { path, method = 'POST', body } = request(input)
      return apiRequest<TResult>(path, { method, body, userId: userId! })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.inventory.all }),
  })
}

export interface StartMaintenanceInput {
  deviceId: number
  type: MaintenanceType
  description: string
  ticketId?: number | null
}

/** UC-16: bakım kaydı aç (cihaz IN_REPAIR olur; iş kuralı 2). */
export function useStartMaintenance() {
  return useInventoryCommand<StartMaintenanceInput, Created>(
    ({ deviceId, type, description, ticketId }) => ({
      path: `/devices/${deviceId}/maintenance-records`,
      body: { type, description, ticket_id: ticketId ?? null },
    }),
  )
}

/** UC-16: bakımı tamamla (cihaz bakım öncesi durumuna döner). */
export function useCompleteMaintenance() {
  return useInventoryCommand<number>((recordId) => ({
    path: `/maintenance-records/${recordId}/complete`,
  }))
}
