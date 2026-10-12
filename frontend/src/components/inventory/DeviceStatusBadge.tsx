import { Badge } from '@/components/ui/badge'
import { DEVICE_STATUS_LABELS } from '@/lib/labels'
import type { DeviceStatus } from '@/types/api'

const VARIANTS: Record<DeviceStatus, 'default' | 'secondary' | 'outline' | 'destructive'> = {
  IN_STOCK: 'outline',
  ASSIGNED: 'secondary',
  IN_REPAIR: 'destructive',
  RETIRED: 'outline',
}

export function DeviceStatusBadge({ status }: { status: DeviceStatus }) {
  return <Badge variant={VARIANTS[status]}>{DEVICE_STATUS_LABELS[status]}</Badge>
}
