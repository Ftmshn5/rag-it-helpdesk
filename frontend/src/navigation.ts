// Rollere göre menü ve ana sayfalar tek yerde (CLAUDE.md: sayfalar role göre ayrılır).

import type { UserRole } from '@/types/api'

export interface NavItem {
  to: string
  label: string
}

export const ROLE_LABELS: Record<UserRole, string> = {
  USER: 'Kullanıcı',
  TECHNICIAN: 'Teknisyen',
  ADMIN: 'BT Yöneticisi',
}

export const NAV_ITEMS: Record<UserRole, NavItem[]> = {
  USER: [
    { to: '/user/tickets', label: 'Taleplerim' }, // UC-03
    { to: '/user/tickets/new', label: 'Yeni talep' }, // UC-01
    { to: '/user/devices', label: 'Cihazlarım' }, // UC-04
  ],
  TECHNICIAN: [
    { to: '/technician/queue', label: 'Atanan talepler' }, // UC-05
    { to: '/technician/maintenance', label: 'Bakım' }, // UC-16, UC-17
  ],
  ADMIN: [
    { to: '/admin/queue', label: 'Atama bekleyenler' }, // UC-10
    { to: '/admin/devices', label: 'Cihazlar ve zimmet' }, // UC-08, UC-09
    { to: '/admin/inventory', label: 'Envanter raporu' }, // UC-11
    { to: '/admin/statistics', label: 'İstatistikler' }, // UC-12
  ],
}

/** Kullanıcı seçildiğinde açılacak sayfa: rolünün ilk menü öğesi. */
export function homePathFor(role: UserRole): string {
  return NAV_ITEMS[role][0].to
}
