// Talep notları (UC-06) ve yeni not ekleme.

import { useState, type FormEvent } from 'react'

import { useAddComment } from '@/api/commands/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { formatDateTime } from '@/lib/format'
import type { TicketDetail } from '@/types/api'

export function CommentsCard({ ticket, canContribute }: { ticket: TicketDetail; canContribute: boolean }) {
  const addComment = useAddComment()
  const [content, setContent] = useState('')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!content.trim()) return
    await addComment.mutateAsync({ ticketId: ticket.summary.ticket_id, content: content.trim() })
    setContent('')
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Notlar</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {ticket.comments.length === 0 ? (
          <p className="text-sm text-muted-foreground">Henüz not yok.</p>
        ) : (
          <ul className="space-y-3">
            {ticket.comments.map((comment) => (
              <li key={comment.id} className="rounded-md bg-muted/50 p-3">
                <div className="text-sm text-muted-foreground">
                  {comment.author_name} · {formatDateTime(comment.created_at)}
                </div>
                <p className="mt-1 whitespace-pre-wrap">{comment.content}</p>
              </li>
            ))}
          </ul>
        )}

        {canContribute && (
          <form onSubmit={handleSubmit} className="space-y-2">
            <Textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Not ekleyin…"
              rows={3}
              maxLength={5000}
              aria-label="Yeni not"
            />
            <ErrorText error={addComment.error} />
            <Button type="submit" size="sm" disabled={addComment.isPending || !content.trim()}>
              Not ekle
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
