'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import {
  ClipboardList,
  Layers,
  BarChart3,
  Settings,
  Home,
  LogOut,
  Sparkles,
  Eye,
  Search,
  Activity,
  Funnel,
  Gauge,
  Siren,
  GitBranch,
  FlaskConical,
  Target,
  TrendingUp,
  Compass,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import type { User } from '@supabase/supabase-js'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

const navigation: NavItem[] = [
  { name: 'Overview', href: '/', icon: Home },
  { name: 'Generate', href: '/generate', icon: Sparkles },
  { name: 'Review Queue', href: '/review', icon: ClipboardList },
  { name: 'Competitors', href: '/competitors', icon: Eye },
  { name: 'Batches', href: '/batches', icon: Layers },
  { name: 'Performance', href: '/performance', icon: BarChart3 },
  { name: 'Content Impact', href: '/content-impact', icon: TrendingUp },
  { name: 'Search Insights', href: '/search-insights', icon: Search },
  { name: 'Shopping Funnel', href: '/shopping-funnel', icon: Funnel },
  { name: 'Tier Intelligence', href: '/tier-scoring', icon: Target },
  { name: 'Market Intelligence', href: '/market-intelligence', icon: Compass },
  { name: 'Optimization Control', href: '/optimization-control-center', icon: Gauge, badge: 'Soon' },
  { name: 'Intent Control', href: '/intent-control-center', icon: Gauge, badge: 'Soon' },
  { name: 'Search Governance', href: '/search-governance', icon: GitBranch },
  { name: 'Experiment Lab', href: '/experiment-lab', icon: FlaskConical },
  { name: 'Attribution Forensics', href: '/attribution-forensics', icon: Siren },
  { name: 'Backfill Monitoring', href: '/backfill', icon: Activity },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [user, setUser] = useState<User | null>(null)
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return localStorage.getItem('sidebar-collapsed') === 'true'
  })

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user)
    })
  }, [])

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('sidebar-collapsed', String(next))
      return next
    })
  }

  const handleSignOut = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  return (
    <div
      className={cn(
        'flex h-full flex-col border-r bg-card transition-all duration-200 overflow-hidden',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center border-b px-3">
        <Link href="/" className="flex items-center gap-2 min-w-0">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
            F
          </div>
          {!collapsed && (
            <span className="text-lg font-semibold whitespace-nowrap">FeedOps</span>
          )}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto overflow-x-hidden p-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href ||
            (item.href !== '/' && pathname.startsWith(item.href))

          return (
            <Link
              key={item.name}
              href={item.href}
              title={collapsed ? item.name : undefined}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors whitespace-nowrap',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <item.icon className="h-5 w-5 shrink-0" />
              {!collapsed && (
                <>
                  {item.name}
                  {item.badge && (
                    <span className="ml-auto text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </Link>
          )
        })}
      </nav>

      {/* Collapse Toggle */}
      <div className="border-t px-2 py-2">
        <button
          onClick={toggleCollapsed}
          className="flex w-full items-center justify-center rounded-lg px-3 py-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </div>

      {/* User & Sign Out */}
      <div className="border-t p-2 space-y-2">
        {user && !collapsed && (
          <div className="text-xs text-muted-foreground truncate px-1">
            {user.email}
          </div>
        )}
        <Button
          variant="outline"
          size="sm"
          className={cn(
            'w-full text-muted-foreground',
            collapsed ? 'justify-center px-0' : 'justify-start'
          )}
          onClick={handleSignOut}
          title={collapsed ? 'Sign Out' : undefined}
        >
          <LogOut className={cn('h-4 w-4', collapsed ? '' : 'mr-2')} />
          {!collapsed && 'Sign Out'}
        </Button>
        {!collapsed && (
          <div className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">Allied Brass</p>
            <p>Feed Optimization Dashboard</p>
          </div>
        )}
      </div>
    </div>
  )
}
