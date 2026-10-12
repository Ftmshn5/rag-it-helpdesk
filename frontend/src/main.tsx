import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'

import App from '@/App'
import { ApiError } from '@/api/client'
import { CurrentUserProvider } from '@/auth/CurrentUserProvider'
import '@/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Yetki/bulunamadı gibi hatalarda tekrar denemek anlamsız; yalnızca ağ hatasında dene
      retry: (failureCount, error) =>
        failureCount < 2 && error instanceof ApiError && error.status === 0,
      refetchOnWindowFocus: true, // sekmeye dönünce güncel veri (teknisyen kuyruğu vb.)
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <CurrentUserProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </CurrentUserProvider>
    </QueryClientProvider>
  </StrictMode>,
)
