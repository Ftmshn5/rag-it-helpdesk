// API'den gelen kodların (enum) kullanıcıya gösterilen Türkçe karşılıkları.

import type {
  DeviceStatus,
  MaintenanceType,
  SupportLevel,
  TicketCategory,
  TicketStatus,
} from '@/types/api'

export const TICKET_STATUS_LABELS: Record<TicketStatus, string> = {
  OPEN: 'Açık',
  AI_ANSWERED: 'AI yanıtladı',
  ESCALATED: 'Teknisyen bekleniyor',
  ASSIGNED: 'Teknisyene atandı',
  IN_PROGRESS: 'Üzerinde çalışılıyor',
  RESOLVED: 'Çözüldü (onay bekliyor)',
  CLOSED: 'Kapandı',
}

export const CATEGORY_LABELS: Record<TicketCategory, string> = {
  HARDWARE: 'Donanım',
  SOFTWARE: 'Yazılım',
  NETWORK: 'Ağ / İnternet',
  ACCOUNT: 'Hesap / Şifre',
}

export const DEVICE_STATUS_LABELS: Record<DeviceStatus, string> = {
  IN_STOCK: 'Depoda',
  ASSIGNED: 'Zimmetli',
  IN_REPAIR: 'Bakımda',
  RETIRED: 'Hurdaya ayrıldı',
}

export const MAINTENANCE_TYPE_LABELS: Record<MaintenanceType, string> = {
  REPAIR: 'Onarım',
  PERIODIC: 'Periyodik bakım',
  PART_REPLACEMENT: 'Parça değişimi',
}

export const SUPPORT_LEVEL_LABELS: Record<SupportLevel, string> = {
  AI: 'AI asistan',
  TIER_1: 'Teknisyen',
  TIER_2: 'Kıdemli teknisyen',
}
