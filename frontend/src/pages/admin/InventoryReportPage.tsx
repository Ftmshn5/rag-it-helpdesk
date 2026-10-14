// UC-11: envanter raporu. Veri read model'den (read.device_inventory) gelir.
//
// Üstteki sayılar tüm envanterin özetidir; tabloya ise seçilen filtre uygulanır.
// Filtreleme backend'de yapılır (GET /inventory/report?status=&type=) ve adreste
// tutulur: filtreli rapor bağlantı olarak paylaşılabilir.

import { Link, useSearchParams } from 'react-router'

import { useInventoryReport } from '@/api/queries/inventory'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DeviceStatusBadge } from '@/components/ui/status-badge'
import { formatDate } from '@/lib/format'
import { DEVICE_STATUS_LABELS } from '@/lib/labels'
import { cn } from '@/lib/utils'
import type { DeviceInventory, DeviceStatus } from '@/types/api'

const STATUSES = Object.keys(DEVICE_STATUS_LABELS) as DeviceStatus[]

export function InventoryReportPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = (searchParams.get('status') as DeviceStatus | null) ?? undefined
  const type = searchParams.get('type') ?? undefined

  const overview = useInventoryReport()
  const filtered = useInventoryReport(status, type)

  /** Aynı filtreye tekrar tıklamak onu kaldırır. */
  function toggleFilter(key: 'status' | 'type', value: string) {
    const next = new URLSearchParams(searchParams)
    if (next.get(key) === value) next.delete(key)
    else next.set(key, value)
    setSearchParams(next)
  }

  return (
    <>
      <PageHeader
        title="Envanter raporu"
        description="Durum ve türe göre cihaz dağılımı. Filtrelemek için bir sayıya tıklayın."
        actions={
          status || type ? (
            <Button variant="outline" onClick={() => setSearchParams({})}>
              Filtreleri temizle
            </Button>
          ) : null
        }
      />

      <QueryState query={overview}>
        {(report) => (
          <div className="mb-6 space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <SummaryTile label="Toplam" value={report.total} active={!status} onClick={() => setSearchParams({})} />
              {STATUSES.map((key) => (
                <SummaryTile
                  key={key}
                  label={DEVICE_STATUS_LABELS[key]}
                  value={report.by_status[key]}
                  active={status === key}
                  onClick={() => toggleFilter('status', key)}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(report.by_type)
                .sort(([, a], [, b]) => b - a)
                .map(([deviceType, count]) => (
                  <Button
                    key={deviceType}
                    size="sm"
                    variant={type === deviceType ? 'default' : 'outline'}
                    onClick={() => toggleFilter('type', deviceType)}
                  >
                    {deviceType}: {count}
                  </Button>
                ))}
            </div>
          </div>
        )}
      </QueryState>

      <Card>
        <CardHeader>
          <CardTitle>
            Cihazlar
            {status && ` · ${DEVICE_STATUS_LABELS[status]}`}
            {type && ` · ${type}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <QueryState query={filtered}>{(report) => <DeviceTable devices={report.devices} />}</QueryState>
        </CardContent>
      </Card>
    </>
  )
}

function SummaryTile({
  label,
  value,
  active,
  onClick,
}: {
  label: string
  value: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        'rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted',
        active && 'border-primary',
      )}
    >
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </button>
  )
}

function DeviceTable({ devices }: { devices: DeviceInventory[] }) {
  if (devices.length === 0) {
    return <p className="text-sm text-muted-foreground">Bu filtreyle eşleşen cihaz yok.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-left text-muted-foreground">
          <tr className="border-b">
            <th className="py-2 pr-4 font-medium">Demirbaş</th>
            <th className="py-2 pr-4 font-medium">Cihaz</th>
            <th className="py-2 pr-4 font-medium">Durum</th>
            <th className="py-2 pr-4 font-medium">Zimmet</th>
            <th className="py-2 pr-4 font-medium">Konum</th>
            <th className="py-2 pr-4 font-medium">Bakım</th>
          </tr>
        </thead>
        <tbody>
          {devices.map((device) => (
            <tr key={device.device_id} className="border-b last:border-0">
              <td className="py-2 pr-4">
                <Link to={`/admin/devices?device=${device.device_id}`} className="font-medium hover:underline">
                  {device.asset_tag}
                </Link>
              </td>
              <td className="py-2 pr-4">
                {device.type} · {device.brand} {device.model}
              </td>
              <td className="py-2 pr-4">
                <DeviceStatusBadge status={device.status} />
              </td>
              <td className="py-2 pr-4">
                {device.holder_name ? (
                  <>
                    {device.holder_name}
                    <div className="text-xs text-muted-foreground">{device.holder_department}</div>
                  </>
                ) : (
                  '—'
                )}
              </td>
              <td className="py-2 pr-4">{device.location ?? '—'}</td>
              <td className="py-2 pr-4">
                {device.maintenance_count} kayıt
                {device.last_maintenance_at && (
                  <div className="text-xs text-muted-foreground">son: {formatDate(device.last_maintenance_at)}</div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
