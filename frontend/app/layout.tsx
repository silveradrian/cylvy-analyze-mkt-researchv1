import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Cylvy Market Intelligence Agent',
  description: 'AI-powered competitive intelligence platform for B2B content analysis with advanced custom dimensions and strategic frameworks',
  icons: {
    icon: '/img/cylvy_lolgo_black.svg',
  }
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className={`${inter.className} antialiased`}>
        <script dangerouslySetInnerHTML={{
          __html: `
            // Auto-set test token for development
            if (!localStorage.getItem('access_token')) {
              localStorage.setItem('access_token', 'test-token-for-development');
              console.log('✅ Test token set for development');
            }
          `
        }} />
        <main className="min-h-screen bg-transparent">
          {children}
        </main>
      </body>
    </html>
  )
}
