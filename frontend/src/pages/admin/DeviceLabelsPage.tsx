// E5: yazdırılabilir QR etiketleri (yönetici). ?device=3 yalnızca o cihazın etiketini gösterir.
// Yazdırırken yan menü ve üst çubuk gizlenir (Tailwind `print:` varyantı, AppLayout).

import { PrinterIcon } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'

import { useDevices } from '@/api/queries/inventory'
import { DeviceQrCode } from '@/components/inventory/DeviceQrCode'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'

export function DeviceLabelsPage() {
  const devices = useDevices()
  const [searchParams] = useSearchParams()
  const onlyId = Number(searchParams.get('device')) || null

  return (
    <>
      <div className="print:hidden">
        <PageHeader
          title="QR etiketleri"
          description="Etiketleri yazdırıp cihazlara yapıştırın; okutulunca cihazın sayfası açılır."
          actions={
            <div className="flex gap-2">
              {onlyId && (
                <Button asChild variant="outline">
                  <Link to="/admin/devices/labels">Tüm cihazlar</Link>
                </Button>
              )}
              <Button onClick={() => window.print()}>
                <PrinterIcon />
                Yazdır
              </Button>
            </div>
          }
        />
      </div>
      <QueryState query={devices}>
        {(data) => {
          const labels = data.filter(
            (device) => device.status !== 'RETIRED' && (onlyId === null || device.device_id === onlyId),
          )
          return (
            <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 print:grid-cols-3 print:gap-2">
              {labels.map((device) => (
                <li
                  key={device.device_id}
                  className="flex break-inside-avoid flex-col items-center gap-2 rounded-lg border border-dashed bg-card p-4 text-center print:rounded-none print:border-black"
                >
                  <DeviceQrCode deviceId={device.device_id} size={120} />
                  <div>
                    <p className="font-mono text-base font-semibold">{device.asset_tag}</p>
                    <p className="text-xs text-muted-foreground print:text-black">
                      {device.type} · {device.brand} {device.model}
                    </p>
                    <p className="mt-1 text-[10px] text-muted-foreground print:text-black">
                      Arıza için okutun · BT Destek
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )
        }}
      </QueryState>
    </>
  )
}
