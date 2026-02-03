import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

type Platform = 'google' | 'bing' | 'shopify'

interface PlatformBadgeProps {
  platform: Platform
  className?: string
}

const platformConfig: Record<Platform, { label: string; className: string }> = {
  google: {
    label: 'Google',
    className: 'bg-blue-100 text-blue-800 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400',
  },
  bing: {
    label: 'Bing',
    className: 'bg-teal-100 text-teal-800 hover:bg-teal-100 dark:bg-teal-900/30 dark:text-teal-400',
  },
  shopify: {
    label: 'Shopify',
    className: 'bg-green-100 text-green-800 hover:bg-green-100 dark:bg-green-900/30 dark:text-green-400',
  },
}

export function PlatformBadge({ platform, className }: PlatformBadgeProps) {
  const config = platformConfig[platform]
  
  return (
    <Badge variant="secondary" className={cn(config.className, className)}>
      {config.label}
    </Badge>
  )
}
