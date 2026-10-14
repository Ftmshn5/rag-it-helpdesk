// Rollere göre menü ve ana sayfalar tek yerde (CLAUDE.md: sayfalar role göre ayrılır).

import {
  BoxesIcon,
  ChartColumnIcon,
  CirclePlusIcon,
  ClipboardListIcon,
  InboxIcon,
  KanbanIcon,
  LaptopIcon,
  ListChecksIcon,
  type LucideIcon,
  MonitorIcon,
  WrenchIcon,
} from 'lucide-react'

import type { UserRole } from '@/types/api'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const ROLE_LABELS: Record<UserRole, string> = {
  USER: 'Kullanıcı',
  TECHNICIAN: 'Teknisyen',
  ADMIN: 'BT Yöneticisi',
}

export const NAV_ITEMS: Record<UserRole, NavItem[]> = {
  USER: [
    { to: '/user/tickets', label: 'Taleplerim', icon: InboxIcon }, // UC-03
    { to: '/user/tickets/new', label: 'Yeni talep', icon: CirclePlusIcon }, // UC-01
    { to: '/user/devices', label: 'Cihazlarım', icon: LaptopIcon }, // UC-04
  ],
  TECHNICIAN: [
    { to: '/technician/queue', label: 'Atanan talepler', icon: ListChecksIcon }, // UC-05
    { to: '/technician/board', label: 'Pano', icon: KanbanIcon }, // UC-06, E2 (State)
    { to: '/technician/maintenance', label: 'Bakım', icon: WrenchIcon }, // UC-16, UC-17
  ],
  ADMIN: [
    { to: '/admin/queue', label: 'Atama bekleyenler', icon: ClipboardListIcon }, // UC-10
    { to: '/admin/devices', label: 'Cihazlar ve zimmet', icon: MonitorIcon }, // UC-08, UC-09
    { to: '/admin/inventory', label: 'Envanter raporu', icon: BoxesIcon }, // UC-11
    { to: '/admin/statistics', label: 'İstatistikler', icon: ChartColumnIcon }, // UC-12
  ],
}

/** Kullanıcı seçildiğinde açılacak sayfa: rolünün ilk menü öğesi. */
export function homePathFor(role: UserRole): string {
  return NAV_ITEMS[role][0].to
}
