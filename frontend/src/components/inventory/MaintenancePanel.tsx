// Seçili cihazın bakım geçmişi (UC-17) ve bakım aç/kapat (UC-16).
//
// İş kuralı 2: bakım açılınca cihaz "Bakımda" olur, kapanınca önceki durumuna
// döner — bu backend'de (domain) uygulanır; ekran yalnızca sonucu gösterir.

import { useState, type FormEvent } from 'react'

import { useCompleteMaintenance, useStartMaintenance } from '@/api/commands/inventory'
import { useMaintenanceHistory } from '@/api/queries/inventory'
import { DeviceStatusBadge } from '@/components/inventory/DeviceStatusBadge'
import { ErrorText, QueryState } from '@/components/layout/QueryState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { formatDateTime } from '@/lib/format'
import { MAINTENANCE_TYPE_LABELS } from '@/lib/labels'
import type { DeviceInventory, MaintenanceType } from '@/types/api'

export function MaintenancePanel({ device }: { device: DeviceInventory }) {
  const history = useMaintenanceHistory(device.device_id)
  const complete = useCompleteMaintenance()
  // Hurdaya ayrılmış veya zaten bakımda olan cihaza yeni bakım açılamaz (iş kuralı 8)
  const canStart = device.status === 'IN_STOCK' || device.status === 'ASSIGNED'

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            {device.asset_tag}
            <DeviceStatusBadge status={device.status} />
          </CardTitle>
          <CardDescription>
            {device.type} · {device.brand} {device.model} · {device.location ?? 'konum yok'}
            {device.holder_name && ` · Zimmet: ${device.holder_name}`}
          </CardDescription>
        </CardHeader>
      </Card>

      {canStart && <StartMaintenanceForm deviceId={device.device_id} />}

      <Card>
        <CardHeader>
          <CardTitle>Bakım geçmişi</CardTitle>
        </CardHeader>
        <CardContent>
          <QueryState query={history}>
            {(records) =>
              records.length === 0 ? (
                <p className="text-sm text-muted-foreground">Bu cihaz için bakım kaydı yok.</p>
              ) : (
                <ul className="space-y-3">
                  {records.map((record) => (
                    <li key={record.id} className="rounded-md border p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{MAINTENANCE_TYPE_LABELS[record.type]}</span>
                        {record.is_open ? (
                          <Badge variant="destructive">Devam ediyor</Badge>
                        ) : (
                          <Badge variant="outline">Tamamlandı</Badge>
                        )}
                        {record.ticket_id && (
                          <span className="text-sm text-muted-foreground">Talep #{record.ticket_id}</span>
                        )}
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm">{record.description}</p>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {record.technician_name} · başlangıç {formatDateTime(record.performed_at)}
                        {record.completed_at && ` · bitiş ${formatDateTime(record.completed_at)}`}
                      </div>
                      {record.is_open && (
                        <Button
                          size="sm"
                          className="mt-2"
                          disabled={complete.isPending}
                          onClick={() => complete.mutate(record.id)}
                        >
                          Bakımı tamamla
                        </Button>
                      )}
                    </li>
                  ))}
                </ul>
              )
            }
          </QueryState>
          <ErrorText error={complete.error} />
        </CardContent>
      </Card>
    </div>
  )
}

function StartMaintenanceForm({ deviceId }: { deviceId: number }) {
  const start = useStartMaintenance()
  const [type, setType] = useState<MaintenanceType>('REPAIR')
  const [description, setDescription] = useState('')
  const [ticketId, setTicketId] = useState('')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!description.trim()) return
    await start.mutateAsync({
      deviceId,
      type,
      description: description.trim(),
      ticketId: ticketId ? Number(ticketId) : null,
    })
    setDescription('')
    setTicketId('')
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Bakım kaydı aç</CardTitle>
        <CardDescription>Cihaz bakım süresince "Bakımda" görünür.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Tür</Label>
              <Select value={type} onValueChange={(value) => setType(value as MaintenanceType)}>
                <SelectTrigger className="w-full" aria-label="Bakım türü">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(MAINTENANCE_TYPE_LABELS).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ticket-id">İlgili talep no (isteğe bağlı)</Label>
              <Input
                id="ticket-id"
                type="number"
                min={1}
                value={ticketId}
                onChange={(event) => setTicketId(event.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="maintenance-description">Açıklama</Label>
            <Textarea
              id="maintenance-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Yapılacak işlem, arıza tespiti…"
              rows={3}
              maxLength={2000}
            />
          </div>
          <ErrorText error={start.error} />
          <Button type="submit" disabled={start.isPending || !description.trim()}>
            Bakımı başlat
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
