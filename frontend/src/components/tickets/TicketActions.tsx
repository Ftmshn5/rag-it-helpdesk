// Talebin mevcut durumunda, görüntüleyen kişinin yapabileceği durum geçişleri.
//
// Hangi düğmenin görüneceği, backend'deki State kurallarının (domain/ticket_state.py)
// ve yetki kurallarının arayüzdeki bir yansımasıdır; yalnızca anlamsız düğme
// göstermemek içindir. Kuralın kendisi backend'de uygulanır: arayüz yanılsa
// bile backend 409/403 döner ve mesaj aşağıda gösterilir.

import type { UseMutationResult } from '@tanstack/react-query'

import {
  useCloseTicket,
  useReopenTicket,
  useResolveTicket,
  useStartWork,
} from '@/api/commands/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { TicketSummary } from '@/types/api'

export interface Viewer {
  isRequester: boolean
  isAssignee: boolean
  isAdmin: boolean
}

interface Action {
  label: string
  hint: string
  mutation: UseMutationResult<void, Error, number>
  variant?: 'default' | 'outline'
}

export function TicketActions({ ticket, viewer }: { ticket: TicketSummary; viewer: Viewer }) {
  const startWork = useStartWork()
  const resolve = useResolveTicket()
  const close = useCloseTicket()
  const reopen = useReopenTicket()

  const actions: Action[] = []
  if (ticket.status === 'ASSIGNED' && viewer.isAssignee) {
    actions.push({ label: 'Çalışmaya başla', hint: 'Talep üzerinde çalıştığınızı bildirir.', mutation: startWork })
  }
  if (ticket.status === 'IN_PROGRESS' && viewer.isAssignee) {
    actions.push({ label: 'Çözüldü olarak işaretle', hint: 'Talep sahibinin onayına gönderilir.', mutation: resolve })
  }
  if (ticket.status === 'RESOLVED' && (viewer.isRequester || viewer.isAdmin)) {
    actions.push({ label: 'Çözümü onayla ve kapat', hint: 'Talep kapanır.', mutation: close })
  }
  if (ticket.status === 'RESOLVED' && viewer.isRequester) {
    actions.push({
      label: 'Sorun devam ediyor',
      hint: 'Talep yeniden açılır ve teknik ekibe iletilir.',
      mutation: reopen,
      variant: 'outline',
    })
  }
  if (actions.length === 0) return null

  const error = actions.find((action) => action.mutation.error)?.mutation.error ?? null
  const isPending = actions.some((action) => action.mutation.isPending)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Yapılabilecek işlemler</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {actions.map((action) => (
            <Button
              key={action.label}
              variant={action.variant ?? 'default'}
              title={action.hint}
              disabled={isPending}
              onClick={() => action.mutation.mutate(ticket.ticket_id)}
            >
              {action.label}
            </Button>
          ))}
        </div>
        <ErrorText error={error} />
      </CardContent>
    </Card>
  )
}
