// Envanter yazmaları (backend: cihaz, zimmet ve bakım command'ları). Hepsi useMutation.
// Başarılı olunca tüm envanter sorguları (cihaz listesi, rapor, bakım geçmişi,
// kullanıcının zimmetli cihazları) yenilenir.

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

// --- Yönetici ---

export interface DeviceDetailsInput {
  type: string
  brand: string
  model: string
  location?: string | null
  purchase_date?: string | null // YYYY-MM-DD
}

export interface RegisterDeviceInput extends DeviceDetailsInput {
  asset_tag: string
  serial_number: string
}

/** UC-08: cihaz ekle (depoya, IN_STOCK olarak girer). */
export function useRegisterDevice() {
  return useInventoryCommand<RegisterDeviceInput, Created>((input) => ({
    path: '/devices',
    body: input,
  }))
}

/**
 * UC-08: cihaz bilgilerini güncelle. Demirbaş ve seri no kimliktir, güncellenmez;
 * durum da burada yok (iş kuralı 6). null gönderilen alan değişmez.
 */
export function useUpdateDevice() {
  return useInventoryCommand<{ deviceId: number; details: Partial<DeviceDetailsInput> }>(
    ({ deviceId, details }) => ({ path: `/devices/${deviceId}`, method: 'PATCH', body: details }),
  )
}

/** UC-09: cihazı kullanıcıya zimmetle (yalnızca depodaki cihaz; iş kuralı 1, 7). */
export function useAssignDevice() {
  return useInventoryCommand<{ deviceId: number; userId: number }, Created>(
    ({ deviceId, userId }) => ({
      path: `/devices/${deviceId}/assignments`,
      body: { user_id: userId },
    }),
  )
}

/** UC-09: cihazı iade al (bakımdaki cihaz iade alınamaz; iş kuralı 9). */
export function useReturnDevice() {
  return useInventoryCommand<number>((deviceId) => ({ path: `/devices/${deviceId}/return` }))
}

/** Cihazı hurdaya ayır (yalnızca depodaki cihaz; iş kuralı 7). */
export function useRetireDevice() {
  return useInventoryCommand<number>((deviceId) => ({ path: `/devices/${deviceId}/retire` }))
}
