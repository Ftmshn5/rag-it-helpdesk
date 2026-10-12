import { Badge } from '@/components/ui/badge'
import { TICKET_STATUS_LABELS } from '@/lib/labels'
import type { TicketStatus, TicketSummary } from '@/types/api'

const STATUS_VARIANTS: Record<TicketStatus, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  OPEN: 'outline',
  AI_ANSWERED: 'default',
  ESCALATED: 'destructive',
  ASSIGNED: 'secondary',
  IN_PROGRESS: 'secondary',
  RESOLVED: 'default',
  CLOSED: 'outline',
}

export function TicketStatusBadge({ status }: { status: TicketStatus }) {
  return <Badge variant={STATUS_VARIANTS[status]}>{TICKET_STATUS_LABELS[status]}</Badge>
}

/** VIP / Acil / Gecikti işaretleri (Decorator'ların arayüzdeki karşılığı). */
export function TicketFlags({ ticket }: { ticket: TicketSummary }) {
  return (
    <>
      {ticket.is_vip && <Badge variant="outline">VIP</Badge>}
      {ticket.is_urgent && <Badge variant="destructive">Acil</Badge>}
      {ticket.is_overdue && <Badge variant="destructive">Gecikti</Badge>}
    </>
  )
}
