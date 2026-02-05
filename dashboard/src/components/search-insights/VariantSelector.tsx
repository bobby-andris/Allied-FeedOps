'use client'

import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Info } from 'lucide-react'

interface VariantSelectorProps {
  platform: 'google' | 'bing' | 'shopify'
  viewType: 'aggregate' | 'variant'
  selectedFinish: string | null
  availableFinishes: Array<{ finish: string | null; finish_code: string | null; count?: number }>
  onViewTypeChange: (view: 'aggregate' | 'variant') => void
  onFinishChange: (finishCode: string | null) => void
}

export function VariantSelector({
  platform,
  viewType,
  selectedFinish,
  availableFinishes,
  onViewTypeChange,
  onFinishChange,
}: VariantSelectorProps) {
  // Shopify doesn't need variant selection
  if (platform === 'shopify') {
    return (
      <div className="p-3 rounded-lg bg-blue-50 border border-blue-200 dark:bg-blue-950 dark:border-blue-900">
        <div className="flex items-start gap-2">
          <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-blue-800 dark:text-blue-200">
            <strong>Shopify:</strong> Product pages show the master description with all
            28 finishes selectable. Variant-level breakdown is not applicable.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-950 dark:border-amber-900">
        <div className="flex items-start gap-2">
          <Info className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
          <p className="text-sm text-amber-800 dark:text-amber-200">
            <strong>Google/Bing:</strong> Ads are served at the variant level. Each
            finish has its own title/description in the GMC feed.
          </p>
        </div>
      </div>

      <div className="flex gap-4 items-center flex-wrap">
        <Tabs
          value={viewType}
          onValueChange={(v) => onViewTypeChange(v as 'aggregate' | 'variant')}
        >
          <TabsList>
            <TabsTrigger value="aggregate">All Variants (Aggregate)</TabsTrigger>
            <TabsTrigger value="variant">By Finish Variant</TabsTrigger>
          </TabsList>
        </Tabs>

        {viewType === 'variant' && (
          <Select
            value={selectedFinish || 'all'}
            onValueChange={(v) => onFinishChange(v === 'all' ? null : v)}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All finishes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All finishes</SelectItem>
              {availableFinishes
                .filter((f) => f.finish_code)
                .map((f) => (
                  <SelectItem key={f.finish_code!} value={f.finish_code!}>
                    {f.finish || f.finish_code}
                    {f.count !== undefined && ` (${f.count})`}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  )
}
