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
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import type { User } from '@supabase/supabase-js'

const navigation = [
  { name: 'Overview', href: '/', icon: Home },
  { name: 'Generate', href: '/generate', icon: Sparkles },
  { name: 'Review Queue', href: '/review', icon: ClipboardList },
  { name: 'Competitors', href: '/competitors', icon: Eye },
  { name: 'Batches', href: '/batches', icon: Layers },
  { name: 'Performance', href: '/performance', icon: BarChart3 },
  { name: 'Search Insights', href: '/search-insights', icon: Search },
  { name: 'Shopping Funnel', href: '/shopping-funnel', icon: Funnel },
  { name: 'Optimization Control', href: '/optimization-control-center', icon: Gauge },
  { name: 'Intent Control', href: '/intent-control-center', icon: Gauge },
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

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user)
    })
  }, [])

  const handleSignOut = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  return (
    <div className="flex h-full w-64 flex-col border-r bg-card">
      {/* Logo */}
      <div className="flex h-16 items-center border-b px-6">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
            F
          </div>
          <span className="text-lg font-semibold">FeedOps</span>
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/' && pathname.startsWith(item.href))
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* User & Sign Out */}
      <div className="border-t p-4 space-y-3">
        {user && (
          <div className="text-xs text-muted-foreground truncate px-1">
            {user.email}
          </div>
        )}
        <Button 
          variant="outline" 
          size="sm" 
          className="w-full justify-start text-muted-foreground"
          onClick={handleSignOut}
        >
          <LogOut className="h-4 w-4 mr-2" />
          Sign Out
        </Button>
        <div className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Allied Brass</p>
          <p>Feed Optimization Dashboard</p>
        </div>
      </div>
    </div>
  )
}
