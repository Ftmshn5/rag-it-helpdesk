// Talep okumaları (backend: GET /tickets/...). Hepsi useQuery; hiçbiri veri değiştirmez.

import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo } from 'react'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { TicketDetail, TicketStatus, TicketSummary } from '@/types/api'

function withStatus(path: string, status?: TicketStatus) {
  return status ? `${path}?status=${status}` : path
}

/**
 * AI yanıtı backend'de arka planda üretilir (gerçek LLM saniyeler sürer).
 * Talep OPEN olduğu sürece ekran birkaç saniyede bir yeniden okur; yanıt gelince
 * (AI_ANSWERED / ESCALATED) yenileme kendiliğinden durur. Basit yoklama (polling)
 * yeterli: tek kullanıcılı demo için WebSocket/SSE gereksiz karmaşıklık olurdu.
 */
const AI_POLL_INTERVAL_MS = 3000

/** UC-03: kullanıcının kendi talepleri (en yeni önce). */
export function useMyTickets(status?: TicketStatus) {
  const { userId } = useCurrentUserId()
  return useQuery({
    queryKey: queryKeys.tickets.mine(userId ?? 0, status),
    queryFn: () => apiRequest<TicketSummary[]>(withStatus('/tickets/mine', status), { userId: userId! }),
    enabled: userId !== null,
    refetchInterval: (query) =>
      query.state.data?.some((ticket) => ticket.status === 'OPEN') ? AI_POLL_INTERVAL_MS : false,
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
    refetchInterval: (query) =>
      query.state.data?.summary.status === 'OPEN' ? AI_POLL_INTERVAL_MS : false,
  })
}

/**
 * Ekran görüntüsünü gösterilebilir bir adrese çevirir.
 * <img src> istek başlığı (X-User-Id) gönderemediği için dosya API istemcisiyle
 * Blob olarak indirilir ve tarayıcı içinde geçici bir "blob:" adresi oluşturulur.
 */
export function useAttachmentImage(ticketId: number, attachmentId: number) {
  const { userId } = useCurrentUserId()
  const query = useQuery({
    queryKey: queryKeys.tickets.attachment(ticketId, attachmentId, userId ?? 0),
    queryFn: () =>
      apiRequest<Blob>(`/tickets/${ticketId}/attachments/${attachmentId}`, {
        userId: userId!,
        responseType: 'blob',
      }),
    enabled: userId !== null,
    staleTime: Infinity, // yüklenen dosya değişmez
  })

  // Adres render sırasında türetilir; effect yalnızca temizlik içindir:
  // bileşen kaldırılınca veya dosya değişince eski adres serbest bırakılır.
  const url = useMemo(() => (query.data ? URL.createObjectURL(query.data) : null), [query.data])
  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [url])

  return { url, isPending: query.isPending, error: query.error }
}
