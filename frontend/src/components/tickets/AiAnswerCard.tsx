// AI asistanın önerisi ve kullanıcının değerlendirmesi (UC-02).
//
// AI içeriği yalnızca renkle değil, kutunun başındaki ikon ve "AI önerisi" etiketiyle de
// ayırt edilir (Tasarım sistemi: ai renkleri, CLAUDE.md).

import { Loader2Icon, SparklesIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { useEvaluateAiAnswer } from '@/api/commands/tickets'
import { ErrorText } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { formatPercent } from '@/lib/format'
import type { TicketDetail } from '@/types/api'

/** AI içeriğinin kutusu: lavanta zemin, solda mor çizgi, başta ikon + etiket. */
function AiBox({ busy = false, aside, children }: { busy?: boolean; aside?: ReactNode; children: ReactNode }) {
  const Icon = busy ? Loader2Icon : SparklesIcon
  return (
    <section
      aria-label="AI önerisi"
      className="rounded-xl border-l-[3px] border-ai-border bg-ai p-4 text-ai-foreground shadow-xs"
    >
      <div className="mb-3 flex items-center gap-2">
        <Icon aria-hidden className={busy ? 'size-4 animate-spin' : 'size-4'} />
        <span className="text-sm font-semibold">AI önerisi</span>
        {aside && <span className="ml-auto text-xs">{aside}</span>}
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

export function AiAnswerCard({ ticket, isRequester }: { ticket: TicketDetail; isRequester: boolean }) {
  const evaluate = useEvaluateAiAnswer()
  const { summary, ai_answer: answer } = ticket

  // AI yanıtı arka planda üretiliyor; sayfa yanıt gelene kadar kendini yeniler
  if (summary.status === 'OPEN') {
    return (
      <AiBox busy>
        <p className="text-sm">
          AI asistan bilgi bankasında talebinize uygun çözüm arıyor. Bu biraz sürebilir; sayfayı
          kapatabilirsiniz, yanıt talebinize kaydedilir.
        </p>
      </AiBox>
    )
  }

  // İş kuralı 4: güven düşükse yanıt talep sahibine gösterilmez (backend gizler)
  if (!answer) {
    if (summary.ai_confidence === null) return null
    return (
      <AiBox>
        <p className="text-sm">
          Bu sorun için bilgi bankasında yeterince güvenilir bir çözüm bulunamadı; talebiniz doğrudan
          teknik ekibe iletildi.
        </p>
      </AiBox>
    )
  }

  const canEvaluate = isRequester && summary.status === 'AI_ANSWERED'

  return (
    <AiBox aside={`Güven ${formatPercent(answer.confidence)}`}>
      <p className="whitespace-pre-wrap text-foreground">{answer.answer}</p>

      {answer.sources.length > 0 && (
        <div className="text-sm">
          Kaynaklar:{' '}
          {answer.sources.map((source) => (
            <code key={source} className="mr-2 rounded bg-white/70 px-1">
              {source}
            </code>
          ))}
        </div>
      )}

      {canEvaluate && (
        <div className="space-y-2 rounded-lg border bg-card p-3 text-foreground">
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
        <p className="text-sm">
          Değerlendirme: {answer.user_feedback === 'HELPFUL' ? 'Sorunu çözdü' : 'Sorunu çözmedi'}
        </p>
      )}
    </AiBox>
  )
}
