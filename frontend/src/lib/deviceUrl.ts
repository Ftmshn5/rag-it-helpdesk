// QR etiketindeki adres: cihaz detay sayfası (E5).
//
// Adresin başı VITE_PUBLIC_URL'den gelir: telefonla okutulacak etiketlerde "localhost"
// işe yaramaz, uygulamanın ağdaki adresi verilmelidir (örn. http://192.168.1.20:5173).
// Tanımlı değilse tarayıcının o anki adresi kullanılır.

export function deviceUrl(deviceId: number): string {
  const base: string = import.meta.env.VITE_PUBLIC_URL ?? window.location.origin
  return `${base.replace(/\/$/, '')}/devices/${deviceId}`
}
