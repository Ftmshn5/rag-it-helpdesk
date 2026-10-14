// Kısa bildirim (toast) kutuları: sonner. Örn. Kanban'da backend'in reddettiği geçişin mesajı.
// Renkler tema değişkenlerinden (Tasarım sistemi).

import { Toaster as Sonner, type ToasterProps } from 'sonner'

export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      position="bottom-right"
      richColors
      closeButton
      style={
        {
          '--normal-bg': 'var(--popover)',
          '--normal-text': 'var(--popover-foreground)',
          '--normal-border': 'var(--border)',
        } as React.CSSProperties
      }
      {...props}
    />
  )
}
