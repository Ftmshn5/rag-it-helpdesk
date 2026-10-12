import { useParams } from 'react-router'

import { PageHeader } from '@/components/layout/PageHeader'

// Talep detayı tüm rollerce kullanılır (talep sahibi, atanan teknisyen, yönetici);
// kimin görebileceğine backend karar verir. İçerik 10. adımda eklenecek.
export function TicketDetailPage() {
  const { ticketId } = useParams()

  return (
    <>
      <PageHeader title={`Talep #${ticketId}`} description="Talep ayrıntıları, AI yanıtı ve notlar." />
      <p className="text-sm text-muted-foreground">Bu ekranın içeriği bir sonraki adımda eklenecek.</p>
    </>
  )
}
