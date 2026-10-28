import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { ChatProvider } from '@/chat/ChatContext'
import { routes } from '@/routes'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
})

const router = createBrowserRouter(routes)

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ChatProvider>
        <RouterProvider router={router} />
      </ChatProvider>
    </QueryClientProvider>
  )
}
