// E5: cihaz detayı — cihazın QR etiketi okutulunca açılan sayfa (her rol).
// Zimmet sahibini yalnızca personel ve cihazın sahibi görür (backend gizler); bakım geçmişi
// yalnızca personele gösterilir. Kullanıcı buradan doğrudan arıza bildirebilir.

import { PrinterIcon, TriangleAlertIcon } from 'lucide-react'
import { Link, useParams } from 'react-router'

import { useDevice } from '@/api/queries/inventory'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { DeviceQrCode } from '@/components/inventory/DeviceQrCode'
import { MaintenanceHistoryCard } from '@/components/inventory/MaintenancePanel'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageMessage } from '@/components/layout/PageMessage'
import { QueryState } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { DeviceStatusBadge } from '@/components/ui/status-badge'
import { formatDate } from '@/lib/format'
import type { DeviceInventory, User } from '@/types/api'

export function DeviceDetailPage() {
  const deviceId = Number(useParams().deviceId)
  const { user } = useCurrentUser()
  const device = useDevice(deviceId)

  if (!user) {
    return <PageMessage title="Kullanıcı seçin" description="Cihaz bilgisini görmek için sol alttan bir kullanıcı seçin." />
  }

  return (
    <QueryState query={device}>
      {(data) => <DeviceDetail device={data} viewer={user} />}
    </QueryState>
  )
}

function DeviceDetail({ device, viewer }: { device: DeviceInventory; viewer: User }) {
  const isStaff = viewer.role === 'TECHNICIAN' || viewer.role === 'ADMIN'
  const rows: [string, string][] = [
    ['Tür', device.type],
    ['Marka / model', `${device.brand} ${device.model}`],
    ['Seri no', device.serial_number],
    ['Konum', device.location ?? '—'],
    ['Alım tarihi', formatDate(device.purchase_date)],
  ]
  if (device.holder_name) {
    rows.push(['Zimmetli kişi', `${device.holder_name}${device.holder_department ? ` · ${device.holder_department}` : ''}`])
    rows.push(['Zimmet tarihi', formatDate(device.assigned_at)])
  }

  return (
    <>
      <PageHeader
        title={`${device.asset_tag} · ${device.type}`}
        description={`${device.brand} ${device.model}`}
        actions={<DeviceStatusBadge status={device.status} />}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>Cihaz bilgileri</CardTitle>
            </CardHeader>
            <CardContent>
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
          {isStaff && <MaintenanceHistoryCard deviceId={device.device_id} />}
        </div>

        <div className="space-y-4">
          {viewer.role === 'USER' && device.status !== 'RETIRED' && (
            <Card>
              <CardHeader>
                <CardTitle>Bu cihazda sorun mu var?</CardTitle>
              </CardHeader>
              <CardContent>
                <Button asChild className="w-full">
                  <Link to={`/user/tickets/new?device=${device.device_id}`}>
                    <TriangleAlertIcon />
                    Arıza bildir
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}
          {isStaff && (
            <Card>
              <CardHeader>
                <CardTitle>QR etiketi</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center gap-3">
                <DeviceQrCode deviceId={device.device_id} size={144} />
                {viewer.role === 'ADMIN' && (
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/admin/devices/labels?device=${device.device_id}`}>
                      <PrinterIcon />
                      Etiketi yazdır
                    </Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
