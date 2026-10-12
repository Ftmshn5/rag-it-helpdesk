// Rol korumalı sayfa grubu.
//
// ÖNEMLİ: Bu yalnızca kullanıcı deneyimi içindir (yanlış menüyü göstermemek).
// Asıl güvenlik backend'dedir: her command/query handler rolü kendisi kontrol
// eder. Tarayıcıdaki kod kullanıcının elindedir ve değiştirilebilir.

import { Outlet } from 'react-router'

import { useCurrentUser } from '@/auth/useCurrentUser'
import { PageMessage } from '@/components/layout/PageMessage'
import type { UserRole } from '@/types/api'

export function RequireRole({ role }: { role: UserRole }) {
  const { user, isLoading } = useCurrentUser()

  if (isLoading) return <PageMessage title="Yükleniyor…" />
  if (!user) {
    return (
      <PageMessage
        title="Kullanıcı seçin"
        description="Devam etmek için sağ üstteki kutudan bir kullanıcı seçin."
      />
    )
  }
  if (user.role !== role) {
    return (
      <PageMessage
        title="Bu sayfa için yetkiniz yok"
        description="Seçili kullanıcının rolü bu sayfayı görüntülemeye uygun değil."
      />
    )
  }
  return <Outlet />
}
