'use client'

import { useMemo } from 'react'
import { Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface HandoffPacketPanelProps {
  packet: Record<string, unknown>
}

function downloadTextFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function toCsvRows(packet: Record<string, unknown>): string[][] {
  const summary = packet.summary as Record<string, unknown> | undefined
  const rows: string[][] = [['field', 'value']]

  if (summary) {
    for (const [key, value] of Object.entries(summary)) {
      rows.push([key, String(value ?? '')])
    }
  }

  const rootCauseRows = (packet.root_causes as Array<Record<string, unknown>> | undefined) ?? []
  rows.push([])
  rows.push(['root_cause_type', 'root_cause_key', 'purchase_revenue', 'revenue_share', 'sessions'])
  for (const row of rootCauseRows) {
    rows.push([
      String(row.rootCauseType ?? ''),
      String(row.rootCauseKey ?? ''),
      String(row.purchaseRevenue ?? ''),
      String(row.revenueShare ?? ''),
      String(row.sessions ?? ''),
    ])
  }

  return rows
}

function csvEscape(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replaceAll('"', '""')}"`
  }
  return value
}

export function HandoffPacketPanel({ packet }: HandoffPacketPanelProps) {
  const exportStamp = useMemo(() => new Date().toISOString().slice(0, 19).replaceAll(':', '-'), [])

  const exportJson = () => {
    downloadTextFile(
      `ga4-attribution-handoff-${exportStamp}.json`,
      JSON.stringify(packet, null, 2),
      'application/json'
    )
  }

  const exportCsv = () => {
    const csvRows = toCsvRows(packet).map((row) => row.map(csvEscape).join(',')).join('\n')
    downloadTextFile(`ga4-attribution-handoff-${exportStamp}.csv`, csvRows, 'text/csv')
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Handoff Packet</CardTitle>
        <CardDescription>
          Export evidence for Analyzify or campaign governance teams without editing tracking setup.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={exportJson}>
          <Download className="mr-2 h-4 w-4" />
          Export JSON
        </Button>
        <Button variant="outline" onClick={exportCsv}>
          <Download className="mr-2 h-4 w-4" />
          Export CSV
        </Button>
      </CardContent>
    </Card>
  )
}
