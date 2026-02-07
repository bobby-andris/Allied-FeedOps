'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PerformanceCard } from '@/components/review/PerformanceCard'
import { useState } from 'react'

export default function PerformanceTestPage() {
  const [queryClient] = useState(() => new QueryClient())

  return (
    <QueryClientProvider client={queryClient}>
      <div className="container mx-auto p-8 max-w-4xl space-y-8">
        <h1 className="text-3xl font-bold mb-8">PerformanceCard Component Test</h1>

        <div className="space-y-8">
          <div>
            <h2 className="text-xl font-semibold mb-4">Test SKU: 920D-6</h2>
            <PerformanceCard sku="920D-6" platform="google" />
          </div>

          <div>
            <h2 className="text-xl font-semibold mb-4">Test SKU: 1051</h2>
            <PerformanceCard sku="1051" platform="google" />
          </div>
        </div>
      </div>
    </QueryClientProvider>
  )
}
