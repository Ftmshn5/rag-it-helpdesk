import { Link } from 'react-router'

import { PageMessage } from '@/components/layout/PageMessage'

export function NotFoundPage() {
  return (
    <PageMessage
      title="Sayfa bulunamadı"
      description={
        <Link to="/" className="underline">
          Ana sayfaya dön
        </Link>
      }
    />
  )
}
