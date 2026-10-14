// E2 — Teknisyen Kanban panosu (State deseninin arayüzdeki karşılığı).
//
// Sütunlar talep durumlarıdır. Kart bırakılınca iyimser olarak hedef sütunda gösterilir ve
// backend'e "bu duruma taşı" denir. Hangi geçişin geçerli olduğu burada YAZILMAZ: kuralın tek
// sahibi backend'deki State sınıflarıdır. Backend reddederse kart animasyonla eski sütununa
// döner ve State'in hata mesajı toast olarak gösterilir.

import {
  DndContext,
  type DragEndEvent,
  DragOverlay,
  type DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { GripVerticalIcon } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { toast } from 'sonner'

import { useMoveTicket } from '@/api/commands/tickets'
import { SlaCountdown } from '@/components/tickets/SlaCountdown'
import { TicketFlags } from '@/components/tickets/TicketBadges'
import { CATEGORY_LABELS, TICKET_STATUS_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { TicketStatus, TicketSummary } from '@/types/api'

const COLUMNS: TicketStatus[] = ['ASSIGNED', 'IN_PROGRESS', 'RESOLVED']

/** Reddedilen taşımanın vurgusu ne kadar görünsün. */
const HIGHLIGHT_MS = 2500

export function KanbanBoard({ tickets }: { tickets: TicketSummary[] }) {
  const move = useMoveTicket()
  // İyimser konumlar: backend yanıt verene kadar kart hedef sütunda görünür
  const [pending, setPending] = useState<Record<number, TicketStatus>>({})
  // Reddedilen taşımalar: sayaç kartın anahtarına girer, her reddedilişte kart yeniden
  // oluşturulur ve giriş animasyonu oynar; vurgu kısa süre sonra kalkar.
  const [returns, setReturns] = useState<Record<number, number>>({})
  const [highlighted, setHighlighted] = useState<number | null>(null)
  const [dragged, setDragged] = useState<TicketSummary | null>(null)
  const sensors = useSensors(
    // Küçük bir hareket eşiği: karta tıklamak (detaya gitmek) sürükleme sayılmaz
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  )

  const columnOf = (ticket: TicketSummary) => pending[ticket.ticket_id] ?? ticket.status

  function handleDragStart({ active }: DragStartEvent) {
    setDragged(tickets.find((ticket) => ticket.ticket_id === active.id) ?? null)
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setDragged(null)
    const ticket = tickets.find((candidate) => candidate.ticket_id === active.id)
    const target = over?.id as TicketStatus | undefined
    if (!ticket || !target || columnOf(ticket) === target) return

    const ticketId = ticket.ticket_id
    setPending((current) => ({ ...current, [ticketId]: target }))
    move.mutate(
      { ticketId, status: target },
      {
        onError: (error) => {
          toast.error('Taşıma yapılamadı', { description: error.message })
          setReturns((current) => ({ ...current, [ticketId]: (current[ticketId] ?? 0) + 1 }))
          setHighlighted(ticketId)
          setTimeout(() => setHighlighted((current) => (current === ticketId ? null : current)), HIGHLIGHT_MS)
        },
        // Başarıda talep sorguları yenilenmiş olur; iyimser konuma artık gerek yok
        onSettled: () =>
          setPending((current) => {
            const { [ticketId]: _done, ...rest } = current
            return rest
          }),
      },
    )
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setDragged(null)}
    >
      <div className="grid gap-4 md:grid-cols-3">
        {COLUMNS.map((status) => {
          const cards = tickets.filter((ticket) => columnOf(ticket) === status)
          return (
            <Column key={status} status={status} count={cards.length}>
              {cards.map((ticket) => (
                <DraggableCard
                  key={`${ticket.ticket_id}-${returns[ticket.ticket_id] ?? 0}`}
                  ticket={ticket}
                  returned={(returns[ticket.ticket_id] ?? 0) > 0}
                  highlighted={highlighted === ticket.ticket_id}
                />
              ))}
            </Column>
          )
        })}
      </div>
      <DragOverlay dropAnimation={null}>{dragged && <CardBody ticket={dragged} lifted />}</DragOverlay>
    </DndContext>
  )
}

function Column({ status, count, children }: { status: TicketStatus; count: number; children: React.ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: status })
  return (
    <section
      ref={setNodeRef}
      aria-label={TICKET_STATUS_LABELS[status]}
      className={cn(
        'flex min-h-64 flex-col gap-2 rounded-xl border bg-card/60 p-3 transition-colors',
        isOver && 'border-primary bg-card ring-2 ring-primary/30',
      )}
    >
      <h2 className="flex items-center justify-between px-1 pb-1 text-sm font-semibold">
        {TICKET_STATUS_LABELS[status]}
        <span className="rounded-full bg-muted px-2 text-xs font-medium text-muted-foreground">{count}</span>
      </h2>
      {children}
      {count === 0 && <p className="px-1 py-6 text-center text-xs text-muted-foreground">Talep yok</p>}
    </section>
  )
}

function DraggableCard({
  ticket,
  returned,
  highlighted,
}: {
  ticket: TicketSummary
  returned: boolean
  highlighted: boolean
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: ticket.ticket_id })
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={cn(
        'cursor-grab touch-none rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing',
        isDragging && 'opacity-40',
        // Yalnızca reddedilip geri dönen kart canlandırılır (ilk yüklemede değil)
        returned && 'animate-in fade-in slide-in-from-right-8 duration-500',
      )}
    >
      <CardBody ticket={ticket} highlight={highlighted} />
    </div>
  )
}

function CardBody({ ticket, lifted, highlight }: { ticket: TicketSummary; lifted?: boolean; highlight?: boolean }) {
  return (
    <article
      className={cn(
        'space-y-2 rounded-lg border bg-card p-3 text-sm shadow-xs',
        lifted && 'rotate-1 shadow-lg',
        highlight && 'border-destructive/60 transition-colors',
      )}
    >
      <div className="flex items-start gap-2">
        <GripVerticalIcon aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <Link to={`/tickets/${ticket.ticket_id}`} className="min-w-0 flex-1 font-medium hover:underline">
          <span className="text-muted-foreground">#{ticket.ticket_id}</span> {ticket.title}
        </Link>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <TicketFlags ticket={ticket} />
        <SlaCountdown ticket={ticket} />
      </div>
      <p className="text-xs text-muted-foreground">
        {CATEGORY_LABELS[ticket.category]} · {ticket.requester_name}
      </p>
    </article>
  )
}
