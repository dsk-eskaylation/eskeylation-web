import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { PlayerProvider } from './player/PlayerContext'
import { ToastProvider } from './components/Toast'
import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import { Home } from './pages/Home'
import { Music } from './pages/Music'
import { MusicAll } from './pages/MusicAll'
import { Video } from './pages/Video'
import { VideoAll } from './pages/VideoAll'
import { Photos } from './pages/Photos'
import { Community } from './pages/Community'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { Cms } from './pages/Cms'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
      <PlayerProvider>
      <Routes>
        {/* Trang public — có PillNav */}
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="music" element={<Music />} />
          <Route path="music/all" element={<MusicAll />} />
          <Route path="video" element={<Video />} />
          <Route path="video/all" element={<VideoAll />} />
          <Route path="photos" element={<Photos />} />
          <Route path="community" element={<Community />} />
        </Route>

        {/* Khu vực quản trị — không dùng PillNav public */}
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route
          path="cms"
          element={
            <RequireAuth>
              <Cms />
            </RequireAuth>
          }
        />
      </Routes>
      </PlayerProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
