import { Link } from 'react-router'

import { PageMessage } from '@/components/layout/PageMessage'
import { SlaCountdown } from '@/components/tickets/SlaCountdown'
import { TicketFlags } from '@/components/tickets/TicketBadges'
import { Card, CardContent } from '@/components/ui/card'
import { StatusBadge } from '@/components/ui/status-badge'
import { CATEGORY_LABELS } from '@/lib/labels'
import { formatDateTime } from '@/lib/format'
import type { TicketSummary } from '@/types/api'

interface TicketListProps {
  tickets: TicketSummary[]
  emptyMessage: string
  /** Kimin talebi olduğu (teknisyen/yönetici listelerinde anlamlı) */
  showRequester?: boolean
  /** İş kuyruğu görünümü: öncelik puanı ve son tarih öne çıkar */
  showPriority?: boolean
}

export function TicketList({ tickets, emptyMessage, showRequester, showPriority }: TicketListProps) {
  if (tickets.length === 0) {
    return <PageMessage title={emptyMessage} />
  }

  return (
    <ul className="space-y-2">
      {tickets.map((ticket) => (
        <li key={ticket.ticket_id}>
          <Link to={`/tickets/${ticket.ticket_id}`} className="block">
            <Card className="transition-colors hover:bg-muted/50">
              <CardContent className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm text-muted-foreground">#{ticket.ticket_id}</span>
                    <span className="font-medium">{ticket.title}</span>
                    <TicketFlags ticket={ticket} />
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    {CATEGORY_LABELS[ticket.category]}
                    {showRequester && ` · ${ticket.requester_name}`}
                    {ticket.device_asset_tag && ` · ${ticket.device_asset_tag}`}
                    {` · ${formatDateTime(ticket.created_at)}`}
                  </div>
                </div>

                {showPriority && <span className="text-sm text-muted-foreground">Öncelik {ticket.priority_score}</span>}
                <SlaCountdown ticket={ticket} />
                <StatusBadge kind={ticket.status} />
              </CardContent>
            </Card>
          </Link>
        </li>
      ))}
    </ul>
  )
}
