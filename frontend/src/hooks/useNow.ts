import { useEffect, useState } from 'react'

/** Şimdiki zaman (ms); `intervalMs` aralıkla yenilenir (canlı geri sayımlar için). */
export function useNow(intervalMs = 15_000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}
