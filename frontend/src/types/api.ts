// Backend'in döndürdüğü veri şekilleri (app/application/queries/*.py içindeki DTO'ların karşılığı).
// Alan adları API ile birebir aynıdır (snake_case); dönüştürme yapılmaz.

export type UserRole = 'USER' | 'TECHNICIAN' | 'ADMIN'

export type TicketStatus =
  | 'OPEN'
  | 'AI_ANSWERED'
  | 'ESCALATED'
  | 'ASSIGNED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'CLOSED'

export type TicketCategory = 'HARDWARE' | 'SOFTWARE' | 'NETWORK' | 'ACCOUNT'

export type AiFeedback = 'HELPFUL' | 'NOT_HELPFUL'

/** Destek seviyesi (backend: Chain of Responsibility, app/domain/support_tier.py). */
export type SupportLevel = 'AI' | 'TIER_1' | 'TIER_2'

export type DeviceStatus = 'IN_STOCK' | 'ASSIGNED' | 'IN_REPAIR' | 'RETIRED'

export type MaintenanceType = 'REPAIR' | 'PERIODIC' | 'PART_REPLACEMENT'

export interface User {
  id: number
  full_name: string
  email: string
  role: UserRole
  department: string | null
  is_vip: boolean
  support_level: SupportLevel | null // yalnızca teknisyenlerde dolu
}

export interface TicketSummary {
  ticket_id: number
  title: string
  category: TicketCategory
  status: TicketStatus
  support_level: SupportLevel
  requester_id: number
  requester_name: string
  assignee_id: number | null
  assignee_name: string | null
  device_asset_tag: string | null
  is_vip: boolean
  is_urgent: boolean
  sla_hours: number
  priority_score: number
  due_at: string
  is_overdue: boolean
  ai_confidence: number | null
  ai_feedback: AiFeedback | null
  comment_count: number
  attachment_count: number
  created_at: string
  resolved_at: string | null
}

export interface AiAnswer {
  answer: string
  confidence: number
  sources: string[]
  user_feedback: AiFeedback | null
}

export interface TicketComment {
  id: number
  author_id: number
  author_name: string
  content: string
  created_at: string
}

export interface TicketAttachment {
  id: number
  mime_type: string
  uploaded_at: string
}

/** Decorator zincirinin bir katmanı: o katman uygulandıktan sonraki SLA ve öncelik. */
export interface SlaLayer {
  name: string
  sla_hours: number
  priority_score: number
}

/** Zaman çizelgesi satırı (E3; backend: read.ticket_timeline, olaylardan beslenir). */
export type TimelineEntryKind =
  | 'CREATED'
  | 'AI_ANSWERED'
  | 'AI_FEEDBACK'
  | 'STATUS_CHANGED'
  | 'COMMENT'
  | 'ATTACHMENT'
  | 'URGENCY'

export interface TimelineEntry {
  kind: TimelineEntryKind
  occurred_at: string
  actor_name: string | null // null: sistem (AI asistan)
  details: Record<string, unknown>
}

export interface TicketDetail {
  summary: TicketSummary
  description: string
  ai_answer: AiAnswer | null
  sla_layers: SlaLayer[] // en içten dışa: Temel talep → VIP → Acil
  timeline: TimelineEntry[] // eskiden yeniye
  comments: TicketComment[]
  attachments: TicketAttachment[]
}

export interface DeviceInventory {
  device_id: number
  asset_tag: string
  type: string
  brand: string
  model: string
  serial_number: string
  status: DeviceStatus
  location: string | null
  purchase_date: string | null
  holder_id: number | null
  holder_name: string | null
  holder_department: string | null
  assigned_at: string | null
  has_open_maintenance: boolean
  maintenance_count: number
  last_maintenance_at: string | null
}

export interface InventoryReport {
  total: number
  by_status: Record<DeviceStatus, number>
  by_type: Record<string, number>
  devices: DeviceInventory[]
}

export interface MaintenanceRecord {
  id: number
  type: MaintenanceType
  description: string
  technician_id: number
  technician_name: string
  ticket_id: number | null
  performed_at: string
  completed_at: string | null
  is_open: boolean
}

// Command yanıtı: CQRS gereği yalnızca yeni kaydın id'si
export interface Created {
  id: number
}

// --- Arıza istatistikleri (UC-12; backend: app/application/queries/statistics.py) ---

export interface WeeklyCount {
  week_start: string // YYYY-MM-DD (pazartesi)
  created: number
  resolved: number
}

export interface SlaStatistics {
  met: number
  breached: number
  open_overdue: number
  compliance_rate: number | null
}

export interface AiStatistics {
  processed: number
  answered: number
  low_confidence: number
  failed: number
  helpful: number
  not_helpful: number
  auto_resolution_rate: number | null
  average_confidence: number | null
}

export interface FailureStatistics {
  generated_at: string
  total: number
  open: number
  by_category: Record<TicketCategory, number>
  by_status: Record<TicketStatus, number>
  weekly: WeeklyCount[]
  average_resolution_hours: number | null
  sla: SlaStatistics
  ai: AiStatistics
}

// --- Bildirimler (backend: app/application/queries/notifications.py) ---

export type NotificationChannel = 'IN_APP' | 'EMAIL' | 'SMS'

export interface NotificationItem {
  id: number
  ticket_id: number | null
  channel: NotificationChannel
  message: string
  created_at: string
  is_read: boolean
}

export interface MyNotifications {
  unread_count: number
  items: NotificationItem[] // en yeniler önce
}
