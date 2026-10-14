// UC-10: talebi teknisyene ata (veya başka teknisyene devret).
// Listede yalnızca talebin seviyesine yeten teknisyenler var (iş kuralı 3 ve 12):
// kıdemli destek (L2) talebi yalnızca kıdemli teknisyene. Kural yine de backend'de uygulanır.

import { useState } from 'react'

import { useAssignTicket } from '@/api/commands/tickets'
import { useUsers } from '@/api/queries/users'
import { ErrorText } from '@/components/layout/QueryState'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { SUPPORT_LEVEL_LABELS } from '@/lib/labels'
import type { SupportLevel } from '@/types/api'

interface AssignTechnicianFormProps {
  ticketId: number
  currentAssigneeId?: number | null
  supportLevel: SupportLevel
  /** Teknisyen başına açık iş sayısı (yönetici dengeli dağıtsın diye; isteğe bağlı) */
  workload?: Map<number, number>
}

export function AssignTechnicianForm({ ticketId, currentAssigneeId, supportLevel, workload }: AssignTechnicianFormProps) {
  const users = useUsers()
  const assign = useAssignTicket()
  const [technicianId, setTechnicianId] = useState('')
  const technicians = (users.data ?? []).filter(
    (user) =>
      user.role === 'TECHNICIAN' &&
      user.id !== currentAssigneeId &&
      (supportLevel !== 'TIER_2' || user.support_level === 'TIER_2'),
  )

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Select value={technicianId} onValueChange={setTechnicianId}>
          <SelectTrigger className="min-w-56" aria-label="Teknisyen">
            <SelectValue placeholder={users.isPending ? 'Yükleniyor…' : 'Teknisyen seçin'} />
          </SelectTrigger>
          <SelectContent>
            {technicians.map((technician) => (
              <SelectItem key={technician.id} value={String(technician.id)}>
                {technician.full_name}
                {technician.support_level === 'TIER_2' && ` · ${SUPPORT_LEVEL_LABELS.TIER_2}`}
                {workload && ` (${workload.get(technician.id) ?? 0} açık iş)`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          disabled={!technicianId || assign.isPending}
          onClick={() => assign.mutate({ ticketId, technicianId: Number(technicianId) })}
        >
          {currentAssigneeId ? 'Devret' : 'Ata'}
        </Button>
      </div>
      <ErrorText error={assign.error ?? users.error} />
    </div>
  )
}
