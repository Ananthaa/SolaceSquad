'use client'

import { ReactNode } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
    LayoutDashboard,
    Activity,
    BookOpen,
    Calendar,
    MessageSquare,
    FileText,
    Dumbbell,
    Sparkles,
    Settings,
    LogOut,
    Heart,
    Menu,
    X
} from 'lucide-react'
import { useState } from 'react'

/**
 * Protected Layout Component
 * Sidebar navigation for authenticated areas (/app and /consultant)
 * Reusable for both user and consultant dashboards
 */

interface ProtectedLayoutProps {
    children: ReactNode
    userType: 'user' | 'consultant'
}

export default function ProtectedLayout({ children, userType }: ProtectedLayoutProps) {
    const pathname = usePathname()
    const [sidebarOpen, setSidebarOpen] = useState(false)

    // Navigation items based on user type
    const userNavItems = [
        { icon: LayoutDashboard, label: 'Dashboard', href: '/app' },
        { icon: Activity, label: 'Vitals & Scan', href: '/app/vitals' },
        { icon: BookOpen, label: 'Daily Journal', href: '/app/journal' },
        { icon: Calendar, label: 'Grooming', href: '/app/grooming' },
        { icon: MessageSquare, label: 'AI Assistant', href: '/app/ai-chat' },
        { icon: Dumbbell, label: 'Exercise', href: '/app/exercise' },
        { icon: FileText, label: 'Reports', href: '/app/reports' },
        { icon: Sparkles, label: 'Find Consultant', href: '/app/consultants' },
    ]

    const consultantNavItems = [
        { icon: LayoutDashboard, label: 'Dashboard', href: '/consultant' },
        { icon: Activity, label: 'My Clients', href: '/consultant/clients' },
        { icon: Calendar, label: 'Schedule', href: '/consultant/schedule' },
        { icon: MessageSquare, label: 'Messages', href: '/consultant/messages' },
        { icon: FileText, label: 'Reports', href: '/consultant/reports' },
        { icon: Settings, label: 'Profile', href: '/consultant/profile' },
    ]

    const navItems = userType === 'user' ? userNavItems : consultantNavItems

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Top Bar */}
            <header className="fixed top-0 left-0 right-0 z-40 bg-white border-b border-gray-200 h-16">
                <div className="flex items-center justify-between h-full px-4">
                    {/* Logo & Mobile Menu */}
                    <div className="flex items-center gap-4">
                        <button
                            className="lg:hidden p-2 hover:bg-gray-100 rounded-lg"
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                        >
                            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                        </button>

                        <Link href="/" className="flex items-center gap-2">
                            <div className="bg-gradient-to-br from-primary-600 to-secondary-600 p-1.5 rounded-lg">
                                <Heart className="w-5 h-5 text-white" fill="white" />
                            </div>
                            <span className="text-xl font-display font-bold gradient-text">
                                Soul Squad
                            </span>
                        </Link>
                    </div>

                    {/* User Menu */}
                    <div className="flex items-center gap-4">
                        <div className="text-right hidden sm:block">
                            <div className="text-sm font-medium text-gray-900">John Doe</div>
                            <div className="text-xs text-gray-500 capitalize">{userType} Account</div>
                        </div>
                        <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-secondary-400 rounded-full flex items-center justify-center text-white font-semibold">
                            JD
                        </div>
                    </div>
                </div>
            </header>

            {/* Sidebar */}
            <aside className={`
        fixed top-16 left-0 bottom-0 w-64 bg-white border-r border-gray-200 z-30
        transform transition-transform duration-200 lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
                <nav className="p-4 space-y-1">
                    {navItems.map((item) => {
                        const isActive = pathname === item.href
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                className={`
                  flex items-center gap-3 px-4 py-3 rounded-lg transition-colors
                  ${isActive
                                        ? 'bg-primary-50 text-primary-700 font-medium'
                                        : 'text-gray-700 hover:bg-gray-100'
                                    }
                `}
                                onClick={() => setSidebarOpen(false)}
                            >
                                <item.icon className="w-5 h-5" />
                                <span>{item.label}</span>
                            </Link>
                        )
                    })}

                    <div className="pt-4 mt-4 border-t border-gray-200 space-y-1">
                        <Link
                            href="/settings"
                            className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
                        >
                            <Settings className="w-5 h-5" />
                            <span>Settings</span>
                        </Link>

                        <button
                            className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-red-600 hover:bg-red-50 transition-colors"
                        >
                            <LogOut className="w-5 h-5" />
                            <span>Logout</span>
                        </button>
                    </div>
                </nav>
            </aside>

            {/* Main Content */}
            <main className="lg:ml-64 pt-16 min-h-screen">
                <div className="p-6">
                    {children}
                </div>
            </main>

            {/* Mobile Sidebar Overlay */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-20 lg:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}
        </div>
    )
}
