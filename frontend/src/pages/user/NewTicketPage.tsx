// UC-01: arıza kaydı oluştur (+ UC-15: isteğe bağlı ekran görüntüsü).
//
// Akış: talep oluşturulur → (dosya varsa) ekran görüntüsü yüklenir → talep
// detayına gidilir. AI yanıtı backend'de talep açılırken üretildiği için detay
// sayfası açıldığında AI'ın önerisi (ya da eskalasyon) hazırdır.

import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router'

import { useAttachScreenshot, useCreateTicket } from '@/api/commands/tickets'
import { useMyDevices } from '@/api/queries/inventory'
import { PageHeader } from '@/components/layout/PageHeader'
import { ErrorText } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
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
import { ACCEPTED_SCREENSHOT_TYPES, MAX_SCREENSHOT_MB, screenshotProblem } from '@/lib/files'
import { CATEGORY_LABELS } from '@/lib/labels'
import type { TicketCategory } from '@/types/api'

const NO_DEVICE = 'NONE'

export function NewTicketPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const devices = useMyDevices()
  const createTicket = useCreateTicket()
  const attachScreenshot = useAttachScreenshot()

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState<TicketCategory | ''>('')
  const [deviceId, setDeviceId] = useState(searchParams.get('device') ?? NO_DEVICE)
  const [isUrgent, setIsUrgent] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const isSubmitting = createTicket.isPending || attachScreenshot.isPending

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    if (title.trim().length < 3) return setFormError('Başlık en az 3 karakter olmalı.')
    if (!category) return setFormError('Lütfen bir kategori seçin.')
    if (!description.trim()) return setFormError('Lütfen sorunu kısaca açıklayın.')
    const fileProblem = file && screenshotProblem(file)
    if (fileProblem) return setFormError(fileProblem)

    const { id } = await createTicket.mutateAsync({
      title: title.trim(),
      description: description.trim(),
      category,
      is_urgent: isUrgent,
      device_id: deviceId === NO_DEVICE ? null : Number(deviceId),
    })

    // Talep artık kayıtlı; yükleme başarısız olsa bile talebi kaybetmeyiz,
    // hatayı detay sayfasında gösteririz (oradan yeniden yüklenebilir).
    let uploadError: string | null = null
    if (file) {
      try {
        await attachScreenshot.mutateAsync({ ticketId: id, file })
      } catch (error) {
        uploadError = (error as Error).message
      }
    }
    navigate(`/tickets/${id}`, { state: { uploadError } })
  }

  return (
    <>
      <PageHeader
        title="Yeni talep"
        description="Sorununuzu anlatın; AI asistan hemen bir çözüm önermeye çalışır."
      />
      <Card className="max-w-2xl">
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="title">Başlık</Label>
              <Input
                id="title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Örn. eduroam ağına bağlanamıyorum"
                maxLength={200}
              />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Kategori</Label>
                <Select value={category} onValueChange={(value) => setCategory(value as TicketCategory)}>
                  <SelectTrigger className="w-full" aria-label="Kategori">
                    <SelectValue placeholder="Seçin" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>İlgili cihaz (isteğe bağlı)</Label>
                <Select value={deviceId} onValueChange={setDeviceId}>
                  <SelectTrigger className="w-full" aria-label="İlgili cihaz">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NO_DEVICE}>Cihaz yok / bilmiyorum</SelectItem>
                    {devices.data?.map((device) => (
                      <SelectItem key={device.device_id} value={device.device_id.toString()}>
                        {device.asset_tag} — {device.brand} {device.model}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Açıklama</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Ne oldu, ne zaman başladı, hangi hata mesajını görüyorsunuz?"
                rows={5}
                maxLength={5000}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="screenshot">Ekran görüntüsü (isteğe bağlı)</Label>
              <Input
                id="screenshot"
                type="file"
                accept={ACCEPTED_SCREENSHOT_TYPES}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              <p className="text-xs text-muted-foreground">
                PNG veya JPG, en fazla {MAX_SCREENSHOT_MB} MB.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="urgent"
                checked={isUrgent}
                onCheckedChange={(checked) => setIsUrgent(checked === true)}
              />
              <Label htmlFor="urgent">Acil (işimi tamamen durduruyor)</Label>
            </div>

            {formError && <p className="text-sm text-destructive">{formError}</p>}
            <ErrorText error={createTicket.error} />

            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Gönderiliyor…' : 'Talebi gönder'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
