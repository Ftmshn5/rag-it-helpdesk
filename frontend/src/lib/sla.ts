// SLA durumunun hesabı (yalnızca gösterim). Süre backend'den gelir: due_at = açılış + sla_hours,
// sla_hours da talebin Decorator zincirinden (Temel 72 → VIP en geç 24 → Acil en geç 4 saat).

import type { TicketSummary } from '@/types/api'

export type SlaTone = 'running' | 'warning' | 'overdue' | 'met' | 'missed'

export interface SlaState {
  tone: SlaTone
  label: string
}

/** Kalan süre toplamın bu oranının altına inince uyarı (sarı). */
const WARNING_RATIO = 0.25
const MINUTE = 60_000

/** 95 dk → "1 sa 35 dk", 3000 dk → "2 g 2 sa" */
export function formatDuration(ms: number): string {
  const totalMinutes = Math.max(1, Math.ceil(ms / MINUTE))
  const days = Math.floor(totalMinutes / 1440)
  const hours = Math.floor((totalMinutes % 1440) / 60)
  const minutes = totalMinutes % 60
  if (days > 0) return hours > 0 ? `${days} g ${hours} sa` : `${days} g`
  if (hours > 0) return minutes > 0 ? `${hours} sa ${minutes} dk` : `${hours} sa`
  return `${minutes} dk`
}

export function slaState(ticket: TicketSummary, now: number): SlaState {
  const due = Date.parse(ticket.due_at)

  // Çözülmüş talepte geri sayım biter; süresinde çözülüp çözülmediği gösterilir
  if (ticket.resolved_at) {
    return Date.parse(ticket.resolved_at) <= due
      ? { tone: 'met', label: 'Süresinde çözüldü' }
      : { tone: 'missed', label: 'Geç çözüldü' }
  }

  const remaining = due - now
  if (remaining <= 0) return { tone: 'overdue', label: `${formatDuration(-remaining)} gecikti` }

  const total = due - Date.parse(ticket.created_at)
  const tone = remaining < total * WARNING_RATIO ? 'warning' : 'running'
  return { tone, label: `${formatDuration(remaining)} kaldı` }
}
