// Talebin ekran görüntüleri (UC-15): küçük resimler ve yeni yükleme.

import { useState, type ChangeEvent } from 'react'

import { useAttachScreenshot } from '@/api/commands/tickets'
import { useAttachmentImage } from '@/api/queries/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ACCEPTED_SCREENSHOT_TYPES, MAX_SCREENSHOT_MB, screenshotProblem } from '@/lib/files'
import { formatDateTime } from '@/lib/format'
import type { TicketAttachment, TicketDetail } from '@/types/api'

export function AttachmentsCard({
  ticket,
  canContribute,
}: {
  ticket: TicketDetail
  canContribute: boolean
}) {
  const attach = useAttachScreenshot()
  const [problem, setProblem] = useState<string | null>(null)
  const ticketId = ticket.summary.ticket_id

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // aynı dosya tekrar seçilebilsin
    if (!file) return
    const issue = screenshotProblem(file)
    setProblem(issue)
    if (!issue) attach.mutate({ ticketId, file })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ekran görüntüleri</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {ticket.attachments.length === 0 ? (
          <p className="text-sm text-muted-foreground">Ekran görüntüsü eklenmemiş.</p>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {ticket.attachments.map((attachment) => (
              <AttachmentThumbnail key={attachment.id} ticketId={ticketId} attachment={attachment} />
            ))}
          </div>
        )}

        {canContribute && (
          <div className="space-y-1">
            <Input
              type="file"
              accept={ACCEPTED_SCREENSHOT_TYPES}
              onChange={handleFile}
              disabled={attach.isPending}
              aria-label="Ekran görüntüsü yükle"
            />
            <p className="text-xs text-muted-foreground">
              PNG veya JPG, en fazla {MAX_SCREENSHOT_MB} MB.
            </p>
            {problem && <p className="text-sm text-destructive">{problem}</p>}
            <ErrorText error={attach.error} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AttachmentThumbnail({ ticketId, attachment }: { ticketId: number; attachment: TicketAttachment }) {
  const image = useAttachmentImage(ticketId, attachment.id)
  const uploaded = formatDateTime(attachment.uploaded_at)

  if (image.error) return <p className="text-xs text-destructive">{image.error.message}</p>
  if (!image.url) return <div className="aspect-video animate-pulse rounded-md bg-muted" />
  return (
    <a href={image.url} target="_blank" rel="noreferrer" title={`Yüklenme: ${uploaded} — büyütmek için tıklayın`}>
      <img
        src={image.url}
        alt={`Ekran görüntüsü (${uploaded})`}
        className="aspect-video w-full rounded-md border object-cover"
      />
    </a>
  )
}
