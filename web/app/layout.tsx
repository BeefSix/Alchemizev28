import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Toaster } from 'react-hot-toast'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'ZUEXIS - Video Processing Terminal',
  description: 'Advanced video processing system for viral content creation',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="terminal-container min-h-screen">
          <div className="terminal-header">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <span className="zuexis-title text-xl">ZUEXIS</span>
                <span className="text-green-600 text-sm">v2.1.0</span>
                <div className="status-indicator status-online"></div>
                <span className="text-green-600 text-xs">SYSTEM ONLINE</span>
              </div>
              <div className="text-green-600 text-xs font-digital">
                <span>NOSTROMO TERMINAL</span>
                <br />
                <span id="timestamp">{new Date().toLocaleString()}</span>
              </div>
            </div>
          </div>
          <main className="terminal-content">
            {children}
          </main>
        </div>
        <Toaster 
          position="top-right"
          toastOptions={{
            className: 'toast',
            duration: 4000,
            style: {
              background: '#000000',
              color: '#00ff00',
              border: '1px solid #00ff00',
              fontFamily: 'Share Tech Mono, monospace',
            },
          }}
        />
      </body>
    </html>
  )
}
