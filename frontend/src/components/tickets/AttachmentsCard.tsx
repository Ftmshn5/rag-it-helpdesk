// Talebin ekran görüntüleri (UC-15): liste ve yeni yükleme.

import { useState, type ChangeEvent } from 'react'

import { useAttachScreenshot } from '@/api/commands/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ACCEPTED_SCREENSHOT_TYPES, MAX_SCREENSHOT_MB, screenshotProblem } from '@/lib/files'
import { formatDateTime } from '@/lib/format'
import type { TicketDetail } from '@/types/api'

export function AttachmentsCard({
  ticket,
  canContribute,
}: {
  ticket: TicketDetail
  canContribute: boolean
}) {
  const attach = useAttachScreenshot()
  const [problem, setProblem] = useState<string | null>(null)

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // aynı dosya tekrar seçilebilsin
    if (!file) return
    const issue = screenshotProblem(file)
    setProblem(issue)
    if (!issue) attach.mutate({ ticketId: ticket.summary.ticket_id, file })
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
          <ul className="space-y-1 text-sm">
            {ticket.attachments.map((attachment, index) => (
              <li key={attachment.id}>
                Görüntü {index + 1} ({attachment.mime_type === 'image/png' ? 'PNG' : 'JPG'}) ·{' '}
                {formatDateTime(attachment.uploaded_at)}
              </li>
            ))}
          </ul>
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
