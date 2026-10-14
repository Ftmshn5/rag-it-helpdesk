// UC-12: arıza istatistikleri. Veri read model'den toplanır (GET /statistics/failures);
// talep işlemlerinden sonra kendiliğinden yenilenir (sorgu anahtarı 'tickets' önekinde).
// Seçilen hafta sayısı adreste tutulur (?weeks=12): bağlantı paylaşılabilir.

import { useSearchParams } from 'react-router'

import { useFailureStatistics } from '@/api/queries/statistics'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { AiOutcomeChart, CategoryChart, SlaChart, SummaryCards, WeeklyTrendChart } from '@/components/statistics/StatisticsCharts'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const WEEK_OPTIONS = [4, 8, 12, 26]
const DEFAULT_WEEKS = 8

export function StatisticsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = Number(searchParams.get('weeks'))
  const weeks = WEEK_OPTIONS.includes(requested) ? requested : DEFAULT_WEEKS
  const statistics = useFailureStatistics(weeks)

  return (
    <>
      <PageHeader
        title="Arıza istatistikleri"
        description="Talep eğilimi, kategori dağılımı, SLA uyumu ve AI asistanın başarısı."
        actions={
          <Select value={String(weeks)} onValueChange={(value) => setSearchParams({ weeks: value })}>
            <SelectTrigger className="w-40" aria-label="Zaman aralığı">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {WEEK_OPTIONS.map((option) => (
                <SelectItem key={option} value={String(option)}>
                  Son {option} hafta
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />
      <QueryState query={statistics}>
        {(data) => (
          <div className="space-y-4">
            <SummaryCards statistics={data} />
            <div className="grid gap-4 lg:grid-cols-2">
              <WeeklyTrendChart weekly={data.weekly} />
              <CategoryChart byCategory={data.by_category} />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <SlaChart sla={data.sla} />
              <AiOutcomeChart ai={data.ai} />
            </div>
          </div>
        )}
      </QueryState>
    </>
  )
}
