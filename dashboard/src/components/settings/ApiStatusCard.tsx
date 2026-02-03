'use client'

import { ReactNode } from 'react'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { AlertCircle, CheckCircle2, HelpCircle, Settings } from 'lucide-react'

export type ServiceStatusType = 'connected' | 'error' | 'not_configured' | 'configured' | 'unknown'

export interface ApiStatusCardProps {
  name: string
  icon?: ReactNode
  status: ServiceStatusType
  details?: string
  error?: string
  latency?: number
  loading?: boolean
}

function StatusBadge({ status, latency }: { status: ServiceStatusType; latency?: number }) {
  switch (status) {
    case 'connected':
      return (
        <Badge className="bg-green-100 text-green-800 hover:bg-green-100 gap-1">
          <CheckCircle2 className="h-3 w-3" />
          Connected
          {latency !== undefined && (
            <span className="text-green-600 text-xs ml-1">({latency}ms)</span>
          )}
        </Badge>
      )
    case 'configured':
      return (
        <Badge className="bg-blue-100 text-blue-800 hover:bg-blue-100 gap-1">
          <Settings className="h-3 w-3" />
          Configured
        </Badge>
      )
    case 'error':
      return (
        <Badge className="bg-red-100 text-red-800 hover:bg-red-100 gap-1">
          <AlertCircle className="h-3 w-3" />
          Error
        </Badge>
      )
    case 'not_configured':
      return (
        <Badge className="bg-yellow-100 text-yellow-800 hover:bg-yellow-100 gap-1">
          <HelpCircle className="h-3 w-3" />
          Not Configured
        </Badge>
      )
    default:
      return (
        <Badge className="bg-gray-100 text-gray-800 hover:bg-gray-100 gap-1">
          <HelpCircle className="h-3 w-3" />
          Unknown
        </Badge>
      )
  }
}

function LoadingState() {
  return (
    <div className="flex items-center justify-between">
      <div className="space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-48" />
      </div>
      <Skeleton className="h-6 w-24" />
    </div>
  )
}

export function ApiStatusCard({
  name,
  icon,
  status,
  details,
  error,
  latency,
  loading = false,
}: ApiStatusCardProps) {
  if (loading) {
    return <LoadingState />
  }

  return (
    <div className="flex items-center justify-between">
      <div>
        <p className="font-medium flex items-center gap-2">
          {icon}
          {name}
        </p>
        {details && (
          <p className="text-sm text-muted-foreground">{details}</p>
        )}
        {error && status === 'error' && (
          <p className="text-sm text-red-600 mt-1">{error}</p>
        )}
        {error && status === 'not_configured' && (
          <p className="text-sm text-yellow-600 mt-1">{error}</p>
        )}
      </div>
      <StatusBadge status={status} latency={latency} />
    </div>
  )
}
