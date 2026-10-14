// E5: cihazın QR kodu. Okutulunca cihaz detay sayfası (/devices/{id}) açılır.

import { QRCodeSVG } from 'qrcode.react'

import { deviceUrl } from '@/lib/deviceUrl'

export function DeviceQrCode({ deviceId, size = 128 }: { deviceId: number; size?: number }) {
  return (
    <QRCodeSVG
      value={deviceUrl(deviceId)}
      size={size}
      marginSize={1}
      level="M"
      title={`Cihaz ${deviceId} QR kodu`}
      className="rounded-sm bg-white"
    />
  )
}
