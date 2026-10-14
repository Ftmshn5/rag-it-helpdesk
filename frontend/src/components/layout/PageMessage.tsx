import { InboxIcon, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

/**
 * Boş durum / bilgi mesajı (liste boş, kullanıcı seçilmedi, yetki yok, sayfa bulunamadı…).
 * `w-full`: ızgara hücresi içinde içeriği kadar daralmaz, en fazla max-w-lg genişlikte ortalanır.
 */
export function PageMessage({
  title,
  description,
  icon: Icon = InboxIcon,
  action,
}: {
  title: string
  description?: ReactNode
  icon?: LucideIcon
  action?: ReactNode
}) {
  return (
    <div className="mx-auto flex w-full max-w-lg flex-col items-center rounded-xl border border-dashed bg-card px-6 py-10 text-center">
      <span className="mb-3 flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Icon className="size-5" />
      </span>
      <h2 className="font-medium">{title}</h2>
      {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
