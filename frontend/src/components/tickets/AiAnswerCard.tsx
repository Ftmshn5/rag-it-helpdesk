// AI asistanın önerisi ve kullanıcının değerlendirmesi (UC-02).

import { useEvaluateAiAnswer } from '@/api/commands/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatPercent } from '@/lib/format'
import type { TicketDetail } from '@/types/api'

export function AiAnswerCard({ ticket, isRequester }: { ticket: TicketDetail; isRequester: boolean }) {
  const evaluate = useEvaluateAiAnswer()
  const { summary, ai_answer: answer } = ticket

  // İş kuralı 4: güven düşükse yanıt talep sahibine gösterilmez (backend gizler)
  if (!answer) {
    if (summary.ai_confidence === null) return null
    return (
      <Card>
        <CardHeader>
          <CardTitle>AI asistan</CardTitle>
          <CardDescription>
            Bu sorun için bilgi bankasında yeterince güvenilir bir çözüm bulunamadı; talebiniz
            doğrudan teknik ekibe iletildi.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }

  const canEvaluate = isRequester && summary.status === 'AI_ANSWERED'

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI asistanın önerisi</CardTitle>
        <CardDescription>Güven: {formatPercent(answer.confidence)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="whitespace-pre-wrap">{answer.answer}</p>

        {answer.sources.length > 0 && (
          <div className="text-sm text-muted-foreground">
            Kaynaklar:{' '}
            {answer.sources.map((source) => (
              <code key={source} className="mr-2 rounded bg-muted px-1">
                {source}
              </code>
            ))}
          </div>
        )}

        {canEvaluate && (
          <div className="space-y-2 rounded-md border p-3">
            <p className="text-sm font-medium">Bu öneri sorununuzu çözdü mü?</p>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={evaluate.isPending}
                onClick={() => evaluate.mutate({ ticketId: summary.ticket_id, isHelpful: true })}
              >
                Evet, sorunum çözüldü
              </Button>
              <Button
                variant="outline"
                disabled={evaluate.isPending}
                onClick={() => evaluate.mutate({ ticketId: summary.ticket_id, isHelpful: false })}
              >
                Hayır, teknisyene iletilsin
              </Button>
            </div>
            <ErrorText error={evaluate.error} />
          </div>
        )}

        {answer.user_feedback && (
          <p className="text-sm text-muted-foreground">
            Değerlendirme:{' '}
            {answer.user_feedback === 'HELPFUL' ? 'Sorunu çözdü' : 'Sorunu çözmedi'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
