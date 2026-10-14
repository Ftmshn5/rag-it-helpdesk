// UC-08 / UC-09: yönetici cihaz ekler, bilgilerini günceller, zimmetler/iade alır, hurdaya ayırır.
// Seçim adreste tutulur: ?device=3 seçili cihaz, ?new=1 yeni cihaz formu.

import { QrCodeIcon } from 'lucide-react'
import { Link, useSearchParams } from 'react-router'

import { useDevices } from '@/api/queries/inventory'
import {
  AssignmentCard,
  DeviceDetailsForm,
  RegisterDeviceForm,
  RetireDeviceCard,
} from '@/components/inventory/DeviceAdminCards'
import { DevicePicker } from '@/components/inventory/DevicePicker'
import { DeviceHeaderCard, MaintenanceHistoryCard } from '@/components/inventory/MaintenancePanel'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageMessage } from '@/components/layout/PageMessage'
import { QueryState } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'

export function DevicesPage() {
  const devices = useDevices()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = Number(searchParams.get('device')) || null
  const isCreating = searchParams.has('new')

  const select = (deviceId: number) => setSearchParams({ device: String(deviceId) })

  return (
    <>
      <PageHeader
        title="Cihazlar ve zimmet"
        description="Cihaz ekleme, güncelleme, zimmetleme ve iade."
        actions={
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link to="/admin/devices/labels">
                <QrCodeIcon />
                QR etiketleri
              </Link>
            </Button>
            <Button onClick={() => setSearchParams({ new: '1' })}>Yeni cihaz</Button>
          </div>
        }
      />
      <QueryState query={devices}>
        {(data) => {
          const selected = data.find((device) => device.device_id === selectedId)
          return (
            <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
              <DevicePicker devices={data} selectedId={isCreating ? null : selectedId} onSelect={select} />

              {isCreating ? (
                <RegisterDeviceForm onCreated={select} />
              ) : selected ? (
                // key: başka cihaz seçilince formların iç durumu sıfırlanır
                <div key={selected.device_id} className="space-y-4">
                  <DeviceHeaderCard device={selected} />
                  <AssignmentCard device={selected} />
                  {selected.status !== 'RETIRED' && <DeviceDetailsForm device={selected} />}
                  {selected.status === 'IN_STOCK' && <RetireDeviceCard device={selected} />}
                  <MaintenanceHistoryCard deviceId={selected.device_id} />
                </div>
              ) : (
                <PageMessage
                  title="Cihaz seçin"
                  description="Soldaki listeden bir cihaz seçin veya yeni cihaz ekleyin."
                />
              )}
            </div>
          )
        }}
      </QueryState>
    </>
  )
}
