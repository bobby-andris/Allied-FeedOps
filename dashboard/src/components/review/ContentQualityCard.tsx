'use client'

/**
 * ContentQualityCard Component
 *
 * Displays 6-dimension quality scoring for product content.
 * Design: Precision Data Dashboard aesthetic with JetBrains Mono typography.
 *
 * Status colors:
 * - Green (#10b981): ≥80% "Ready to publish"
 * - Amber (#f59e0b): 70-79% "Minor revisions needed"
 * - Red (#ef4444): <70% "Major revision required"
 */

import { useState, useEffect } from 'react'
import { analyzeSixDimensions, type Platform, type SixDimensionScore } from '@/lib/quality-scoring'

interface ContentQualityCardProps {
  title: string
  description: string
  platform: Platform
  masterSku: string
}

export function ContentQualityCard({
  title,
  description,
  platform,
  masterSku,
}: ContentQualityCardProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const [analysis, setAnalysis] = useState<SixDimensionScore | null>(null)

  // Load expanded state from localStorage
  useEffect(() => {
    const key = `contentQualityCard:${masterSku}:expanded`
    const stored = localStorage.getItem(key)
    if (stored !== null) {
      setIsExpanded(stored === 'true')
    } else {
      // Default to expanded if no stored preference
      setIsExpanded(true)
    }
  }, [masterSku])

  // Save expanded state to localStorage
  useEffect(() => {
    const key = `contentQualityCard:${masterSku}:expanded`
    localStorage.setItem(key, String(isExpanded))
  }, [isExpanded, masterSku])

  // Analyze content on mount or when props change
  useEffect(() => {
    if (title && description) {
      const result = analyzeSixDimensions(title, description, platform)
      setAnalysis(result)
    }
  }, [title, description, platform])

  if (!analysis) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium uppercase tracking-wide text-gray-500">
            ✅ CONTENT QUALITY
          </h3>
          <span className="text-sm text-gray-400">Loading...</span>
        </div>
      </div>
    )
  }

  const statusColor = {
    ready: '#10b981',   // emerald-500
    minor: '#f59e0b',   // amber-500
    major: '#ef4444',   // red-500
  }[analysis.status]

  const statusLabel = {
    ready: 'Ready to publish',
    minor: 'Minor revisions needed',
    major: 'Major revision required',
  }[analysis.status]

  const toggleExpanded = () => setIsExpanded(!isExpanded)

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white shadow-sm transition-all duration-200 hover:shadow-md"
      style={{
        borderLeft: `4px solid ${statusColor}`,
      }}
    >
      {/* Header - Always Visible */}
      <button
        onClick={toggleExpanded}
        className="w-full p-4 text-left focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
        aria-expanded={isExpanded}
        aria-controls={`quality-card-${masterSku}`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="font-mono text-sm font-medium uppercase tracking-wide text-gray-500">
              ✅ CONTENT QUALITY
            </h3>
            <span
              className="rounded-full px-2 py-0.5 text-xs font-semibold"
              style={{
                backgroundColor: `${statusColor}20`,
                color: statusColor,
              }}
            >
              {analysis.overallScore}%
            </span>
          </div>
          <svg
            className={`h-5 w-5 text-gray-400 transition-transform duration-200 ${
              isExpanded ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>

        {/* Collapsed State - Top Issue */}
        {!isExpanded && (
          <div className="mt-2 text-sm text-gray-600">
            {statusLabel} • {analysis.lowestDimension.label}: {analysis.lowestDimension.score}/10
          </div>
        )}
      </button>

      {/* Expanded State - 6 Dimensions */}
      {isExpanded && (
        <div
          id={`quality-card-${masterSku}`}
          className="border-t border-gray-200 p-4 pt-3"
        >
          <div className="space-y-3">
            {/* Dimension 1: Specificity */}
            <DimensionRow
              label="Specificity"
              score={analysis.specificity}
              detail="Concrete claims"
            />

            {/* Dimension 2: Benefit Coverage */}
            <DimensionRow
              label="Benefit Coverage"
              score={analysis.benefitCoverage}
              detail="Benefits in hook"
            />

            {/* Dimension 3: Keyword Inclusion */}
            <DimensionRow
              label="Keyword Inclusion"
              score={analysis.keywordInclusion}
              detail="Search term coverage"
            />

            {/* Dimension 4: Format Adherence */}
            <DimensionRow
              label="Format Adherence"
              score={analysis.formatAdherence}
              detail="Within limits"
            />

            {/* Dimension 5: Brand Voice */}
            <DimensionRow
              label="Brand Voice"
              score={analysis.brandVoice}
              detail="Premium tone"
            />

            {/* Dimension 6: Factual Accuracy */}
            <DimensionRow
              label="Factual Accuracy"
              score={analysis.factualAccuracy}
              detail="All claims verified"
            />
          </div>

          {/* Bottom Action Hint */}
          {analysis.status !== 'ready' && (
            <div
              className="mt-4 rounded-md p-3 text-sm"
              style={{
                backgroundColor: `${statusColor}10`,
                color: statusColor,
              }}
            >
              💡 Improve {analysis.lowestDimension.label} for +
              {Math.round((10 - analysis.lowestDimension.score) * 10 / 6)}% overall score
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Dimension Row Component
// ============================================================================

interface DimensionRowProps {
  label: string
  score: number
  detail: string
}

function DimensionRow({ label, score, detail }: DimensionRowProps) {
  const percentage = (score / 10) * 100

  // Color based on score (emerald for high, amber for medium, red for low)
  const color = score >= 8 ? '#10b981' : score >= 6 ? '#f59e0b' : '#ef4444'

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs font-medium text-gray-700">{label}</span>
        <span className="font-mono text-xs font-semibold text-gray-900">{score}/10</span>
      </div>

      {/* Progress Bar */}
      <div className="relative h-2 overflow-hidden rounded-full bg-gray-100">
        <div
          className="h-full transition-all duration-500 ease-out"
          style={{
            width: `${percentage}%`,
            background: `linear-gradient(90deg, ${color}, ${color}CC)`,
          }}
        />
      </div>

      {/* Detail Text */}
      <div className="text-xs text-gray-500">{detail}</div>
    </div>
  )
}
