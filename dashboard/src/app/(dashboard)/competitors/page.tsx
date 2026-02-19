'use client'

import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { RefreshCw, Search, AlertCircle, Loader2, Eye } from 'lucide-react'
import { CompetitorCard } from '@/components/competitors/CompetitorCard'
import { PatternAnalysis } from '@/components/competitors/PatternAnalysis'
import { ComparisonView } from '@/components/competitors/ComparisonView'
import { SerpOverview } from '@/components/competitors/SerpOverview'
import type {
  CompetitorListing,
  CompetitorPattern,
  CompetitorScrapeJob,
} from '@/lib/supabase/types'
import Link from 'next/link'

const CATEGORIES = [
  { value: 'towel bars', label: 'Towel Bars' },
  { value: 'grab bars', label: 'Grab Bars' },
  { value: 'toilet paper holders', label: 'Toilet Paper Holders' },
  { value: 'robe hooks', label: 'Robe Hooks' },
  { value: 'soap dispensers', label: 'Soap Dispensers' },
  { value: 'glass shelves', label: 'Glass Shelves' },
  { value: 'mirrors', label: 'Mirrors' },
]

interface CompetitorData {
  listings: CompetitorListing[]
  patterns: CompetitorPattern[]
  ourContent: { sku?: string; title: string | null; description: string | null } | null
  recentJobs: CompetitorScrapeJob[]
  domainStats: { domain: string; count: number; avgPosition: number }[]
  lastScraped: string | null
  totalListings: number
  searchQuery: string | null
}

export default function CompetitorsPage() {
  const [category, setCategory] = useState('towel bars')
  const [data, setData] = useState<CompetitorData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Scraping state
  const [scraping, setScraping] = useState(false)
  const [scrapeStatus, setScrapeStatus] = useState<string | null>(null)

  // Comparison state
  const [selectedListing, setSelectedListing] = useState<CompetitorListing | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        category,
        sourceType: 'serp',
      })

      const res = await fetch(`/api/competitors?${params}`)
      if (!res.ok) {
        const errorData = await res.json()
        throw new Error(errorData.error || 'Failed to fetch data')
      }
      const json = await res.json()
      setData(json)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [category])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const pollJobStatus = useCallback(async (jobId: string) => {
    const maxAttempts = 60 // 5 minutes with 5 second intervals
    let attempts = 0

    const poll = async () => {
      attempts++
      try {
        const res = await fetch(`/api/competitors/scrape/${jobId}`)
        const jobData = await res.json()

        if (jobData.status === 'completed') {
          setScrapeStatus(`Completed! ${jobData.message}`)
          setScraping(false)
          fetchData()
          setTimeout(() => setScrapeStatus(null), 5000)
          return
        }

        if (jobData.status === 'failed') {
          setError(jobData.message || 'Scrape failed')
          setScrapeStatus(null)
          setScraping(false)
          return
        }

        // Still running
        setScrapeStatus(jobData.message || `Running... (${attempts * 5}s)`)

        if (attempts < maxAttempts) {
          setTimeout(poll, 5000)
        } else {
          setScrapeStatus('Scrape is taking longer than expected. Check Recent Jobs for status.')
          setScraping(false)
        }
      } catch {
        setError('Error checking job status')
        setScraping(false)
      }
    }

    setTimeout(poll, 3000)
  }, [fetchData])

  const startScrape = async () => {
    setScraping(true)
    setScrapeStatus(`Starting Google SERP scrape for "${category}"...`)

    try {
      const createRes = await fetch('/api/competitors/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category,
          jobType: 'serp',
          source: 'google',
        }),
      })

      if (!createRes.ok) {
        const errorData = await createRes.json()
        throw new Error(errorData.error || 'Failed to create job')
      }

      const { job, message } = await createRes.json()
      setScrapeStatus(message || 'Scrape started, waiting for results...')

      pollJobStatus(job.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Scrape failed')
      setScrapeStatus(null)
      setScraping(false)
    }
  }

  const serpListings = data?.listings.filter((l) => l.source_type === 'serp') || []

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold">Competitor Intelligence</h1>
          <p className="text-muted-foreground">
            Analyze Google SERP results to see who ranks for your product categories
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((cat) => (
                <SelectItem key={cat.value} value={cat.value}>
                  {cat.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            onClick={startScrape}
            disabled={scraping}
          >
            {scraping ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-2" />
            )}
            Scrape Google SERP
          </Button>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {/* Scrape status */}
      {scrapeStatus && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <p className="text-blue-700 text-sm">{scrapeStatus}</p>
        </div>
      )}

      {/* Usage guidance */}
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex items-start gap-3">
        <Search className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
        <div className="text-sm text-amber-800">
          <p className="font-medium mb-1">When to use Competitor Intelligence</p>
          <p>
            Use this page to understand who dominates Google Shopping results for a product category
            and what title patterns they use. For SKU-level keyword data from your own campaigns,
            use{' '}
            <Link href="/search-insights" className="underline underline-offset-2 font-medium">
              Search Insights
            </Link>{' '}
            instead.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Search Query Display */}
          {data?.searchQuery && (
            <Card className="bg-muted/50">
              <CardContent className="py-3">
                <div className="flex items-center gap-3">
                  <Search className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <span className="text-sm text-muted-foreground">Search query used: </span>
                    <span className="font-medium">{data.searchQuery}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-3 gap-6">
            {/* SERP Overview + Patterns */}
            <div className="col-span-1 space-y-4">
              <SerpOverview
                domainStats={data?.domainStats || []}
                totalListings={serpListings.length}
              />
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Winning Patterns</CardTitle>
                </CardHeader>
                <CardContent>
                  <PatternAnalysis
                    patterns={data?.patterns || []}
                    ourContent={data?.ourContent}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Listings */}
            <div className="col-span-2 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">
                  Search Results{' '}
                  <Badge variant="secondary">{serpListings.length}</Badge>
                </h3>
                {data?.lastScraped && (
                  <span className="text-xs text-muted-foreground">
                    Last scraped: {new Date(data.lastScraped).toLocaleDateString()}
                  </span>
                )}
              </div>
              {serpListings.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center space-y-4">
                    <div className="flex justify-center">
                      <div className="rounded-full bg-muted p-4">
                        <Eye className="h-8 w-8 text-muted-foreground" />
                      </div>
                    </div>
                    <div className="space-y-1">
                      <p className="font-medium text-foreground">No SERP data for this category yet</p>
                      <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                        Click &quot;Scrape Google SERP&quot; above to analyze search results for{' '}
                        <strong>{category}</strong>. Scrapes take 2–5 minutes and use your Apify
                        account.
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  {serpListings.slice(0, 12).map((listing) => (
                    <CompetitorCard
                      key={listing.id}
                      listing={listing}
                      onSelect={() => setSelectedListing(listing)}
                      selected={selectedListing?.id === listing.id}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Comparison view */}
      {selectedListing && data?.ourContent && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium">Side-by-Side Comparison</h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedListing(null)}
            >
              Clear Selection
            </Button>
          </div>
          <ComparisonView
            ourContent={data.ourContent}
            competitor={selectedListing}
          />
        </div>
      )}

      {/* Recent jobs */}
      {data?.recentJobs && data.recentJobs.length > 0 && (
        <Card className="mt-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Recent Scrape Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.recentJobs.slice(0, 5).map((job) => (
                <div
                  key={job.id}
                  className="border-b border-muted pb-2 last:border-0 last:pb-0"
                >
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          job.status === 'completed'
                            ? 'default'
                            : job.status === 'failed'
                              ? 'destructive'
                              : 'secondary'
                        }
                      >
                        {job.status}
                      </Badge>
                      <span className="text-muted-foreground">
                        {job.source} ({job.job_type})
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {job.listings_count} listings •{' '}
                      {new Date(job.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  {job.search_query && (
                    <div className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
                      <Search className="h-3 w-3" />
                      <span className="truncate max-w-md">{job.search_query}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
