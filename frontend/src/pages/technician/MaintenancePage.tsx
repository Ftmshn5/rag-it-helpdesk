// UC-16 / UC-17: teknisyen bir cihaz seçer; bakım geçmişini görür, bakım açar/kapatır.
// Seçili cihaz adreste tutulur (?device=3): yenilemede korunur, bağlantı paylaşılabilir.

import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { useDevices } from '@/api/queries/inventory'
import { DeviceStatusBadge } from '@/components/inventory/DeviceStatusBadge'
import { MaintenancePanel } from '@/components/inventory/MaintenancePanel'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageMessage } from '@/components/layout/PageMessage'
import { QueryState } from '@/components/layout/QueryState'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export function MaintenancePage() {
  const devices = useDevices()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const selectedId = Number(searchParams.get('device')) || null

  return (
    <>
      <PageHeader title="Bakım" description="Cihaz seçin; bakım geçmişini görün, bakım kaydı açın veya kapatın." />
      <QueryState query={devices}>
        {(data) => {
          const term = search.trim().toLocaleLowerCase('tr')
          const filtered = data.filter((device) =>
            `${device.asset_tag} ${device.type} ${device.brand} ${device.model}`
              .toLocaleLowerCase('tr')
              .includes(term),
          )
          const selected = data.find((device) => device.device_id === selectedId)

          return (
            <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
              <div className="space-y-2">
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Demirbaş no, tür veya marka ara…"
                  aria-label="Cihaz ara"
                />
                <ul className="max-h-[70vh] space-y-1 overflow-y-auto">
                  {filtered.map((device) => (
                    <li key={device.device_id}>
                      <button
                        type="button"
                        onClick={() => setSearchParams({ device: String(device.device_id) })}
                        className={cn(
                          'flex w-full items-center justify-between gap-2 rounded-md border bg-background px-3 py-2 text-left text-sm hover:bg-muted',
                          device.device_id === selectedId && 'border-primary bg-muted',
                        )}
                      >
                        <span>
                          <span className="font-medium">{device.asset_tag}</span>{' '}
                          <span className="text-muted-foreground">{device.type}</span>
                        </span>
                        <DeviceStatusBadge status={device.status} />
                      </button>
                    </li>
                  ))}
                  {filtered.length === 0 && (
                    <li className="text-sm text-muted-foreground">Eşleşen cihaz yok.</li>
                  )}
                </ul>
              </div>

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
