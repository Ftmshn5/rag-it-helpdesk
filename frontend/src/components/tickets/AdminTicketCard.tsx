// Talep detayında yöneticiye özel işlemler: teknisyen atama/devir (UC-10) ve
// aciliyet değiştirme. Aciliyet Decorator'ı (UrgentTicket) etkiler: SLA ve
// öncelik puanı backend'de yeniden hesaplanır, ekran güncel değeri okur.

import { useSetTicketUrgency } from '@/api/commands/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { AssignTechnicianForm } from '@/components/tickets/AssignTechnicianForm'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { TicketStatus, TicketSummary } from '@/types/api'

// domain/ticket_state.py ile aynı kurallar (yalnızca hangi bölümün görüneceği için)
const ASSIGNABLE: TicketStatus[] = ['ESCALATED', 'ASSIGNED', 'IN_PROGRESS']
const URGENCY_LOCKED: TicketStatus[] = ['RESOLVED', 'CLOSED']

export function AdminTicketCard({ ticket }: { ticket: TicketSummary }) {
  const setUrgency = useSetTicketUrgency()
  const canAssign = ASSIGNABLE.includes(ticket.status)
  const canChangeUrgency = !URGENCY_LOCKED.includes(ticket.status)
  if (!canAssign && !canChangeUrgency) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Yönetici işlemleri</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {canAssign && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              {ticket.assignee_name ? `Şu an: ${ticket.assignee_name}` : 'Henüz teknisyen atanmadı.'}
            </p>
            <AssignTechnicianForm
              ticketId={ticket.ticket_id}
              currentAssigneeId={ticket.assignee_id}
              supportLevel={ticket.support_level}
            />
          </div>
        )}
        {canChangeUrgency && (
          <div className="space-y-2">
            <Button
              variant="outline"
              disabled={setUrgency.isPending}
              onClick={() => setUrgency.mutate({ ticketId: ticket.ticket_id, isUrgent: !ticket.is_urgent })}
            >
              {ticket.is_urgent ? 'Acil işaretini kaldır' : 'Acil olarak işaretle'}
            </Button>
            <ErrorText error={setUrgency.error} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
