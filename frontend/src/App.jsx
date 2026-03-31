import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom'
import Navbar from './components/layout/Navbar/index.jsx'
import Home from './pages/Home/index.jsx'
import Player from './pages/Player/index.jsx'
import Game from './pages/Game/index.jsx'
import Bets from './pages/Bets/index.jsx'
import Profile from './pages/Profile/index.jsx'
import Login from './pages/Login/index.jsx'
import Register from './pages/Register/index.jsx'
import Leaderboard from './pages/Leaderboard/index.jsx'
import BetOnPros from './pages/BetOnPros/index.jsx'

import Footer from './components/layout/Footer/index.jsx'
// App.jsx — dans la Route WithNavbar
import Settings from './pages/Settings/index.jsx'
function WithNavbar() {
  return (
    <div style={{ minHeight: '100vh', background: '#111215' }}>
      <Navbar />
      <Outlet />
      <Footer />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />
        {/* Page Game sans navbar (plein écran) */}
        <Route path="/game/:id" element={<Game />} />
        <Route element={<WithNavbar />}>
          <Route path="/"                              element={<Home />} />
          <Route path="/player/:region/:name/:tag"     element={<Player />} />
          <Route path="/bets"                          element={<Bets />} />
          <Route path="/profile/:userId" element={<Profile />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/leaderboard"                    element={<Leaderboard />} />
          <Route path="/betonpros" element={<BetOnPros />} />    
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}