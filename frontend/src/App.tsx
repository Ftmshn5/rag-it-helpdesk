// Uygulamanın tüm adresleri. Her rolün sayfaları kendi grubunda ve RequireRole
// ile korunur (yalnızca arayüz düzeyinde; asıl yetki kontrolü backend'dedir).

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

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<HomePage />} />
        <Route path="tickets/:ticketId" element={<TicketDetailPage />} />

        <Route path="user" element={<RequireRole role="USER" />}>
          <Route path="tickets" element={<MyTicketsPage />} />
          <Route path="tickets/new" element={<NewTicketPage />} />
          <Route path="devices" element={<MyDevicesPage />} />
        </Route>

        <Route path="technician" element={<RequireRole role="TECHNICIAN" />}>
          <Route path="queue" element={<AssignedTicketsPage />} />
          <Route path="maintenance" element={<MaintenancePage />} />
        </Route>

        <Route path="admin" element={<RequireRole role="ADMIN" />}>
          <Route path="queue" element={<AssignmentQueuePage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="inventory" element={<InventoryReportPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
