import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { PlayerProvider } from './player/PlayerContext'
import { ToastProvider } from './components/Toast'
import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import './App.css'

const Home = lazy(() => import('./pages/Home').then((m) => ({ default: m.Home })))
const Music = lazy(() => import('./pages/Music').then((m) => ({ default: m.Music })))
const MusicAll = lazy(() => import('./pages/MusicAll').then((m) => ({ default: m.MusicAll })))
const Video = lazy(() => import('./pages/Video').then((m) => ({ default: m.Video })))
const VideoAll = lazy(() => import('./pages/VideoAll').then((m) => ({ default: m.VideoAll })))
const Photos = lazy(() => import('./pages/Photos').then((m) => ({ default: m.Photos })))
const Community = lazy(() => import('./pages/Community').then((m) => ({ default: m.Community })))
const Login = lazy(() => import('./pages/Login').then((m) => ({ default: m.Login })))
const Register = lazy(() => import('./pages/Register').then((m) => ({ default: m.Register })))
const Cms = lazy(() => import('./pages/Cms').then((m) => ({ default: m.Cms })))
const NotFound = lazy(() => import('./pages/NotFound').then((m) => ({ default: m.NotFound })))

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
      <PlayerProvider>
      <Suspense fallback={<div className="route-loading" role="status">Đang tải…</div>}>
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
          <Route path="*" element={<NotFound />} />
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
      </Suspense>
      </PlayerProvider>
      </ToastProvider>
    </BrowserRouter>
  )
}
