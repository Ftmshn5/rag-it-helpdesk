// UC-12 istatistik grafikleri (shadcn/ui chart = Recharts + tema renkleri).
// Bileşenler yalnızca gösterir; tüm hesaplama backend'dedir (FailureStatistics).

import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, XAxis, YAxis } from 'recharts'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  type ChartConfig,
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart'
import { formatPercent } from '@/lib/format'
import { CATEGORY_LABELS } from '@/lib/labels'
import type { AiStatistics, FailureStatistics, SlaStatistics, TicketCategory, WeeklyCount } from '@/types/api'

const weekLabel = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'short' })

// --- Özet kartları ---

export function SummaryCards({ statistics }: { statistics: FailureStatistics }) {
  const { sla, ai } = statistics
  const items = [
    { label: 'Toplam talep', value: String(statistics.total), hint: `${statistics.open} tanesi açık` },
    {
      label: 'Ortalama çözülme süresi',
      value: statistics.average_resolution_hours === null ? '—' : `${statistics.average_resolution_hours} saat`,
      hint: 'açılıştan çözülmeye',
    },
    {
      label: 'SLA uyumu',
      value: sla.compliance_rate === null ? '—' : formatPercent(sla.compliance_rate),
      hint: `${sla.open_overdue} açık talebin süresi geçti`,
    },
    {
      label: 'AI ile otomatik çözüm',
      value: ai.auto_resolution_rate === null ? '—' : formatPercent(ai.auto_resolution_rate),
      hint: 'teknisyene gitmeden kapanan',
    },
  ]

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label}>
          <CardHeader>
            <CardDescription>{item.label}</CardDescription>
            <CardTitle className="text-2xl">{item.value}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">{item.hint}</CardContent>
        </Card>
      ))}
    </div>
  )
}

// --- Haftalık eğilim ---

const weeklyConfig = {
  created: { label: 'Açılan', color: 'var(--chart-2)' },
  resolved: { label: 'Çözülen', color: 'var(--chart-4)' },
} satisfies ChartConfig

export function WeeklyTrendChart({ weekly }: { weekly: WeeklyCount[] }) {
  const data = weekly.map((week) => ({ ...week, label: weekLabel.format(new Date(week.week_start)) }))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Haftalık talepler</CardTitle>
        <CardDescription>Her hafta açılan ve çözülen talep sayısı (pazartesi başlangıçlı).</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={weeklyConfig} className="h-64 w-full">
          <BarChart data={data} accessibilityLayer>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} />
            <YAxis allowDecimals={false} width={28} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Bar dataKey="created" fill="var(--color-created)" radius={4} />
            <Bar dataKey="resolved" fill="var(--color-resolved)" radius={4} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

// --- Kategori dağılımı ---

const categoryConfig = { count: { label: 'Talep', color: 'var(--chart-2)' } } satisfies ChartConfig

export function CategoryChart({ byCategory }: { byCategory: Record<TicketCategory, number> }) {
  const data = (Object.keys(byCategory) as TicketCategory[]).map((category) => ({
    category: CATEGORY_LABELS[category],
    count: byCategory[category],
  }))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Kategoriye göre</CardTitle>
        <CardDescription>Tüm taleplerin arıza kategorisi dağılımı.</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={categoryConfig} className="h-64 w-full">
          <BarChart data={data} layout="vertical" accessibilityLayer margin={{ left: 8 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="category" width={110} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent hideLabel />} />
            <Bar dataKey="count" fill="var(--color-count)" radius={4} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

// --- AI başarısı ---

const aiConfig = {
  answered: { label: 'Yanıt gösterildi', color: 'var(--chart-2)' },
  low_confidence: { label: 'Düşük güven → eskale', color: 'var(--chart-4)' },
  failed: { label: 'AI hata verdi → eskale', color: 'var(--destructive)' },
} satisfies ChartConfig

export function AiOutcomeChart({ ai }: { ai: AiStatistics }) {
  const data = (['answered', 'low_confidence', 'failed'] as const).map((key) => ({
    outcome: key,
    count: ai[key],
    fill: `var(--color-${key})`,
  }))
  const evaluated = ai.helpful + ai.not_helpful

  return (
    <Card>
      <CardHeader>
        <CardTitle>AI asistan</CardTitle>
        <CardDescription>
          AI'ın ele aldığı {ai.processed} talebin sonucu (iş kuralı 4: güven eşiği).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {ai.processed === 0 ? (
          <p className="text-sm text-muted-foreground">Henüz AI'ın ele aldığı talep yok.</p>
        ) : (
          <ChartContainer config={aiConfig} className="mx-auto h-56 w-full">
            <PieChart accessibilityLayer>
              <ChartTooltip content={<ChartTooltipContent nameKey="outcome" hideLabel />} />
              <Pie data={data} dataKey="count" nameKey="outcome" innerRadius={50} strokeWidth={4}>
                {data.map((entry) => (
                  <Cell key={entry.outcome} fill={entry.fill} />
                ))}
              </Pie>
              <ChartLegend content={<ChartLegendContent nameKey="outcome" />} />
            </PieChart>
          </ChartContainer>
        )}
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Kullanıcı: işe yaradı</dt>
          <dd>{ai.helpful}</dd>
          <dt className="text-muted-foreground">Kullanıcı: işe yaramadı</dt>
          <dd>{ai.not_helpful}</dd>
          <dt className="text-muted-foreground">Memnuniyet</dt>
          <dd>{evaluated ? formatPercent(ai.helpful / evaluated) : '—'}</dd>
          <dt className="text-muted-foreground">Ortalama güven</dt>
          <dd>{ai.average_confidence === null ? '—' : formatPercent(ai.average_confidence)}</dd>
        </dl>
      </CardContent>
    </Card>
  )
}

// --- SLA uyumu ---

const slaConfig = {
  met: { label: 'Süresinde çözüldü', color: 'var(--chart-2)' },
  breached: { label: 'Geç çözüldü', color: 'var(--chart-4)' },
  open_overdue: { label: 'Açık, süresi geçti', color: 'var(--destructive)' },
} satisfies ChartConfig

export function SlaChart({ sla }: { sla: SlaStatistics }) {
  const data = (['met', 'breached', 'open_overdue'] as const).map((key) => ({
    outcome: key,
    count: sla[key],
    fill: `var(--color-${key})`,
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>SLA uyumu</CardTitle>
        <CardDescription>
          SLA süresi talebin decorator zincirinden gelir (VIP en geç 24, Acil en geç 4 saat).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={slaConfig} className="h-56 w-full">
          <BarChart data={data} accessibilityLayer>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="outcome"
              tickLine={false}
              axisLine={false}
              tickFormatter={(key: keyof typeof slaConfig) => slaConfig[key].label}
            />
            <YAxis allowDecimals={false} width={28} tickLine={false} axisLine={false} />
            <ChartTooltip content={<ChartTooltipContent nameKey="outcome" hideLabel />} />
            <Bar dataKey="count" radius={4}>
              {data.map((entry) => (
                <Cell key={entry.outcome} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
