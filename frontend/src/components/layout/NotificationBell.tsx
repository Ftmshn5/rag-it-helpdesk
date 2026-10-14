// Üst menüdeki zil: okunmamış bildirim sayısı ve son bildirimler.
//
// Bildirimleri backend üretir (talep olaylarını dinleyen Observer'lar); burada
// yalnızca okunur ve okundu işaretlenir. E-posta / SMS kanalları benzetimdir:
// gerçekte gönderilmez, burada kanal etiketiyle gösterilir.

import { BellIcon } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import { useMarkNotificationsRead } from '@/api/commands/notifications'
import { useMyNotifications } from '@/api/queries/notifications'
import { ErrorText } from '@/components/layout/QueryState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { formatDateTime } from '@/lib/format'
import { NOTIFICATION_CHANNEL_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { NotificationItem } from '@/types/api'

const MAX_BADGE_COUNT = 9

export function NotificationBell() {
  const notifications = useMyNotifications()
  const markRead = useMarkNotificationsRead()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  const unread = notifications.data?.unread_count ?? 0
  const items = notifications.data?.items ?? []

  function openNotification(notification: NotificationItem) {
    if (!notification.is_read) markRead.mutate([notification.id])
    if (notification.ticket_id !== null) {
      setOpen(false)
      navigate(`/tickets/${notification.ticket_id}`)
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={unread ? `Bildirimler, ${unread} okunmamış` : 'Bildirimler'}
        >
          <BellIcon />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] leading-4 font-medium text-white">
              {unread > MAX_BADGE_COUNT ? `${MAX_BADGE_COUNT}+` : unread}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <span className="text-sm font-medium">Bildirimler</span>
          <Button
            variant="ghost"
            size="sm"
            disabled={unread === 0 || markRead.isPending}
            onClick={() => markRead.mutate([])}
          >
            Tümünü okundu işaretle
          </Button>
        </div>

        {items.length === 0 ? (
          <p className="px-3 py-6 text-center text-sm text-muted-foreground">
            {notifications.isPending ? 'Yükleniyor…' : 'Bildirim yok.'}
          </p>
        ) : (
          <ul className="max-h-96 divide-y overflow-y-auto">
            {items.map((notification) => (
              <li key={notification.id}>
                <button
                  type="button"
                  onClick={() => openNotification(notification)}
                  className={cn(
                    'flex w-full gap-2 px-3 py-2 text-left text-sm hover:bg-muted',
                    !notification.is_read && 'bg-muted/50',
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      'mt-1.5 size-2 shrink-0 rounded-full',
                      notification.is_read ? 'bg-transparent' : 'bg-primary',
                    )}
                  />
                  <span className="min-w-0 flex-1 space-y-1">
                    <span className={cn('block', !notification.is_read && 'font-medium')}>
                      {notification.message}
                    </span>
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                      {formatDateTime(notification.created_at)}
                      {notification.channel !== 'IN_APP' && (
                        <Badge variant="outline">{NOTIFICATION_CHANNEL_LABELS[notification.channel]}</Badge>
                      )}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {(notifications.error ?? markRead.error) && (
          <div className="border-t px-3 py-2">
            <ErrorText error={notifications.error ?? markRead.error} />
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
