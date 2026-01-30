'use client'

import Link from 'next/link'
import { Heart, Mail, Phone, MapPin, Facebook, Twitter, Instagram, Linkedin } from 'lucide-react'

/**
 * Footer Component
 * Site-wide footer with links, contact info, and social media
 */
export default function Footer() {
    return (
        <footer className="bg-gray-900 text-gray-300">
            <div className="container-custom py-12">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                    {/* Brand Section */}
                    <div>
                        <Link href="/" className="flex items-center gap-2 mb-4">
                            <div className="bg-gradient-to-br from-primary-600 to-secondary-600 p-2 rounded-xl">
                                <Heart className="w-5 h-5 text-white" fill="white" />
                            </div>
                            <span className="text-xl font-display font-bold text-white">
                                Soul Squad
                            </span>
                        </Link>
                        <p className="text-sm text-gray-400 mb-4">
                            Professional wellbeing consultants trained to support you with empathy, care, and love.
                        </p>
                        <div className="flex gap-3">
                            <a href="#" className="p-2 bg-gray-800 rounded-lg hover:bg-primary-600 transition-colors">
                                <Facebook className="w-4 h-4" />
                            </a>
                            <a href="#" className="p-2 bg-gray-800 rounded-lg hover:bg-primary-600 transition-colors">
                                <Twitter className="w-4 h-4" />
                            </a>
                            <a href="#" className="p-2 bg-gray-800 rounded-lg hover:bg-primary-600 transition-colors">
                                <Instagram className="w-4 h-4" />
                            </a>
                            <a href="#" className="p-2 bg-gray-800 rounded-lg hover:bg-primary-600 transition-colors">
                                <Linkedin className="w-4 h-4" />
                            </a>
                        </div>
                    </div>

                    {/* Quick Links */}
                    <div>
                        <h3 className="text-white font-semibold mb-4">Quick Links</h3>
                        <ul className="space-y-2">
                            <li>
                                <Link href="/#services" className="text-sm hover:text-primary-400 transition-colors">
                                    Services
                                </Link>
                            </li>
                            <li>
                                <Link href="/#why-us" className="text-sm hover:text-primary-400 transition-colors">
                                    Why Us
                                </Link>
                            </li>
                            <li>
                                <Link href="/#testimonials" className="text-sm hover:text-primary-400 transition-colors">
                                    Testimonials
                                </Link>
                            </li>
                            <li>
                                <Link href="/app" className="text-sm hover:text-primary-400 transition-colors">
                                    User Dashboard
                                </Link>
                            </li>
                            <li>
                                <Link href="/consultant" className="text-sm hover:text-primary-400 transition-colors">
                                    Consultant Portal
                                </Link>
                            </li>
                        </ul>
                    </div>

                    {/* Services */}
                    <div>
                        <h3 className="text-white font-semibold mb-4">Our Services</h3>
                        <ul className="space-y-2">
                            <li className="text-sm">Virtual Consultation</li>
                            <li className="text-sm">Wellness Planning</li>
                            <li className="text-sm">Professional Coaching</li>
                            <li className="text-sm">Family Workshops</li>
                            <li className="text-sm">Corporate Sessions</li>
                        </ul>
                    </div>

                    {/* Contact Info */}
                    <div>
                        <h3 className="text-white font-semibold mb-4">Contact Us</h3>
                        <ul className="space-y-3">
                            <li className="flex items-start gap-2 text-sm">
                                <Mail className="w-4 h-4 mt-0.5 text-primary-400" />
                                <span>support@soulsquad.com</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm">
                                <Phone className="w-4 h-4 mt-0.5 text-primary-400" />
                                <span>+91 1234 567 890</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm">
                                <MapPin className="w-4 h-4 mt-0.5 text-primary-400" />
                                <span>Bangalore, India</span>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* Bottom Bar */}
                <div className="border-t border-gray-800 mt-8 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
                    <p className="text-sm text-gray-400">
                        © {new Date().getFullYear()} Soul Squad. All rights reserved.
                    </p>
                    <div className="flex gap-6">
                        <Link href="#" className="text-sm text-gray-400 hover:text-primary-400 transition-colors">
                            Privacy Policy
                        </Link>
                        <Link href="#" className="text-sm text-gray-400 hover:text-primary-400 transition-colors">
                            Terms of Service
                        </Link>
                        <Link href="#" className="text-sm text-gray-400 hover:text-primary-400 transition-colors">
                            Cookie Policy
                        </Link>
                    </div>
                </div>
            </div>
        </footer>
    )
}
