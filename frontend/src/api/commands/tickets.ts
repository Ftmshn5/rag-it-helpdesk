// Talep yazmaları (backend: POST/PUT /tickets...). Hepsi useMutation.
//
// Kalıp: command başarılı olunca etkilediği okumaların önbelleği geçersiz
// kılınır (invalidate); ekran güncel veriyi query tarafından yeniden okur.
// Command'ın yanıtından veri "tahmin edilmez" — backend'deki CQRS ile aynı fikir.

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { Created, TicketCategory, TicketStatus } from '@/types/api'

/**
 * Talep command'ları için ortak hook: isteği seçili kullanıcı adına gönderir,
 * başarılı olunca tüm talep sorgularını (listeler + detay) yeniler.
 */
function useTicketCommand<TInput, TResult = void>(
  request: (input: TInput) => { path: string; method?: 'POST' | 'PUT'; body?: unknown },
) {
  const { userId } = useCurrentUserId()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: TInput) => {
      const { path, method = 'POST', body } = request(input)
      return apiRequest<TResult>(path, { method, body, userId: userId! })
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.tickets.all }),
  })
}

// --- Kullanıcı ---

export interface CreateTicketInput {
  title: string
  description: string
  category: TicketCategory
  is_urgent: boolean
  device_id?: number | null
}

/** UC-01: arıza kaydı oluştur. */
export function useCreateTicket() {
  return useTicketCommand<CreateTicketInput, Created>((input) => ({ path: '/tickets', body: input }))
}

/** UC-15: talebe ekran görüntüsü ekle (multipart/form-data). */
export function useAttachScreenshot() {
  return useTicketCommand<{ ticketId: number; file: File }, Created>(({ ticketId, file }) => {
    const form = new FormData()
    form.append('file', file)
    return { path: `/tickets/${ticketId}/attachments`, body: form }
  })
}

/** UC-02: AI önerisini değerlendir (çözüldü → kapanır, çözülmedi → eskale). */
export function useEvaluateAiAnswer() {
  return useTicketCommand<{ ticketId: number; isHelpful: boolean }>(({ ticketId, isHelpful }) => ({
    path: `/tickets/${ticketId}/ai-feedback`,
    body: { is_helpful: isHelpful },
  }))
}

/** Çözümü onayla (RESOLVED → CLOSED): talep sahibi veya yönetici. */
export function useCloseTicket() {
  return useTicketCommand<number>((ticketId) => ({ path: `/tickets/${ticketId}/close` }))
}

/** Sorun sürüyor (RESOLVED → ESCALATED): yalnızca talep sahibi. */
export function useReopenTicket() {
  return useTicketCommand<number>((ticketId) => ({ path: `/tickets/${ticketId}/reopen` }))
}

/** UC-06: not ekle (talebin tarafları). */
export function useAddComment() {
  return useTicketCommand<{ ticketId: number; content: string }, Created>(
    ({ ticketId, content }) => ({ path: `/tickets/${ticketId}/comments`, body: { content } }),
  )
}

// --- Teknisyen ---

/** UC-06: çalışmaya başla (ASSIGNED → IN_PROGRESS). */
export function useStartWork() {
  return useTicketCommand<number>((ticketId) => ({ path: `/tickets/${ticketId}/start` }))
}

/**
 * E2 Kanban: talebi hedef duruma taşı. Hangi taşımanın geçerli olduğuna backend (State)
 * karar verir; geçersizse 409 ve Türkçe mesaj döner (ApiError.message).
 */
export function useMoveTicket() {
  return useTicketCommand<{ ticketId: number; status: TicketStatus }>(({ ticketId, status }) => ({
    path: `/tickets/${ticketId}/move`,
    body: { status },
  }))
}

/** UC-06: çözüldü olarak işaretle (IN_PROGRESS → RESOLVED). */
export function useResolveTicket() {
  return useTicketCommand<number>((ticketId) => ({ path: `/tickets/${ticketId}/resolve` }))
}

/** UC-07: üst seviyeye eskale et (ASSIGNED / IN_PROGRESS → ESCALATED, seviye L1 → L2). */
export function useEscalateTicket() {
  return useTicketCommand<{ ticketId: number; reason: string }>(({ ticketId, reason }) => ({
    path: `/tickets/${ticketId}/escalate`,
    body: { reason },
  }))
}

// --- Yönetici ---

/** UC-10: talebi teknisyene ata. */
export function useAssignTicket() {
  return useTicketCommand<{ ticketId: number; technicianId: number }>(
    ({ ticketId, technicianId }) => ({
      path: `/tickets/${ticketId}/assign`,
      body: { technician_id: technicianId },
    }),
  )
}

/** Acil işaretini değiştir (yönetici). */
export function useSetTicketUrgency() {
  return useTicketCommand<{ ticketId: number; isUrgent: boolean }>(({ ticketId, isUrgent }) => ({
    path: `/tickets/${ticketId}/urgency`,
    method: 'PUT',
    body: { is_urgent: isUrgent },
  }))
}
