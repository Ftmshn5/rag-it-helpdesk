// Yöneticinin cihaz işlemleri (UC-08, UC-09).
//
// Cihaz durumu hiçbir formda doğrudan seçilmez (iş kuralı 6): durum yalnızca
// zimmet / iade / hurdaya ayırma / bakım iş akışlarıyla değişir. Hangi kartın
// görüneceği durum kurallarının arayüzdeki yansımasıdır; kuralın kendisi
// backend'dedir (yanılsa 409 döner ve mesaj gösterilir).

import { useState, type FormEvent } from 'react'

import {
  useAssignDevice,
  useRegisterDevice,
  useRetireDevice,
  useReturnDevice,
  useUpdateDevice,
  type DeviceDetailsInput,
} from '@/api/commands/inventory'
import { useUsers } from '@/api/queries/users'
import { ErrorText } from '@/components/layout/QueryState'
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
import { formatDate } from '@/lib/format'
import type { DeviceInventory } from '@/types/api'

// --- Ortak alanlar ---

interface DetailsState {
  type: string
  brand: string
  model: string
  location: string
  purchase_date: string
}

function TextField({
  id,
  label,
  value,
  onChange,
  required,
  type = 'text',
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  required?: boolean
  type?: 'text' | 'date'
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        value={value}
        required={required}
        maxLength={120}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

function DetailsFields({
  idPrefix,
  value,
  onChange,
}: {
  idPrefix: string
  value: DetailsState
  onChange: (value: DetailsState) => void
}) {
  const set = (key: keyof DetailsState) => (next: string) => onChange({ ...value, [key]: next })
  return (
    <>
      <TextField id={`${idPrefix}-type`} label="Tür" value={value.type} onChange={set('type')} required />
      <TextField id={`${idPrefix}-brand`} label="Marka" value={value.brand} onChange={set('brand')} required />
      <TextField id={`${idPrefix}-model`} label="Model" value={value.model} onChange={set('model')} required />
      <TextField id={`${idPrefix}-location`} label="Konum" value={value.location} onChange={set('location')} />
      <TextField
        id={`${idPrefix}-purchase`}
        label="Satın alma tarihi"
        type="date"
        value={value.purchase_date}
        onChange={set('purchase_date')}
      />
    </>
  )
}

/** Boş metin "değer yok" demektir; API'ye null gider. */
function toDetailsInput(state: DetailsState): DeviceDetailsInput {
  return {
    type: state.type.trim(),
    brand: state.brand.trim(),
    model: state.model.trim(),
    location: state.location.trim() || null,
    purchase_date: state.purchase_date || null,
  }
}

// --- UC-08: cihaz ekle ---

const EMPTY_DETAILS: DetailsState = { type: '', brand: '', model: '', location: '', purchase_date: '' }

export function RegisterDeviceForm({ onCreated }: { onCreated: (deviceId: number) => void }) {
  const register = useRegisterDevice()
  const [assetTag, setAssetTag] = useState('')
  const [serialNumber, setSerialNumber] = useState('')
  const [details, setDetails] = useState<DetailsState>(EMPTY_DETAILS)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const created = await register.mutateAsync({
      asset_tag: assetTag.trim(),
      serial_number: serialNumber.trim(),
      ...toDetailsInput(details),
    })
    onCreated(created.id)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Yeni cihaz</CardTitle>
        <CardDescription>Cihaz depoya ("Depoda") kaydedilir; ardından zimmetlenebilir.</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField id="new-asset-tag" label="Demirbaş no" value={assetTag} onChange={setAssetTag} required />
            <TextField
              id="new-serial"
              label="Seri no"
              value={serialNumber}
              onChange={setSerialNumber}
              required
            />
            <DetailsFields idPrefix="new" value={details} onChange={setDetails} />
          </div>
          <ErrorText error={register.error} />
          <Button type="submit" disabled={register.isPending}>
            Cihazı kaydet
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

// --- UC-08: bilgileri güncelle ---

export function DeviceDetailsForm({ device }: { device: DeviceInventory }) {
  const update = useUpdateDevice()
  const [details, setDetails] = useState<DetailsState>({
    type: device.type,
    brand: device.brand,
    model: device.model,
    location: device.location ?? '',
    purchase_date: device.purchase_date ?? '',
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    // Backend'de null "değiştirme" demektir; konum/tarih silinemez, yalnızca değiştirilebilir.
    update.mutate({ deviceId: device.device_id, details: toDetailsInput(details) })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cihaz bilgileri</CardTitle>
        <CardDescription>
          Demirbaş no ({device.asset_tag}) ve seri no ({device.serial_number}) cihazın kimliğidir,
          değiştirilemez.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <DetailsFields idPrefix="edit" value={details} onChange={setDetails} />
          </div>
          <ErrorText error={update.error} />
          {update.isSuccess && !update.isPending && (
            <p className="text-sm text-muted-foreground">Kaydedildi.</p>
          )}
          <Button type="submit" variant="outline" disabled={update.isPending}>
            Bilgileri kaydet
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

// --- UC-09: zimmet / iade ---

export function AssignmentCard({ device }: { device: DeviceInventory }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Zimmet</CardTitle>
      </CardHeader>
      <CardContent>
        {device.status === 'IN_STOCK' && <AssignDeviceForm deviceId={device.device_id} />}
        {device.status === 'ASSIGNED' && <ReturnDevicePanel device={device} />}
        {device.status === 'IN_REPAIR' && (
          <p className="text-sm text-muted-foreground">
            Cihaz bakımda{device.holder_name && ` (zimmet: ${device.holder_name})`}. Bakım
            tamamlanmadan zimmet veya iade yapılamaz.
          </p>
        )}
        {device.status === 'RETIRED' && (
          <p className="text-sm text-muted-foreground">Hurdaya ayrılmış cihaz zimmetlenemez.</p>
        )}
      </CardContent>
    </Card>
  )
}

function AssignDeviceForm({ deviceId }: { deviceId: number }) {
  const users = useUsers()
  const assign = useAssignDevice()
  const [userId, setUserId] = useState('')

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Select value={userId} onValueChange={setUserId}>
          <SelectTrigger className="min-w-64" aria-label="Zimmetlenecek kişi">
            <SelectValue placeholder={users.isPending ? 'Yükleniyor…' : 'Kişi seçin'} />
          </SelectTrigger>
          <SelectContent>
            {users.data?.map((user) => (
              <SelectItem key={user.id} value={String(user.id)}>
                {user.full_name}
                {user.department && ` — ${user.department}`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          disabled={!userId || assign.isPending}
          onClick={() => assign.mutate({ deviceId, userId: Number(userId) })}
        >
          Zimmetle
        </Button>
      </div>
      <ErrorText error={assign.error ?? users.error} />
    </div>
  )
}

function ReturnDevicePanel({ device }: { device: DeviceInventory }) {
  const returnDevice = useReturnDevice()
  return (
    <div className="space-y-3">
      <p className="text-sm">
        {device.holder_name}
        {device.holder_department && ` (${device.holder_department})`} · {formatDate(device.assigned_at)}{' '}
        tarihinden beri
      </p>
      <Button
        variant="outline"
        disabled={returnDevice.isPending}
        onClick={() => returnDevice.mutate(device.device_id)}
      >
        İade al
      </Button>
      <ErrorText error={returnDevice.error} />
    </div>
  )
}

// --- Hurdaya ayır ---

export function RetireDeviceCard({ device }: { device: DeviceInventory }) {
  const retire = useRetireDevice()

  function handleRetire() {
    // Geri alınamayan işlem: tarayıcının onay penceresi yeterli
    if (window.confirm(`${device.asset_tag} hurdaya ayrılsın mı? Bu işlem geri alınamaz.`)) {
      retire.mutate(device.device_id)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Hurdaya ayır</CardTitle>
        <CardDescription>Yalnızca depodaki cihaz hurdaya ayrılabilir; işlem geri alınamaz.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Button variant="destructive" disabled={retire.isPending} onClick={handleRetire}>
          Hurdaya ayır
        </Button>
        <ErrorText error={retire.error} />
      </CardContent>
    </Card>
  )
}
