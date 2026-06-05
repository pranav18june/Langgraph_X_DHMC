import { Routes, Route, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Landing from './pages/Landing'
import Simulator from './pages/Simulator'
import AuditDashboard from './pages/AuditDashboard'
import MerkleExplorer from './pages/MerkleExplorer'
import Glossary from './pages/Glossary'
import './App.css'

function App() {
  const location = useLocation()

  return (
    <div className="app">
      <Navbar />
      <main className="app__main" key={location.pathname}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/simulator" element={<Simulator />} />
          <Route path="/audit" element={<AuditDashboard />} />
          <Route path="/explorer" element={<MerkleExplorer />} />
          <Route path="/glossary" element={<Glossary />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
