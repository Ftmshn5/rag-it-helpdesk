// UC-16 / UC-17: teknisyen bir cihaz seçer; bakım geçmişini görür, bakım açar/kapatır.
// Seçili cihaz adreste tutulur (?device=3): yenilemede korunur, bağlantı paylaşılabilir.

import { useSearchParams } from 'react-router'

import { useDevices } from '@/api/queries/inventory'
import { DevicePicker } from '@/components/inventory/DevicePicker'
import { MaintenancePanel } from '@/components/inventory/MaintenancePanel'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageMessage } from '@/components/layout/PageMessage'
import { QueryState } from '@/components/layout/QueryState'

export function MaintenancePage() {
  const devices = useDevices()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedId = Number(searchParams.get('device')) || null

  return (
    <>
      <PageHeader title="Bakım" description="Cihaz seçin; bakım geçmişini görün, bakım kaydı açın veya kapatın." />
      <QueryState query={devices}>
        {(data) => {
          const selected = data.find((device) => device.device_id === selectedId)
          return (
            <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
              <DevicePicker
                devices={data}
                selectedId={selectedId}
                onSelect={(id) => setSearchParams({ device: String(id) })}
              />
              {selected ? (
                <MaintenancePanel key={selected.device_id} device={selected} />
              ) : (
                <PageMessage title="Cihaz seçin" description="Soldaki listeden bir cihaz seçin." />
              )}
            </div>
          )
        }}
      </QueryState>
    </>
  )
}
