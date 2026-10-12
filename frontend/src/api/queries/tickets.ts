// Talep okumaları (backend: GET /tickets/...). Hepsi useQuery; hiçbiri veri değiştirmez.

import { useQuery } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { TicketDetail, TicketStatus, TicketSummary } from '@/types/api'

function withStatus(path: string, status?: TicketStatus) {
  return status ? `${path}?status=${status}` : path
}

/** UC-03: kullanıcının kendi talepleri (en yeni önce). */
export function useMyTickets(status?: TicketStatus) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.tickets.mine(userId ?? 0, status),
    queryFn: () => apiRequest<TicketSummary[]>(withStatus('/tickets/mine', status), { userId: userId! }),
    enabled: userId !== null,
  })
}

/** UC-05: teknisyenin iş kuyruğu (öncelik puanı ve son tarihe göre). */
export function useAssignedTickets(status?: TicketStatus) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.tickets.assigned(userId ?? 0, status),
    queryFn: () =>
      apiRequest<TicketSummary[]>(withStatus('/tickets/assigned', status), { userId: userId! }),
    enabled: userId !== null,
  })
}

/** Yönetici kuyruğu (örn. ESCALATED: atama bekleyen talepler). */
export function useTicketQueue(status?: TicketStatus) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.tickets.queue(status),
    queryFn: () => apiRequest<TicketSummary[]>(withStatus('/tickets', status), { userId: userId! }),
    enabled: userId !== null,
  })
}

export function useTicketDetail(ticketId: number) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: [...queryKeys.tickets.detail(ticketId), userId],
    queryFn: () => apiRequest<TicketDetail>(`/tickets/${ticketId}`, { userId: userId! }),
    enabled: userId !== null,
  })
}
