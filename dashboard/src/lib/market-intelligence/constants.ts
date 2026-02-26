export const COMPETITOR_TOKENS = [
  'moen', 'delta', 'kohler', 'grohe', 'hansgrohe', 'pfister',
  'american standard', 'brizo', 'rohl', 'symmons', 'jacuzzi',
  'kingston brass', 'signature hardware', 'kraus', 'vigo',
] as const

export const BRAND_TOKENS = ['allied brass', 'allied'] as const

export const LONG_TAIL_BUCKETS = [
  { label: '1-2 words', min: 1, max: 2 },
  { label: '3-4 words', min: 3, max: 4 },
  { label: '5+ words', min: 5, max: Infinity },
] as const

export const BCG_QUADRANT_LABELS: Record<string, { label: string; description: string }> = {
  star: { label: 'Stars', description: 'High ROAS, High Revenue' },
  cashCow: { label: 'Cash Cows', description: 'High ROAS, Low Revenue' },
  questionMark: { label: 'Question Marks', description: 'Low ROAS, High Revenue' },
  dog: { label: 'Dogs', description: 'Low ROAS, Low Revenue' },
}

export const BCG_COLORS: Record<string, string> = {
  star: '#22c55e',        // green-500
  cashCow: '#3b82f6',     // blue-500
  questionMark: '#f59e0b', // amber-500
  dog: '#ef4444',          // red-500
}

export const SEASONAL_THRESHOLD = 20 // >20% MoM change flags a term
export const NEW_TERM_WINDOW_DAYS = 7
