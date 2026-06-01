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
import AdminRatings from './pages/AdminRatings/index.jsx'
import Settings from './pages/Settings/index.jsx'
import Games from './pages/Games/index.jsx'
import CoachDiff from './pages/CoachDiff/index.jsx'
import CoachDiffGame from './pages/CoachDiffGame/index.jsx'
import LootBox from './pages/LootBox/index.jsx'
import Footer from './components/layout/Footer/index.jsx'
import AdminCards from './pages/AdminCards/index.jsx'
import AdminLootboxes from './pages/AdminLootboxes/index.jsx'
import AdminGm from './pages/AdminGm/index.jsx'
import GameMode from './pages/GameMode'


function WithNavbar() {
  return (
    <div style={{ minHeight: '100vh', background: '#171717' }}>
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
        <Route path="/game/:id" element={<Game />} />
        <Route element={<WithNavbar />}>
          <Route path="/"                              element={<Home />} />
          <Route path="/player/:region/:name/:tag"     element={<Player />} />
          <Route path="/bets"                          element={<Bets />} />
          <Route path="/profile/:userId"               element={<Profile />} />
          <Route path="/profile"                       element={<Profile />} />
          <Route path="/leaderboard"                   element={<Leaderboard />} />
          <Route path="/betonpros"                     element={<BetOnPros />} />
          <Route path="/settings"                      element={<Settings />} />
          <Route path="/admin/ratings"                 element={<AdminRatings />} />
          <Route path="/games"                         element={<Games />} />
          <Route path="/games/coachdiff"               element={<CoachDiff />} />
          <Route path="/games/coachdiff/:gameId"       element={<CoachDiffGame />} />
          <Route path="/lootbox"                       element={<LootBox />} />
          <Route path="/admin/cards"                   element={<AdminCards />} />
          <Route path="/admin/lootboxes" element={<AdminLootboxes />} />
          <Route path="/games/myceo" element={<GameMode />} />
          <Route path="/admin/gm" element={<AdminGm />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}