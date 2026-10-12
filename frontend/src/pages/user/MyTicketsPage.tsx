// UC-03: kullanıcı kendi taleplerini listeler ve takip eder.

import { useState } from 'react'
import { Link } from 'react-router'

import { useMyTickets } from '@/api/queries/tickets'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { TicketList } from '@/components/tickets/TicketList'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { TICKET_STATUS_LABELS } from '@/lib/labels'
import type { TicketStatus } from '@/types/api'

const ALL = 'ALL'

export function MyTicketsPage() {
  const [status, setStatus] = useState<TicketStatus | typeof ALL>(ALL)
  const tickets = useMyTickets(status === ALL ? undefined : status)

  return (
    <>
      <PageHeader
        title="Taleplerim"
        description="Açtığınız arıza kayıtları ve durumları."
        actions={
          <div className="flex gap-2">
            <Select value={status} onValueChange={(value) => setStatus(value as TicketStatus)}>
              <SelectTrigger className="w-56" aria-label="Duruma göre filtrele">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Tüm durumlar</SelectItem>
                {Object.entries(TICKET_STATUS_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button asChild>
              <Link to="/user/tickets/new">Yeni talep</Link>
            </Button>
          </div>
        }
      />
      <QueryState query={tickets}>
        {(data) => (
          <TicketList
            tickets={data}
            emptyMessage={
              status === ALL ? 'Henüz bir talebiniz yok.' : 'Bu durumda talebiniz yok.'
            }
          />
        )}
      </QueryState>
    </>
  )
}
