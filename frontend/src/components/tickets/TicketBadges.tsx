import { StatusBadge } from '@/components/ui/status-badge'
import type { TicketSummary } from '@/types/api'

/** Talebin işaretleri: VIP / Acil (Decorator'ların arayüzdeki karşılığı), Gecikti ve üst destek seviyesi. */
export function TicketFlags({ ticket }: { ticket: TicketSummary }) {
  return (
    <>
      {ticket.is_vip && <StatusBadge kind="VIP" />}
      {ticket.is_urgent && <StatusBadge kind="URGENT" />}
      {ticket.is_overdue && <StatusBadge kind="OVERDUE" />}
      {ticket.support_level === 'TIER_2' && <StatusBadge kind="SENIOR" />}
    </>
  )
}
