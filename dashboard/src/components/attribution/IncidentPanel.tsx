'use client'

import { AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export interface IncidentPanelItem {
  id: string
  rule_id: string
  severity: string
  status: string
  message: string
  created_at: string
}

interface IncidentPanelProps {
  incidents: IncidentPanelItem[]
}

function severityVariant(severity: string) {
  const normalized = severity.toLowerCase()
  if (normalized === 'critical' || normalized === 'high') {
    return 'destructive' as const
  }
  if (normalized === 'medium') {
    return 'outline' as const
  }
  return 'secondary' as const
}

export function IncidentPanel({ incidents }: IncidentPanelProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Guardrail Incidents</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {incidents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active attribution incidents.</p>
        ) : (
          incidents.map((incident) => (
            <div
              key={incident.id}
              className="rounded-md border border-border bg-muted/20 p-3"
            >
              <div className="mb-1 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-muted-foreground" />
                <Badge variant={severityVariant(incident.severity)}>
                  {incident.severity.toUpperCase()}
                </Badge>
                <Badge variant="outline">{incident.status}</Badge>
                <span className="text-xs text-muted-foreground">{incident.rule_id}</span>
              </div>
              <p className="text-sm">{incident.message}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Detected {new Date(incident.created_at).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  )
}
