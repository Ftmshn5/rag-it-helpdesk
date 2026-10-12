import { Navigate } from 'react-router'

import { useCurrentUser } from '@/auth/useCurrentUser'
import { PageMessage } from '@/components/layout/PageMessage'
import { homePathFor } from '@/navigation'

/** "/" adresi: kullanıcı seçiliyse rolünün ana sayfasına yönlendirir. */
export function HomePage() {
  const { user, isLoading } = useCurrentUser()

  if (isLoading) return <PageMessage title="Yükleniyor…" />
  if (user) return <Navigate to={homePathFor(user.role)} replace />
  return (
    <PageMessage
      title="Hoş geldiniz"
      description="Sağ üstteki kutudan bir kullanıcı seçin. Seçtiğiniz kullanıcının rolüne (kullanıcı, teknisyen, BT yöneticisi) göre ilgili ekranlar açılır."
    />
  )
}
