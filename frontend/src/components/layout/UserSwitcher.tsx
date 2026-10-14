// Yan menüdeki kullanıcı seçme kutusu. Kimlik doğrulama kapsam dışı olduğu için
// "giriş" yerine kullanıcı seçilir; seçilen id her istekte X-User-Id olarak gider.

import { useNavigate } from 'react-router'

import { useUsers } from '@/api/queries/users'
import { useCurrentUserId } from '@/auth/currentUser'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { homePathFor, ROLE_LABELS } from '@/navigation'
import type { UserRole } from '@/types/api'

const ROLE_ORDER: UserRole[] = ['USER', 'TECHNICIAN', 'ADMIN']

export function UserSwitcher({ className = 'w-64' }: { className?: string }) {
  const users = useUsers()
  const { userId, setUserId } = useCurrentUserId()
  const navigate = useNavigate()

  if (users.isError) {
    return <span className="text-sm text-destructive">{users.error.message}</span>
  }

  function handleChange(value: string) {
    const user = users.data?.find((candidate) => candidate.id === Number(value))
    if (!user) return
    setUserId(user.id)
    navigate(homePathFor(user.role)) // yeni rolün ana sayfasına geç
  }

  return (
    <Select value={userId?.toString() ?? ''} onValueChange={handleChange} disabled={users.isPending}>
      <SelectTrigger className={className} aria-label="Kullanıcı seç">
        <SelectValue placeholder={users.isPending ? 'Yükleniyor…' : 'Kullanıcı seçin'} />
      </SelectTrigger>
      <SelectContent>
        {ROLE_ORDER.map((role) => (
          <SelectGroup key={role}>
            <SelectLabel>{ROLE_LABELS[role]}</SelectLabel>
            {users.data
              ?.filter((user) => user.role === role)
              .map((user) => (
                <SelectItem key={user.id} value={user.id.toString()}>
                  {user.full_name}
                  {user.is_vip && ' (VIP)'}
                </SelectItem>
              ))}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  )
}
