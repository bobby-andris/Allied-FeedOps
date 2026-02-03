import { cn } from '@/lib/utils'

interface QualityScoreProps {
  score: number | null
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function QualityScore({ score, size = 'md', showLabel = true }: QualityScoreProps) {
  if (score === null) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <span className="text-sm">No score</span>
      </div>
    )
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-100 dark:bg-green-900/30'
    if (score >= 70) return 'text-yellow-600 bg-yellow-100 dark:bg-yellow-900/30'
    return 'text-red-600 bg-red-100 dark:bg-red-900/30'
  }

  const getScoreLabel = (score: number) => {
    if (score >= 80) return 'Excellent'
    if (score >= 70) return 'Good'
    return 'Needs Work'
  }

  const sizeClasses = {
    sm: 'h-6 w-6 text-xs',
    md: 'h-8 w-8 text-sm',
    lg: 'h-10 w-10 text-base',
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          'flex items-center justify-center rounded-full font-bold',
          getScoreColor(score),
          sizeClasses[size]
        )}
      >
        {Math.round(score)}
      </div>
      {showLabel && (
        <span className={cn('text-sm', getScoreColor(score).split(' ')[0])}>
          {getScoreLabel(score)}
        </span>
      )}
    </div>
  )
}
