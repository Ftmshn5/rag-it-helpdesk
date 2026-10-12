// UC-04: kullanıcı kendisine zimmetli cihazları görür; buradan doğrudan arıza bildirebilir.

import { Link } from 'react-router'

import { useMyDevices } from '@/api/queries/inventory'
import { PageHeader } from '@/components/layout/PageHeader'
import { QueryState } from '@/components/layout/QueryState'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate } from '@/lib/format'
import { DEVICE_STATUS_LABELS } from '@/lib/labels'

export function MyDevicesPage() {
  const devices = useMyDevices()

  return (
    <>
      <PageHeader title="Cihazlarım" description="Size zimmetli cihazlar." />
      <QueryState query={devices}>
        {(data) =>
          data.length === 0 ? (
            <p className="text-sm text-muted-foreground">Size zimmetli bir cihaz yok.</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.map((device) => (
                <Card key={device.device_id}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between gap-2">
                      {device.asset_tag}
                      <Badge variant={device.status === 'IN_REPAIR' ? 'destructive' : 'secondary'}>
                        {DEVICE_STATUS_LABELS[device.status]}
                      </Badge>
                    </CardTitle>
                    <CardDescription>
                      {device.type} · {device.brand} {device.model}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-1 text-sm">
                    <div>Seri no: {device.serial_number}</div>
                    <div>Konum: {device.location ?? '—'}</div>
                    <div>Zimmet tarihi: {formatDate(device.assigned_at)}</div>
                    <Button asChild variant="outline" size="sm" className="mt-3">
                      <Link to={`/user/tickets/new?device=${device.device_id}`}>Arıza bildir</Link>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )
        }
      </QueryState>
    </>
  )
}
