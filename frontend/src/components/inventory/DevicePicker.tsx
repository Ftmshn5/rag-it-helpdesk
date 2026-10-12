// Aranabilir cihaz listesi: teknisyenin bakım ekranı ve yöneticinin cihaz ekranı ortak kullanır.
// Seçim durumu bileşende değil, çağıran sayfada (adres çubuğunda) tutulur.

import { useState } from 'react'

import { DeviceStatusBadge } from '@/components/inventory/DeviceStatusBadge'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import type { DeviceInventory } from '@/types/api'

interface DevicePickerProps {
  devices: DeviceInventory[]
  selectedId: number | null
  onSelect: (deviceId: number) => void
}

export function DevicePicker({ devices, selectedId, onSelect }: DevicePickerProps) {
  const [search, setSearch] = useState('')
  const term = search.trim().toLocaleLowerCase('tr')
  const filtered = devices.filter((device) =>
    [device.asset_tag, device.type, device.brand, device.model, device.holder_name ?? '']
      .join(' ')
      .toLocaleLowerCase('tr')
      .includes(term),
  )

  return (
    <div className="space-y-2">
      <Input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Demirbaş no, tür, marka veya kişi ara…"
        aria-label="Cihaz ara"
      />
      <ul className="max-h-[70vh] space-y-1 overflow-y-auto">
        {filtered.map((device) => (
          <li key={device.device_id}>
            <button
              type="button"
              onClick={() => onSelect(device.device_id)}
              className={cn(
                'flex w-full items-center justify-between gap-2 rounded-md border bg-background px-3 py-2 text-left text-sm hover:bg-muted',
                device.device_id === selectedId && 'border-primary bg-muted',
              )}
            >
              <span className="min-w-0">
                <span className="font-medium">{device.asset_tag}</span>{' '}
                <span className="text-muted-foreground">{device.type}</span>
                {device.holder_name && (
                  <span className="block truncate text-xs text-muted-foreground">
                    {device.holder_name}
                  </span>
                )}
              </span>
              <DeviceStatusBadge status={device.status} />
            </button>
          </li>
        ))}
        {filtered.length === 0 && <li className="text-sm text-muted-foreground">Eşleşen cihaz yok.</li>}
      </ul>
    </div>
  )
}
