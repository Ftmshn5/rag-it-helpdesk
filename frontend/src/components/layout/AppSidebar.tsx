// Yan menü: uygulama adı, seçili rolün sayfaları ve en altta kullanıcı seçici.
// Geniş ekranda sabit durur; dar ekranda AppLayout onu açılır panel olarak gösterir.

import { HeadsetIcon } from 'lucide-react'
import { Link, NavLink } from 'react-router'

import { useCurrentUser } from '@/auth/useCurrentUser'
import { UserSwitcher } from '@/components/layout/UserSwitcher'
import { cn } from '@/lib/utils'
import { NAV_ITEMS, ROLE_LABELS } from '@/navigation'

/** `onNavigate`: dar ekranda bir sayfaya geçince paneli kapatmak için. */
export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useCurrentUser()

  return (
    <div className="flex h-full flex-col gap-6 bg-sidebar p-3 text-sidebar-foreground">
      <Link to="/" onClick={onNavigate} className="flex items-center gap-2.5 px-2 pt-1">
        <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <HeadsetIcon className="size-5" />
        </span>
        <span className="leading-tight">
          <span className="block font-semibold text-white">BT Destek</span>
          <span className="block text-xs text-sidebar-foreground">Talep ve envanter</span>
        </span>
      </Link>

      {user && (
        <nav aria-label="Ana menü" className="space-y-1">
          <p className="px-2 pb-1 text-xs font-medium tracking-wide text-sidebar-foreground/70 uppercase">
            {ROLE_LABELS[user.role]}
          </p>
          {NAV_ITEMS[user.role].map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-white',
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>
      )}

      <div className="mt-auto space-y-2 border-t border-sidebar-border pt-4">
        <p className="px-2 text-xs text-sidebar-foreground/70">Kullanıcı (demo: giriş yerine seçim)</p>
        <UserSwitcher className="w-full border-sidebar-border bg-sidebar-accent/40 text-white" />
      </div>
    </div>
  )
}
