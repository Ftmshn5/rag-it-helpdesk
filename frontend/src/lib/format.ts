// Tarih ve sayı biçimlendirme (Türkçe yerel ayarıyla).

const dateTime = new Intl.DateTimeFormat('tr-TR', { dateStyle: 'medium', timeStyle: 'short' })
const dateOnly = new Intl.DateTimeFormat('tr-TR', { dateStyle: 'medium' })

export function formatDateTime(value: string | null): string {
  return value ? dateTime.format(new Date(value)) : '—'
}

export function formatDate(value: string | null): string {
  return value ? dateOnly.format(new Date(value)) : '—'
}

/** 0.85 → "%85" */
export function formatPercent(value: number): string {
  return `%${Math.round(value * 100)}`
}
