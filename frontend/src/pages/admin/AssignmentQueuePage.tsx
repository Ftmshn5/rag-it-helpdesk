// UC-10: eskale edilmiş (AI çözemedi / kullanıcı "çözülmedi" dedi / yeniden açıldı)
// talepler teknisyene atanır. Sıra backend'den gelir: öncelik puanı, sonra son tarih.
// "Tüm talepler" görünümü yöneticinin genel takibi içindir.

import { useState } from 'react'
import { Link } from 'react-router'

import { useTicketQueue } from '@/api/queries/tickets'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { AssignTechnicianForm } from '@/components/tickets/AssignTechnicianForm'
import { TicketFlags } from '@/components/tickets/TicketBadges'
import { TicketList } from '@/components/tickets/TicketList'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { formatDateTime } from '@/lib/format'
import { CATEGORY_LABELS } from '@/lib/labels'
import type { TicketSummary } from '@/types/api'

/** Teknisyen başına üzerindeki açık (atanmış / çalışılan) talep sayısı. */
function countWorkload(tickets: TicketSummary[]) {
  const workload = new Map<number, number>()
  for (const ticket of tickets) {
    if (ticket.assignee_id && (ticket.status === 'ASSIGNED' || ticket.status === 'IN_PROGRESS')) {
      workload.set(ticket.assignee_id, (workload.get(ticket.assignee_id) ?? 0) + 1)
    }
  }
  return workload
}

export function AssignmentQueuePage() {
  const [showAll, setShowAll] = useState(false)
  const allTickets = useTicketQueue()

  return (
    <>
      <PageHeader
        title={showAll ? 'Tüm talepler' : 'Atama bekleyenler'}
        description={
          showAll
            ? 'Sistemdeki tüm talepler.'
            : 'Eskale edilmiş, teknisyen ataması bekleyen talepler (öncelik sırasıyla).'
        }
        actions={
          <Button variant="outline" onClick={() => setShowAll((value) => !value)}>
            {showAll ? 'Atama bekleyenler' : 'Tüm talepler'}
          </Button>
        }
      />
      <QueryState query={allTickets}>
        {(tickets) =>
          showAll ? (
            <TicketList tickets={tickets} emptyMessage="Henüz talep yok." showRequester showPriority />
          ) : (
            <EscalatedList
              tickets={tickets.filter((ticket) => ticket.status === 'ESCALATED')}
              workload={countWorkload(tickets)}
            />
          )
        }
      </QueryState>
    </>
  )
}

function EscalatedList({ tickets, workload }: { tickets: TicketSummary[]; workload: Map<number, number> }) {
  if (tickets.length === 0) {
    return <p className="text-sm text-muted-foreground">Atama bekleyen talep yok.</p>
  }

  return (
    <ul className="space-y-2">
      {tickets.map((ticket) => (
        <li key={ticket.ticket_id}>
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm text-muted-foreground">#{ticket.ticket_id}</span>
                  <Link to={`/tickets/${ticket.ticket_id}`} className="font-medium hover:underline">
                    {ticket.title}
                  </Link>
                  <TicketFlags ticket={ticket} />
                </div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {CATEGORY_LABELS[ticket.category]} · {ticket.requester_name}
                  {ticket.device_asset_tag && ` · ${ticket.device_asset_tag}`} · öncelik{' '}
                  {ticket.priority_score} · son tarih {formatDateTime(ticket.due_at)}
                </div>
              </div>
              <AssignTechnicianForm ticketId={ticket.ticket_id} workload={workload} />
            </CardContent>
          </Card>
        </li>
      ))}
    </ul>
  )
}
