// TanStack Query önbellek anahtarları tek yerde.
//
// Okumalar (useQuery) bu anahtarlarla önbelleğe alınır; yazmalar (useMutation)
// başarılı olunca ilgili anahtarları geçersiz kılar (invalidate) ve veri yeniden
// çekilir. Bu, backend'deki CQRS'in ön yüzdeki karşılığıdır: command veri
// döndürmez, güncel hali query tarafından okunur.
//
// Kullanıcıya özel listelerde kullanıcı id'si anahtarın parçasıdır: kullanıcı
// değiştirildiğinde başka birinin önbelleği gösterilmez.

import type { DeviceStatus, TicketStatus } from '@/types/api'

export const queryKeys = {
  users: ['users'] as const,

  tickets: {
    all: ['tickets'] as const, // tüm talep sorgularının ortak öneki
    mine: (userId: number, status?: TicketStatus) => ['tickets', 'mine', userId, status] as const,
    assigned: (userId: number, status?: TicketStatus) =>
      ['tickets', 'assigned', userId, status] as const,
    queue: (status?: TicketStatus) => ['tickets', 'queue', status] as const,
    detail: (ticketId: number) => ['tickets', 'detail', ticketId] as const,
    // İstatistikler talep verisinden hesaplanır: 'tickets' önekinde olduğu için
    // her talep işleminden sonra (invalidate) kendiliğinden yenilenir.
    statistics: (weeks: number) => ['tickets', 'statistics', weeks] as const,
    // 'tickets' önekinin dışında: dosya değişmez, talep yenilenince tekrar indirilmez.
    // Yetki kişiye bağlı olduğu için kullanıcı id'si anahtarda.
    attachment: (ticketId: number, attachmentId: number, userId: number) =>
      ['attachments', ticketId, attachmentId, userId] as const,
  },

  inventory: {
    all: ['inventory'] as const,
    report: (status?: DeviceStatus, type?: string) => ['inventory', 'report', status, type] as const,
    devices: (status?: DeviceStatus) => ['inventory', 'devices', status] as const,
    mine: (userId: number) => ['inventory', 'mine', userId] as const,
    maintenance: (deviceId: number) => ['inventory', 'maintenance', deviceId] as const,
  },
}
