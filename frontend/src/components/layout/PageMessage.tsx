import type { ReactNode } from 'react'

import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

/** Boş durum / bilgi mesajı (kullanıcı seçilmedi, yetki yok, sayfa bulunamadı…). */
export function PageMessage({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <Card className="mx-auto max-w-lg">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
    </Card>
  )
}
