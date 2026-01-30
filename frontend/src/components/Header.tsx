'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Menu, X, Heart } from 'lucide-react'

/**
 * Header Component
 * Navigation bar with responsive mobile menu
 * Includes auth placeholders (Login/Signup buttons)
 */
export default function Header() {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

    return (
        <header className="fixed top-0 left-0 right-0 z-50 glass shadow-sm">
            <nav className="container-custom">
                <div className="flex items-center justify-between h-20">
                    {/* Logo */}
                    <Link href="/" className="flex items-center gap-2 group">
                        <div className="bg-gradient-to-br from-primary-600 to-secondary-600 p-2 rounded-xl group-hover:scale-110 transition-transform">
                            <Heart className="w-6 h-6 text-white" fill="white" />
                        </div>
                        <span className="text-2xl font-display font-bold gradient-text">
                            Soul Squad
                        </span>
                    </Link>

                    {/* Desktop Navigation */}
                    <div className="hidden md:flex items-center gap-8">
                        <Link href="/#services" className="text-gray-700 hover:text-primary-600 font-medium transition-colors">
                            Services
                        </Link>
                        <Link href="/#why-us" className="text-gray-700 hover:text-primary-600 font-medium transition-colors">
                            Why Us
                        </Link>
                        <Link href="/#testimonials" className="text-gray-700 hover:text-primary-600 font-medium transition-colors">
                            Testimonials
                        </Link>
                        <Link href="/consultant" className="text-gray-700 hover:text-primary-600 font-medium transition-colors">
                            For Consultants
                        </Link>
                    </div>

                    {/* Auth Buttons - Desktop */}
                    <div className="hidden md:flex items-center gap-4">
                        <button className="text-primary-700 hover:text-primary-800 font-medium transition-colors">
                            Login
                        </button>
                        <button className="btn btn-primary">
                            Get Started
                        </button>
                    </div>

                    {/* Mobile Menu Button */}
                    <button
                        className="md:hidden p-2 text-gray-700 hover:text-primary-600"
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                    >
                        {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                    </button>
                </div>

                {/* Mobile Navigation */}
                {mobileMenuOpen && (
                    <div className="md:hidden py-4 animate-slide-down">
                        <div className="flex flex-col gap-4">
                            <Link
                                href="/#services"
                                className="text-gray-700 hover:text-primary-600 font-medium py-2"
                                onClick={() => setMobileMenuOpen(false)}
                            >
                                Services
                            </Link>
                            <Link
                                href="/#why-us"
                                className="text-gray-700 hover:text-primary-600 font-medium py-2"
                                onClick={() => setMobileMenuOpen(false)}
                            >
                                Why Us
                            </Link>
                            <Link
                                href="/#testimonials"
                                className="text-gray-700 hover:text-primary-600 font-medium py-2"
                                onClick={() => setMobileMenuOpen(false)}
                            >
                                Testimonials
                            </Link>
                            <Link
                                href="/consultant"
                                className="text-gray-700 hover:text-primary-600 font-medium py-2"
                                onClick={() => setMobileMenuOpen(false)}
                            >
                                For Consultants
                            </Link>
                            <div className="flex flex-col gap-2 pt-4 border-t">
                                <button className="btn btn-secondary w-full">
                                    Login
                                </button>
                                <button className="btn btn-primary w-full">
                                    Get Started
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </nav>
        </header>
    )
}
