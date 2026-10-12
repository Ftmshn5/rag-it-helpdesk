import { useUsers } from '@/api/queries/users'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// Geçici sayfa (9b): API istemcisi + TanStack Query + shadcn/ui zincirinin
// çalıştığını gösterir. 9c'de rol seçici, yönlendirme ve sayfa iskeleti gelecek.

const ROLE_LABELS = { USER: 'Kullanıcı', TECHNICIAN: 'Teknisyen', ADMIN: 'Yönetici' } as const

export default function App() {
  const users = useUsers()

  return (
    <main className="mx-auto max-w-xl p-8">
      <Card>
        <CardHeader>
          <CardTitle>BT Destek ve Envanter</CardTitle>
        </CardHeader>
        <CardContent>
          {users.isPending && <p className="text-muted-foreground">Kullanıcılar yükleniyor…</p>}
          {users.isError && <p className="text-destructive">{users.error.message}</p>}
          {users.data && (
            <ul className="space-y-2">
              {users.data.map((user) => (
                <li key={user.id} className="flex items-center justify-between">
                  <span>{user.full_name}</span>
                  <span className="flex gap-1">
                    {user.is_vip && <Badge>VIP</Badge>}
                    <Badge variant="secondary">{ROLE_LABELS[user.role]}</Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
