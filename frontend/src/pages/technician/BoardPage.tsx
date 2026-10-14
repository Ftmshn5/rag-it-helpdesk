// E2 / UC-06: teknisyenin Kanban panosu. Kartlar sürüklenerek durum değiştirilir;
// geçişin geçerliliğine backend (State) karar verir.

import { useAssignedTickets } from '@/api/queries/tickets'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { KanbanBoard } from '@/components/tickets/KanbanBoard'

export function BoardPage() {
  const tickets = useAssignedTickets()

  return (
    <>
      <PageHeader
        title="Pano"
        description="Talepleri sürükleyerek durumunu değiştirin. Geçerli olmayan bir taşıma geri alınır."
      />
      <QueryState query={tickets}>{(data) => <KanbanBoard tickets={data} />}</QueryState>
    </>
  )
}
