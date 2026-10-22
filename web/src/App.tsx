import { useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router'
import { Footer } from './components/Footer'
import { Header } from './components/Header'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'
import { RacesPage } from './pages/RacesPage'
import { StrategyPage } from './pages/StrategyPage'
import { TyresPage } from './pages/TyresPage'

/** New section, new page: start at the top (filters inside a section keep the scroll). */
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo?.({ top: 0 })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <div className="flex min-h-dvh flex-col">
      <ScrollToTop />
      <Header />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/races" element={<RacesPage />} />
          <Route path="/tyres" element={<TyresPage />} />
          <Route path="/strategy" element={<StrategyPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
