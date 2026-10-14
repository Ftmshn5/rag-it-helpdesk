// E3 — Talep zaman çizelgesi (Observer deseninin arayüzdeki karşılığı).
//
// Satırlar backend'de event bus'a yayınlanan olaylardan oluşur (read.ticket_timeline).
// Backend olguyu saklar (tür, kişi, ayrıntılar); cümleyi ve ikonu burada üretiriz.

import {
  ArrowUpCircleIcon,
  CircleCheckIcon,
  CirclePlusIcon,
  LockIcon,
  type LucideIcon,
  MessageSquareIcon,
  PaperclipIcon,
  PlayIcon,
  RefreshCwIcon,
  SparklesIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  TriangleAlertIcon,
  UserCheckIcon,
} from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime, formatPercent } from '@/lib/format'
import { TICKET_STATUS_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { TicketStatus, TimelineEntry } from '@/types/api'

interface Described {
  icon: LucideIcon
  title: string
  body?: string
  ai?: boolean // AI asistanın adımı: AI rengiyle ayırt edilir (Tasarım sistemi)
}

const REWORK: TicketStatus[] = ['ASSIGNED', 'IN_PROGRESS']

function describeStatusChange(details: TimelineEntry['details']): Described {
  const oldStatus = details.old_status as TicketStatus
  const newStatus = details.new_status as TicketStatus
  const assignee = details.assignee_name as string | null

  switch (newStatus) {
    case 'ESCALATED':
      if (oldStatus === 'RESOLVED') return { icon: RefreshCwIcon, title: 'Talep yeniden açıldı' }
      if (REWORK.includes(oldStatus))
        return { icon: ArrowUpCircleIcon, title: 'Üst seviyeye eskale edildi', body: 'Kıdemli teknisyene atanacak.' }
      return { icon: ArrowUpCircleIcon, title: 'Teknik ekibe iletildi' }
    case 'ASSIGNED':
      return {
        icon: UserCheckIcon,
        title: REWORK.includes(oldStatus) ? 'Başka teknisyene devredildi' : 'Teknisyene atandı',
        body: assignee ?? undefined,
      }
    case 'IN_PROGRESS':
      return { icon: PlayIcon, title: 'Çalışmaya başlandı' }
    case 'RESOLVED':
      return { icon: CircleCheckIcon, title: 'Çözüldü olarak işaretlendi' }
    case 'CLOSED':
      return { icon: LockIcon, title: 'Talep kapatıldı' }
    default:
      return {
        icon: RefreshCwIcon,
        title: `Durum: ${TICKET_STATUS_LABELS[oldStatus]} → ${TICKET_STATUS_LABELS[newStatus]}`,
      }
  }
}

function describe(entry: TimelineEntry): Described {
  const { details } = entry
  switch (entry.kind) {
    case 'CREATED':
      return {
        icon: CirclePlusIcon,
        title: 'Talep oluşturuldu',
        body: details.sla_hours ? `Çözüm süresi: ${details.sla_hours} saat` : undefined,
      }
    case 'AI_ANSWERED': {
      if (details.escalated)
        return { icon: SparklesIcon, title: 'AI güvenilir bir çözüm bulamadı', body: 'Talep teknik ekibe iletildi.', ai: true }
      const confidence = typeof details.confidence === 'number' ? ` (güven ${formatPercent(details.confidence)})` : ''
      return { icon: SparklesIcon, title: `AI asistan çözüm önerdi${confidence}`, ai: true }
    }
    case 'AI_FEEDBACK':
      return details.is_helpful
        ? { icon: ThumbsUpIcon, title: 'AI önerisi sorunu çözdü' }
        : { icon: ThumbsDownIcon, title: 'AI önerisi sorunu çözmedi' }
    case 'STATUS_CHANGED':
      return describeStatusChange(details)
    case 'COMMENT':
      return { icon: MessageSquareIcon, title: 'Not eklendi', body: details.excerpt as string }
    case 'ATTACHMENT':
      return { icon: PaperclipIcon, title: 'Ekran görüntüsü eklendi' }
    case 'URGENCY':
      return details.is_urgent
        ? { icon: TriangleAlertIcon, title: 'Acil olarak işaretlendi', body: `Çözüm süresi: ${details.sla_hours} saat` }
        : { icon: TriangleAlertIcon, title: 'Acil işareti kaldırıldı', body: `Çözüm süresi: ${details.sla_hours} saat` }
  }
}

export function TimelineCard({ entries }: { entries: TimelineEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Zaman çizelgesi</CardTitle>
        <CardDescription>Talebin geçmişi; her adım sistemde gerçekleşen bir olaydır.</CardDescription>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">Henüz kayıt yok.</p>
        ) : (
          <ol className="relative space-y-4 border-l border-border pl-6">
            {entries.map((entry, index) => {
              const { icon: Icon, title, body, ai } = describe(entry)
              return (
                <li key={`${entry.occurred_at}-${index}`} className="relative">
                  <span
                    aria-hidden
                    className={cn(
                      'absolute top-0 -left-[37px] flex size-6 items-center justify-center rounded-full border bg-card',
                      ai && 'border-ai-border bg-ai text-ai-foreground',
                    )}
                  >
                    <Icon className="size-3.5" />
                  </span>
                  <p className={cn('text-sm font-medium', ai && 'text-ai-foreground')}>{title}</p>
                  {body && <p className="mt-0.5 text-sm whitespace-pre-wrap text-muted-foreground">{body}</p>}
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {formatDateTime(entry.occurred_at)} · {entry.actor_name ?? 'AI asistan'}
                  </p>
                </li>
              )
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}
