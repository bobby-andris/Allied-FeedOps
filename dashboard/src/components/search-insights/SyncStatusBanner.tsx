'use client'

import { useState, useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { RefreshCw, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface SyncStatusBannerProps {
  lastSynced?: string | null
  onSync: () => Promise<void>
  currentJobId?: string | null
}

export function SyncStatusBanner({
  lastSynced,
  onSync,
  currentJobId,
}: SyncStatusBannerProps) {
  const [syncing, setSyncing] = useState(false)
  const [jobStatus, setJobStatus] = useState<{
    status: string
    progress: number
    queriesFetched: number
    queriesEnriched: number
    error?: string
  } | null>(null)

  // Poll job status if we have a job ID
  useEffect(() => {
    if (!currentJobId) {
      return
    }

    let isCancelled = false

    const pollStatus = async () => {
      try {
        const res = await fetch(`/api/search-insights/sync/${currentJobId}`)
        if (res.ok && !isCancelled) {
          const data = await res.json()
          setJobStatus({
            status: data.status,
            progress: data.progress,
            queriesFetched: data.queriesFetched,
            queriesEnriched: data.queriesEnriched,
            error: data.errorMessage,
          })

          // Stop polling if complete or failed
          if (data.status === 'completed' || data.status === 'failed') {
            setSyncing(false)
          }
        }
      } catch (err) {
        console.error('Failed to poll job status:', err)
      }
    }

    // Poll immediately and then every 2 seconds
    pollStatus()
    const interval = setInterval(pollStatus, 2000)

    return () => {
      isCancelled = true
      clearInterval(interval)
      setJobStatus(null)
    }
  }, [currentJobId])

  async function handleSync() {
    setSyncing(true)
    try {
      await onSync()
    } catch (err) {
      setSyncing(false)
      console.error('Sync failed:', err)
    }
  }

  const isRunning = jobStatus?.status === 'running' || jobStatus?.status === 'pending'

  return (
    <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border">
      <div className="flex items-center gap-4">
        {/* Status Icon */}
        {isRunning ? (
          <RefreshCw className="h-5 w-5 text-blue-500 animate-spin" />
        ) : jobStatus?.status === 'completed' ? (
          <CheckCircle className="h-5 w-5 text-green-500" />
        ) : jobStatus?.status === 'failed' ? (
          <AlertCircle className="h-5 w-5 text-red-500" />
        ) : (
          <Clock className="h-5 w-5 text-muted-foreground" />
        )}

        {/* Status Text */}
        <div className="space-y-1">
          {isRunning ? (
            <>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Syncing search terms...</span>
                <Badge variant="secondary">{jobStatus?.progress || 0}%</Badge>
              </div>
              <div className="w-48">
                <Progress value={jobStatus?.progress || 0} className="h-1" />
              </div>
              {jobStatus && jobStatus.queriesFetched > 0 && (
                <p className="text-xs text-muted-foreground">
                  {jobStatus.queriesFetched.toLocaleString()} queries fetched
                  {jobStatus.queriesEnriched > 0 &&
                    `, ${jobStatus.queriesEnriched.toLocaleString()} enriched`}
                </p>
              )}
            </>
          ) : jobStatus?.status === 'completed' ? (
            <>
              <span className="text-sm font-medium text-green-600">
                Sync completed
              </span>
              <p className="text-xs text-muted-foreground">
                {jobStatus.queriesFetched.toLocaleString()} queries synced
                {jobStatus.queriesEnriched > 0 &&
                  `, ${jobStatus.queriesEnriched.toLocaleString()} enriched with search volume`}
              </p>
            </>
          ) : jobStatus?.status === 'failed' ? (
            <>
              <span className="text-sm font-medium text-red-600">Sync failed</span>
              <p className="text-xs text-muted-foreground">
                {jobStatus.error || 'Unknown error'}
              </p>
            </>
          ) : lastSynced ? (
            <>
              <span className="text-sm">
                Last synced{' '}
                <span className="font-medium">
                  {formatDistanceToNow(new Date(lastSynced), { addSuffix: true })}
                </span>
              </span>
            </>
          ) : (
            <span className="text-sm text-muted-foreground">
              No sync data available
            </span>
          )}
        </div>
      </div>

      {/* Sync Button */}
      <Button
        onClick={handleSync}
        disabled={syncing || isRunning}
        variant="outline"
        size="sm"
      >
        <RefreshCw
          className={`h-4 w-4 mr-2 ${syncing || isRunning ? 'animate-spin' : ''}`}
        />
        {syncing || isRunning ? 'Syncing...' : 'Sync Data'}
      </Button>
    </div>
  )
}
