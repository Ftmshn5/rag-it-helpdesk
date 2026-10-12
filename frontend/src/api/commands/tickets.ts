// Talep yazmaları (backend: POST /tickets...). Hepsi useMutation.
//
// Kalıp: command başarılı olunca etkilediği okumaların önbelleği geçersiz
// kılınır (invalidate); ekran güncel veriyi query tarafından yeniden okur.
// Command'ın yanıtından veri "tahmin edilmez" — backend'deki CQRS ile aynı fikir.
//
// Diğer talep command'ları (değerlendirme, atama, durum geçişleri, not, ek)
// ekranlarıyla birlikte 10. adımda bu dosyaya eklenecek.

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiRequest } from '@/api/client'
import { queryKeys } from '@/api/queryKeys'
import { useCurrentUserId } from '@/auth/currentUser'
import type { Created, TicketCategory } from '@/types/api'

export interface CreateTicketInput {
  title: string
  description: string
  category: TicketCategory
  is_urgent: boolean
  device_id?: number | null
}

/** UC-01: arıza kaydı oluştur. */
export function useCreateTicket() {
  const { userId } = useCurrentUserId()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: CreateTicketInput) =>
      apiRequest<Created>('/tickets', { method: 'POST', body: input, userId: userId! }),
    onSuccess: () =>
      // Yeni talep "taleplerim" listesinde, AI'ın sonucu ise kuyruklarda görünür
      queryClient.invalidateQueries({ queryKey: queryKeys.tickets.all }),
  })
}
