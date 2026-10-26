import type { RouteObject } from 'react-router'
import { Layout } from '@/components/Layout'
import { AskPage } from '@/pages/AskPage'
import { ContractView } from '@/pages/ContractView'
import { Dashboard } from '@/pages/Dashboard'
import { EvalPage } from '@/pages/EvalPage'
import { UploadPage } from '@/pages/UploadPage'

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Dashboard /> },
      { path: '/upload', element: <UploadPage /> },
      { path: '/contracts/:id', element: <ContractView /> },
      { path: '/ask', element: <AskPage /> },
      { path: '/eval', element: <EvalPage /> },
    ],
  },
]
