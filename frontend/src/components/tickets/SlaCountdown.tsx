// E1 — SLA geri sayımı (Decorator deseninin arayüzdeki karşılığı).
//
// SlaCountdown: her talep kartında çözülme süresine kalan zaman (canlı). Süre, talebin
// Decorator zincirinden gelen sla_hours değerinden hesaplanmıştır (backend: due_at).
// SlaCard: detay sayfasında zincirin hangi katmanlardan oluştuğu ve SLA'yı nasıl değiştirdiği.

import { ChevronRightIcon } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SlaBadge } from '@/components/ui/status-badge'
import { useNow } from '@/hooks/useNow'
import { formatDateTime } from '@/lib/format'
import { slaState } from '@/lib/sla'
import type { SlaLayer, TicketSummary } from '@/types/api'

export function SlaCountdown({ ticket }: { ticket: TicketSummary }) {
  const now = useNow()
  const state = slaState(ticket, now)
  return <SlaBadge tone={state.tone} label={state.label} />
}

export function SlaCard({ ticket, layers }: { ticket: TicketSummary; layers: SlaLayer[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          Çözüm süresi (SLA)
          <SlaCountdown ticket={ticket} />
        </CardTitle>
        <CardDescription>Hedef: {formatDateTime(ticket.due_at)}</CardDescription>
      </CardHeader>
      {layers.length > 0 && (
        <CardContent className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Süre, talebe uygulanan katmanlarla belirlenir (Decorator zinciri):
          </p>
          <ol className="flex flex-wrap items-center gap-1.5 text-sm">
            {layers.map((layer, index) => (
              <li key={layer.name} className="flex items-center gap-1.5">
                {index > 0 && <ChevronRightIcon aria-hidden className="size-4 text-muted-foreground" />}
                <span className="rounded-md border bg-muted px-2 py-1">
                  <span className="font-medium">{layer.name}</span>{' '}
                  <span className="text-muted-foreground">{layer.sla_hours} sa</span>
                </span>
              </li>
            ))}
          </ol>
          {layers.length === 1 && (
            <p className="text-xs text-muted-foreground">VIP veya acil olmayan talep: varsayılan süre.</p>
          )}
        </CardContent>
      )}
    </Card>
  )
}
