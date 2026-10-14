// Tüm sayfaların ortak çerçevesi: solda yan menü, üstte ince bir çubuk (bildirimler ve
// seçili kullanıcı), ortada sayfa içeriği. Dar ekranda yan menü bir düğmeyle açılır.

import { MenuIcon } from 'lucide-react'
import { useState } from 'react'
import { Outlet } from 'react-router'

import { useCurrentUser } from '@/auth/useCurrentUser'
import { AppSidebar } from '@/components/layout/AppSidebar'
import { NotificationBell } from '@/components/layout/NotificationBell'
import { Button } from '@/components/ui/button'
import { Toaster } from '@/components/ui/sonner'
import { ROLE_LABELS } from '@/navigation'
import type { User } from '@/types/api'

export function AppLayout() {
  const { user } = useCurrentUser()
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)

  return (
    <div className="flex min-h-svh bg-background print:bg-white">
      {/* Dış kutu sayfa boyunca uzanır (koyu zemin kesilmez); iç kutu kaydırırken sabit kalır */}
      <aside className="hidden w-64 shrink-0 border-r border-sidebar-border bg-sidebar lg:block print:hidden">
        <div className="sticky top-0 h-svh">
          <AppSidebar />
        </div>
      </aside>

      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div aria-hidden className="absolute inset-0 bg-black/30" onClick={closeMenu} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r shadow-xl">
            <AppSidebar onNavigate={closeMenu} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b bg-card/95 px-4 backdrop-blur lg:px-8 print:hidden">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Menüyü aç"
            onClick={() => setMenuOpen(true)}
          >
            <MenuIcon />
          </Button>
          <div className="ml-auto flex items-center gap-3">
            {user && <NotificationBell />}
            {user && <CurrentUserChip user={user} />}
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 lg:px-8 lg:py-8 print:max-w-none print:p-0">
          <Outlet />
        </main>
        <Toaster />
      </div>
    </div>
  )
}

function CurrentUserChip({ user }: { user: User }) {
  const initials = user.full_name
    .split(' ')
    .filter((part) => !part.endsWith('.')) // "Prof. Dr." gibi unvanları atla
    .map((part) => part[0])
    .slice(0, 2)
    .join('')

  return (
    <div className="flex items-center gap-2">
      <span className="flex size-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
        {initials}
      </span>
      <span className="hidden leading-tight sm:block">
        <span className="block text-sm font-medium">{user.full_name}</span>
        <span className="block text-xs text-muted-foreground">
          {ROLE_LABELS[user.role]}
          {user.is_vip && ' · VIP'}
        </span>
      </span>
    </div>
  )
}
