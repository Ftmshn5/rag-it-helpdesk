// Tüm sayfaların ortak çerçevesi: üst menü (rolün sayfaları + kullanıcı seçici) ve içerik alanı.

import { NavLink, Outlet } from 'react-router'

import { useCurrentUser } from '@/auth/useCurrentUser'
import { UserSwitcher } from '@/components/layout/UserSwitcher'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { NAV_ITEMS, ROLE_LABELS } from '@/navigation'

export function AppLayout() {
  const { user } = useCurrentUser()

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="border-b bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
          <span className="font-semibold">BT Destek ve Envanter</span>

          {user && (
            <nav className="flex flex-wrap gap-1">
              {NAV_ITEMS[user.role].map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end
                  className={({ isActive }) =>
                    cn(
                      'rounded-md px-3 py-1.5 text-sm transition-colors hover:bg-muted',
                      isActive ? 'bg-muted font-medium' : 'text-muted-foreground',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          )}

          <div className="ml-auto flex items-center gap-2">
            {user && <Badge variant="secondary">{ROLE_LABELS[user.role]}</Badge>}
            <UserSwitcher />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
