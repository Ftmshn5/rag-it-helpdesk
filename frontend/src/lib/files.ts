// Ekran görüntüsü için tarayıcı tarafı ön kontrol (iş kuralı 5).
// Yalnızca hızlı geri bildirim içindir: asıl kontrol backend'de, dosyanın
// içeriğine (magic bytes) bakılarak yapılır; buradaki tür bilgisi dosya
// adından geldiği için güvenilir değildir.

export const ACCEPTED_SCREENSHOT_TYPES = 'image/png,image/jpeg'
export const MAX_SCREENSHOT_MB = 5

export function screenshotProblem(file: File): string | null {
  if (!['image/png', 'image/jpeg'].includes(file.type)) {
    return 'Yalnızca PNG veya JPG formatında ekran görüntüsü yüklenebilir.'
  }
  if (file.size > MAX_SCREENSHOT_MB * 1024 * 1024) {
    return `Dosya boyutu en fazla ${MAX_SCREENSHOT_MB} MB olabilir.`
  }
  return null
}
