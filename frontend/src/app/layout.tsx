import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
    title: 'Soul Squad - Your Wellbeing Partner',
    description: 'Professional wellbeing consultants trained to support you with empathy, care, and love.',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    )
}
