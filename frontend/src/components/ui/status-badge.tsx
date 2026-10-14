// Uygulamadaki tüm rozetler: talep durumları ve talep işaretleri (VIP, Acil, Kıdemli destek), SLA geri sayımı
// tek bir StatusBadge bileşeninden; cihaz durumları aynı rozet kalıbıyla DeviceStatusBadge'den.
// Renkler CLAUDE.md "Tasarım sistemi" tablosundadır. Renk tek başına anlam taşımaz: her rozetin
// metni vardır, işaret rozetlerinde ayrıca ikon bulunur.

import {
  CircleCheckIcon,
  ClockAlertIcon,
  CrownIcon,
  type LucideIcon,
  ShieldCheckIcon,
  TimerIcon,
  TriangleAlertIcon,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { DEVICE_STATUS_LABELS, TICKET_STATUS_LABELS } from '@/lib/labels'
import type { SlaTone } from '@/lib/sla'
import { cn } from '@/lib/utils'
import type { DeviceStatus, TicketStatus } from '@/types/api'

interface BadgeStyle {
  label: string
  className: string // zemin / yazı rengi
  icon?: LucideIcon
}

/** Rozetin ortak görünümü (StatusBadge ve DeviceStatusBadge kullanır). */
function BadgePill({ style }: { style: BadgeStyle }): ReactNode {
  const Icon = style.icon
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        style.className,
      )}
    >
      {Icon && <Icon aria-hidden className="size-3" />}
      {style.label}
    </span>
  )
}

// --- Talep: durumlar ve işaretler ---

export type TicketFlag = 'VIP' | 'URGENT' | 'SENIOR'
export type StatusBadgeKind = TicketStatus | TicketFlag

const TICKET_BADGES: Record<StatusBadgeKind, BadgeStyle> = {
  OPEN: { label: TICKET_STATUS_LABELS.OPEN, className: 'bg-[#F1F5F9] text-[#334155]' },
  AI_ANSWERED: { label: TICKET_STATUS_LABELS.AI_ANSWERED, className: 'bg-[#EDE9FE] text-[#5B21B6]' },
  ESCALATED: { label: TICKET_STATUS_LABELS.ESCALATED, className: 'bg-[#FEF3C7] text-[#92400E]' },
  ASSIGNED: { label: TICKET_STATUS_LABELS.ASSIGNED, className: 'bg-[#E0E7FF] text-[#3730A3]' },
  IN_PROGRESS: { label: TICKET_STATUS_LABELS.IN_PROGRESS, className: 'bg-[#E0F2FE] text-[#075985]' },
  RESOLVED: { label: TICKET_STATUS_LABELS.RESOLVED, className: 'bg-[#DCFCE7] text-[#166534]' },
  CLOSED: { label: TICKET_STATUS_LABELS.CLOSED, className: 'bg-[#F1F5F9] text-[#64748B]' },
  VIP: { label: 'VIP', className: 'bg-[#FEF9C3] text-[#854D0E]', icon: CrownIcon },
  URGENT: { label: 'Acil', className: 'bg-[#FEE2E2] text-[#991B1B]', icon: TriangleAlertIcon },
  SENIOR: { label: 'Kıdemli destek', className: 'bg-[#E0E7FF] text-[#3730A3]', icon: ShieldCheckIcon },
}

export function StatusBadge({ kind }: { kind: StatusBadgeKind }) {
  return <BadgePill style={TICKET_BADGES[kind]} />
}

// --- Cihaz durumları ---

const DEVICE_BADGES: Record<DeviceStatus, BadgeStyle> = {
  IN_STOCK: { label: DEVICE_STATUS_LABELS.IN_STOCK, className: 'bg-[#DCFCE7] text-[#166534]' }, // yeşil
  ASSIGNED: { label: DEVICE_STATUS_LABELS.ASSIGNED, className: 'bg-[#E0E7FF] text-[#3730A3]' }, // indigo
  IN_REPAIR: { label: DEVICE_STATUS_LABELS.IN_REPAIR, className: 'bg-[#FFEDD5] text-[#9A3412]' }, // turuncu
  RETIRED: { label: DEVICE_STATUS_LABELS.RETIRED, className: 'bg-[#F1F5F9] text-[#64748B]' }, // gri
}

export function DeviceStatusBadge({ status }: { status: DeviceStatus }) {
  return <BadgePill style={DEVICE_BADGES[status]} />
}

// --- SLA geri sayımı (E1) ---

// Kalan süre normal: nötr · %25'in altı: sarı · geçti: kırmızı · çözüldü: yeşil / kırmızı
const SLA_BADGES: Record<SlaTone, Omit<BadgeStyle, 'label'>> = {
  running: { className: 'bg-[#F1F5F9] text-[#334155]', icon: TimerIcon },
  warning: { className: 'bg-[#FEF3C7] text-[#92400E]', icon: TimerIcon },
  overdue: { className: 'bg-[#FEE2E2] text-[#991B1B]', icon: ClockAlertIcon },
  met: { className: 'bg-[#DCFCE7] text-[#166534]', icon: CircleCheckIcon },
  missed: { className: 'bg-[#FEE2E2] text-[#991B1B]', icon: ClockAlertIcon },
}

export function SlaBadge({ tone, label }: { tone: SlaTone; label: string }) {
  return <BadgePill style={{ ...SLA_BADGES[tone], label }} />
}
