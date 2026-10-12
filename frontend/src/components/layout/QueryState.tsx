// Okuma (useQuery) sonucunun ortak yükleniyor / hata görünümü.

import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'

export function QueryState<T>({
  query,
  children,
}: {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
}) {
  if (query.isPending) return <p className="text-sm text-muted-foreground">Yükleniyor…</p>
  if (query.isError) return <ErrorText error={query.error} />
  return <>{children(query.data)}</>
}

/** Backend'in Türkçe hata mesajını gösterir (ApiError.message). */
export function ErrorText({ error }: { error: Error | null }) {
  if (!error) return null
  return <p className="text-sm text-destructive">{error.message}</p>
}
