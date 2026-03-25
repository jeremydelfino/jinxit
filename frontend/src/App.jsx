import { BrowserRouter, Routes, Route, Outlet } from 'react-router-dom'
import Navbar from './components/layout/Navbar/index.jsx'
import Home from './pages/Home/index.jsx'
import Player from './pages/Player/index.jsx'
import Bets from './pages/Bets/index.jsx'
import Profile from './pages/Profile/index.jsx'
import Login from './pages/Login/index.jsx'
import Register from './pages/Register/index.jsx'
import Game from './pages/Game/index.jsx'

function WithNavbar() {
  return (
    <div style={{ minHeight: '100vh', background: '#111215' }}>
      <Navbar />
      <Outlet />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route element={<WithNavbar />}>
          <Route path="/" element={<Home />} />
          <Route path="/player/:region/:name/:tag" element={<Player />} />
          <Route path="/bets" element={<Bets />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/game/:id" element={<Game />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}