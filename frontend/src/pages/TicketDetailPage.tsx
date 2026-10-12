// Talep detayı: talep sahibi, atanan teknisyen ve yönetici için ortak ekran.
// Kimin görebileceğine backend karar verir (yetkisizse 403 mesajı gösterilir);
// ekran, görüntüleyenin rolüne ve talebin durumuna göre bölümleri açar.

import { useLocation, useParams } from 'react-router'

import { useTicketDetail } from '@/api/queries/tickets'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageMessage } from '@/components/layout/PageMessage'
import { QueryState } from '@/components/layout/QueryState'
import { AiAnswerCard } from '@/components/tickets/AiAnswerCard'
import { AttachmentsCard } from '@/components/tickets/AttachmentsCard'
import { TicketFlags, TicketStatusBadge } from '@/components/tickets/TicketBadges'
import { CommentsCard } from '@/components/tickets/CommentsCard'
import { TicketActions, type Viewer } from '@/components/tickets/TicketActions'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDateTime } from '@/lib/format'
import { CATEGORY_LABELS } from '@/lib/labels'
import type { TicketDetail } from '@/types/api'

export function TicketDetailPage() {
  const ticketId = Number(useParams().ticketId)
  const { user } = useCurrentUser()
  const detail = useTicketDetail(ticketId)
  const uploadError = (useLocation().state as { uploadError?: string } | null)?.uploadError

  if (!user) return <PageMessage title="Kullanıcı seçin" />

  return (
    <QueryState query={detail}>
      {(ticket) => {
        const viewer: Viewer = {
          isRequester: user.id === ticket.summary.requester_id,
          isAssignee: user.id === ticket.summary.assignee_id,
          isAdmin: user.role === 'ADMIN',
        }
        const canContribute =
          ticket.summary.status !== 'CLOSED' &&
          (viewer.isRequester || viewer.isAssignee || viewer.isAdmin)

        return (
          <>
            <PageHeader
              title={`#${ticket.summary.ticket_id} ${ticket.summary.title}`}
              actions={
                <div className="flex flex-wrap gap-2">
                  <TicketFlags ticket={ticket.summary} />
                  <TicketStatusBadge status={ticket.summary.status} />
                </div>
              }
            />
            {uploadError && (
              <p className="mb-4 text-sm text-destructive">
                Talep oluşturuldu ancak ekran görüntüsü yüklenemedi: {uploadError}
              </p>
            )}

            <div className="grid gap-4 lg:grid-cols-3">
              <div className="space-y-4 lg:col-span-2">
                <TicketInfoCard ticket={ticket} />
                <AiAnswerCard ticket={ticket} isRequester={viewer.isRequester} />
                <CommentsCard ticket={ticket} canContribute={canContribute} />
              </div>
              <div className="space-y-4">
                <TicketActions ticket={ticket.summary} viewer={viewer} />
                <AttachmentsCard ticket={ticket} canContribute={canContribute} />
              </div>
            </div>
          </>
        )
      }}
    </QueryState>
  )
}

function TicketInfoCard({ ticket }: { ticket: TicketDetail }) {
  const { summary } = ticket
  const rows: [string, string][] = [
    ['Kategori', CATEGORY_LABELS[summary.category]],
    ['Talep sahibi', summary.requester_name],
    ['Teknisyen', summary.assignee_name ?? '—'],
    ['İlgili cihaz', summary.device_asset_tag ?? '—'],
    ['Açılış', formatDateTime(summary.created_at)],
    ['Çözüm hedefi', `${formatDateTime(summary.due_at)} (${summary.sla_hours} saat)`],
    ['Çözülme', formatDateTime(summary.resolved_at)],
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle>Talep</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="whitespace-pre-wrap">{ticket.description}</p>
        <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
          {rows.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  )
}
