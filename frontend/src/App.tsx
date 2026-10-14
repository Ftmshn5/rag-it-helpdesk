// Uygulamanın tüm adresleri. Her rolün sayfaları kendi grubunda ve RequireRole
// ile korunur (yalnızca arayüz düzeyinde; asıl yetki kontrolü backend'dedir).

import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'

import { AppLayout } from '@/components/layout/AppLayout'
import { RequireRole } from '@/components/layout/RequireRole'
import { AssignmentQueuePage } from '@/pages/admin/AssignmentQueuePage'
import { DevicesPage } from '@/pages/admin/DevicesPage'
import { InventoryReportPage } from '@/pages/admin/InventoryReportPage'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { AssignedTicketsPage } from '@/pages/technician/AssignedTicketsPage'
import { MaintenancePage } from '@/pages/technician/MaintenancePage'
import { TicketDetailPage } from '@/pages/TicketDetailPage'
import { MyDevicesPage } from '@/pages/user/MyDevicesPage'
import { MyTicketsPage } from '@/pages/user/MyTicketsPage'
import { NewTicketPage } from '@/pages/user/NewTicketPage'

// Büyük kütüphaneler yalnızca kullanıldıkları sayfayla birlikte indirilir (ayrı parça):
// Recharts → yöneticinin istatistik sayfası, dnd-kit → teknisyenin panosu, QR → cihaz sayfaları.
const StatisticsPage = lazy(() =>
  import('@/pages/admin/StatisticsPage').then((module) => ({ default: module.StatisticsPage })),
)
const BoardPage = lazy(() => import('@/pages/technician/BoardPage').then((module) => ({ default: module.BoardPage })))
const DeviceDetailPage = lazy(() =>
  import('@/pages/DeviceDetailPage').then((module) => ({ default: module.DeviceDetailPage })),
)
const DeviceLabelsPage = lazy(() =>
  import('@/pages/admin/DeviceLabelsPage').then((module) => ({ default: module.DeviceLabelsPage })),
)
const pageFallback = <p className="text-sm text-muted-foreground">Yükleniyor…</p>

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="tickets/:ticketId" element={<TicketDetailPage />} />
        {/* QR etiketi bu adrese götürür; her rol açabilir (E5) */}
        <Route
          path="devices/:deviceId"
          element={
            <Suspense fallback={pageFallback}>
              <DeviceDetailPage />
            </Suspense>
          }
        />

        <Route path="user" element={<RequireRole role="USER" />}>
          <Route path="tickets" element={<MyTicketsPage />} />
          <Route path="tickets/new" element={<NewTicketPage />} />
          <Route path="devices" element={<MyDevicesPage />} />
        </Route>

        <Route path="technician" element={<RequireRole role="TECHNICIAN" />}>
          <Route path="queue" element={<AssignedTicketsPage />} />
          <Route
            path="board"
            element={
              <Suspense fallback={pageFallback}>
                <BoardPage />
              </Suspense>
            }
          />
          <Route path="maintenance" element={<MaintenancePage />} />
        </Route>

        <Route path="admin" element={<RequireRole role="ADMIN" />}>
          <Route path="queue" element={<AssignmentQueuePage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route
            path="devices/labels"
            element={
              <Suspense fallback={pageFallback}>
                <DeviceLabelsPage />
              </Suspense>
            }
          />
          <Route path="inventory" element={<InventoryReportPage />} />
          <Route
            path="statistics"
            element={
              <Suspense fallback={pageFallback}>
                <StatisticsPage />
              </Suspense>
            }
          />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
