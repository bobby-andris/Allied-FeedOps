'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  ClipboardList,
  Layers,
  BarChart3,
  Settings,
  Home,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navigation = [
  { name: 'Overview', href: '/', icon: Home },
  { name: 'Review Queue', href: '/review', icon: ClipboardList },
  { name: 'Batches', href: '/batches', icon: Layers },
  { name: 'Performance', href: '/performance', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

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

      {/* Footer */}
      <div className="border-t p-4">
        <div className="rounded-lg bg-muted p-3 text-xs text-muted-foreground">
          <p className="font-medium text-foreground">Allied Brass</p>
          <p>Feed Optimization Dashboard</p>
        </div>
      </div>
    </div>
  )
}
