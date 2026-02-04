'use client'

import { formatDistanceToNow } from 'date-fns'
import { CheckCircle, XCircle, Upload, RefreshCw } from 'lucide-react'
import Link from 'next/link'

interface Activity {
  type: string
  sku: string
  platform?: string
  status?: string
  timestamp: string
  user?: string
}

interface RecentActivityProps {
  activities: Activity[]
}

function getIcon(type: string, status?: string) {
  if (type === 'publish' && status === 'success') {
    return <Upload className="h-4 w-4 text-green-500" />
  }
  if (type === 'publish' && status === 'failed') {
    return <XCircle className="h-4 w-4 text-red-500" />
  }
  if (type === 'approval') {
    return <CheckCircle className="h-4 w-4 text-blue-500" />
  }
  return <RefreshCw className="h-4 w-4 text-gray-500" />
}

function getActionText(type: string, status?: string, platform?: string) {
  if (type === 'publish' && status === 'success') {
    return `published to ${platform || 'production'}`
  }
  if (type === 'publish' && status === 'failed') {
    return `failed to publish to ${platform || 'production'}`
  }
  if (type === 'unpublish') {
    return `unpublished from ${platform || 'production'}`
  }
  return type
}

export function RecentActivity({ activities }: RecentActivityProps) {
  if (!activities.length) {
    return (
      <p className="text-sm text-muted-foreground py-4">No recent activity</p>
    )
  }

  return (
    <div className="space-y-3">
      {activities.slice(0, 10).map((activity, i) => (
        <div key={i} className="flex items-start gap-3 text-sm">
          {getIcon(activity.type, activity.status)}
          <div className="flex-1 min-w-0">
            <p className="truncate">
              <Link
                href={`/review/${activity.sku}`}
                className="font-medium hover:underline"
              >
                {activity.sku}
              </Link>{' '}
              {getActionText(activity.type, activity.status, activity.platform)}
            </p>
            <p className="text-xs text-muted-foreground">
              {formatDistanceToNow(new Date(activity.timestamp), {
                addSuffix: true,
              })}
              {activity.user && ` by ${activity.user}`}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
