// UC-07: atanan teknisyen talebi kıdemli teknisyene (L2) eskale eder.
//
// Kartın görünmesi backend kurallarının yansımasıdır: State (yalnızca ASSIGNED /
// IN_PROGRESS) ve Chain of Responsibility (L2 en üst seviye, daha fazla eskale
// edilemez). Kural backend'de uygulanır; arayüz yanılırsa 409 mesajı gösterilir.
//
// Eskalasyondan sonra talep teknisyenden alınır (yeniden atama kuyruğuna döner);
// teknisyen talebi artık göremeyeceği için atanan talepler listesine yönlendirilir.

import { type FormEvent, useState } from 'react'
import { useNavigate } from 'react-router'

import { useEscalateTicket } from '@/api/commands/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import type { TicketSummary } from '@/types/api'

const MIN_REASON_LENGTH = 3

export function EscalateTicketCard({ ticket }: { ticket: TicketSummary }) {
  const escalate = useEscalateTicket()
  const navigate = useNavigate()
  const [reason, setReason] = useState('')

  const canEscalate =
    (ticket.status === 'ASSIGNED' || ticket.status === 'IN_PROGRESS') && ticket.support_level === 'TIER_1'
  if (!canEscalate) return null

  const trimmed = reason.trim()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (trimmed.length < MIN_REASON_LENGTH) return
    await escalate.mutateAsync({ ticketId: ticket.ticket_id, reason: trimmed })
    navigate('/technician/queue')
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Üst seviyeye eskale et</CardTitle>
        <CardDescription>
          Talep, kıdemli teknisyene atanmak üzere yöneticiye döner. Gerekçe talebe not olarak eklenir.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-2">
          <Textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Neden üst seviye gerekiyor? (örn. anakart arızası, yetki dışı işlem)"
            rows={3}
            maxLength={2000}
            aria-label="Eskalasyon gerekçesi"
          />
          <ErrorText error={escalate.error} />
          <Button
            type="submit"
            variant="outline"
            size="sm"
            disabled={escalate.isPending || trimmed.length < MIN_REASON_LENGTH}
          >
            Eskale et
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
