import { StatusBadge } from '@/components/ui/status-badge'
import type { TicketSummary } from '@/types/api'

/** Talebin işaretleri: VIP / Acil (Decorator'ların arayüzdeki karşılığı) ve üst destek seviyesi.
 * Gecikme ayrı bir rozet değil, SLA geri sayımının (SlaCountdown) bir halidir. */
export function TicketFlags({ ticket }: { ticket: TicketSummary }) {
  return (
    <>
      {ticket.is_vip && <StatusBadge kind="VIP" />}
      {ticket.is_urgent && <StatusBadge kind="URGENT" />}
      {ticket.support_level === 'TIER_2' && <StatusBadge kind="SENIOR" />}
    </>
  )
}
