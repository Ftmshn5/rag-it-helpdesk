// E4 — AI cevabının kaynakları (Facade/RAG'in arayüzdeki karşılığı).
//
// Her kaynak, AI'ın yanıt üretirken kullandığı bilgi bankası dokümanıdır. Etikete tıklanınca
// o dokümandan AI'a verilen parçalar açılır. Parçalar yanıtla birlikte saklanmış anlık
// kopyalardır: doküman sonradan değişse bile yanıtın hangi metne dayandığı görülür.

import { BookOpenIcon, FileTextIcon } from 'lucide-react'

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { AnswerSource } from '@/types/api'

export function AnswerSources({ sources }: { sources: AnswerSource[] }) {
  if (sources.length === 0) return null

  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium">Kaynaklar</p>
      <ul className="flex flex-wrap gap-2">
        {sources.map((source) => (
          <li key={source.file_path}>
            <SourceChip source={source} />
          </li>
        ))}
      </ul>
    </div>
  )
}

function SourceChip({ source }: { source: AnswerSource }) {
  const fileName = source.file_path.split('/').pop()
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-full border border-ai-border/30 bg-card px-2.5 py-1 text-xs font-medium text-ai-foreground transition-colors hover:border-ai-border hover:bg-ai focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <FileTextIcon aria-hidden className="size-3.5" />
          {source.title}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(32rem,90vw)] p-0">
        <div className="flex items-start gap-2 border-b px-4 py-3">
          <BookOpenIcon aria-hidden className="mt-0.5 size-4 text-ai-foreground" />
          <div className="min-w-0">
            <p className="text-sm font-semibold">{source.title}</p>
            <p className="truncate text-xs text-muted-foreground">Bilgi bankası · {fileName}</p>
          </div>
        </div>
        <div className="max-h-80 space-y-3 overflow-y-auto px-4 py-3">
          {source.excerpts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Bu yanıt için kullanılan parça kaydedilmemiş (eski kayıt).
            </p>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">AI'ın yanıt üretirken kullandığı bölüm(ler):</p>
              {source.excerpts.map((excerpt, index) => (
                <blockquote
                  key={index}
                  className="border-l-[3px] border-ai-border bg-ai px-3 py-2 text-sm whitespace-pre-wrap text-foreground"
                >
                  {excerpt}
                </blockquote>
              ))}
            </>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
