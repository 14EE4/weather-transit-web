
import React, { useEffect, useState } from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import AppM from './AppM'
import './index.css'

function ResponsiveApp() {
  const [isMobile, setIsMobile] = useState(
    () => window.matchMedia('(max-width: 768px)').matches
  )

  useEffect(() => {
    const media = window.matchMedia('(max-width: 768px)')

    const handleResize = () => {
      setIsMobile(media.matches)
    }

    media.addEventListener('change', handleResize)

    return () => {
      media.removeEventListener('change', handleResize)
    }
  }, [])

  return isMobile ? <AppM /> : <App />
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ResponsiveApp />
  </React.StrictMode>,
)
