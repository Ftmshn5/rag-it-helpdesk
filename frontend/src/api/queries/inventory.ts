// Envanter okumaları (backend: GET /inventory/report, /devices/mine, /devices/{id}/maintenance-records).

import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { DeviceInventory, DeviceStatus, InventoryReport, MaintenanceRecord } from '@/types/api'

/** UC-11: envanter raporu (yönetici). */
export function useInventoryReport(status?: DeviceStatus, type?: string) {
  const { userId } = useCurrentUserId()
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (type) params.set('type', type)
  const query = params.size ? `?${params}` : ''

  return useQuery({
    queryKey: queryKeys.inventory.report(status, type),
    queryFn: () => apiRequest<InventoryReport>(`/inventory/report${query}`, { userId: userId! }),
    enabled: userId !== null,
  })
}

/** UC-04: kullanıcının zimmetli cihazları. */
export function useMyDevices() {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.inventory.mine(userId ?? 0),
    queryFn: () => apiRequest<DeviceInventory[]>('/devices/mine', { userId: userId! }),
    enabled: userId !== null,
  })
}

/** UC-17: cihazın bakım geçmişi (teknisyen, yönetici). */
export function useMaintenanceHistory(deviceId: number) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.inventory.maintenance(deviceId),
    queryFn: () =>
      apiRequest<MaintenanceRecord[]>(`/devices/${deviceId}/maintenance-records`, {
        userId: userId!,
      }),
    enabled: userId !== null,
  })
}

/** Cihaz listesi (teknisyen: bakım kaydı; yönetici: zimmet işlemleri). */
export function useDevices(status?: DeviceStatus) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.inventory.devices(status),
    queryFn: () =>
      apiRequest<DeviceInventory[]>(status ? `/devices?status=${status}` : '/devices', {
        userId: userId!,
      }),
    enabled: userId !== null,
  })
}
