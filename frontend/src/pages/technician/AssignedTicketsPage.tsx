// UC-05: teknisyenin iş kuyruğu. Sıra backend'den gelir: önce öncelik puanı
// (Decorator: VIP/Acil), sonra son tarih. Talebe tıklayınca detayda durum
// güncelleme ve not ekleme (UC-06) yapılır.

import { useState } from 'react'

import { useAssignedTickets } from '@/api/queries/tickets'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { TicketList } from '@/components/tickets/TicketList'
import { Button } from '@/components/ui/button'
import type { TicketStatus } from '@/types/api'

const FINISHED: TicketStatus[] = ['RESOLVED', 'CLOSED']

export function AssignedTicketsPage() {
  const [showFinished, setShowFinished] = useState(false)
  const tickets = useAssignedTickets()

  return (
    <>
      <PageHeader
        title="Atanan talepler"
        description="Size atanan talepler; öncelik puanı ve son tarihe göre sıralı."
        actions={
          <Button variant="outline" onClick={() => setShowFinished((value) => !value)}>
            {showFinished ? 'Yalnızca açık talepler' : 'Çözülenleri de göster'}
          </Button>
        }
      />
      <QueryState query={tickets}>
        {(data) => {
          const visible = showFinished ? data : data.filter((t) => !FINISHED.includes(t.status))
          const overdue = visible.filter((t) => t.is_overdue).length
          return (
            <>
              {overdue > 0 && (
                <p className="mb-3 text-sm font-medium text-destructive">
                  {overdue} talebin çözüm süresi geçti.
                </p>
              )}
              <TicketList
                tickets={visible}
                emptyMessage="Şu an size atanmış açık talep yok."
                showRequester
                showPriority
              />
            </>
          )
        }}
      </QueryState>
    </>
  )
}
