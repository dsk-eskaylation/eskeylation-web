import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import { Home } from './pages/Home'
import { Music } from './pages/Music'
import { MusicAll } from './pages/MusicAll'
import { Feed } from './pages/Feed'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { Cms } from './pages/Cms'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Trang public — có PillNav */}
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="music" element={<Music />} />
          <Route path="music/all" element={<MusicAll />} />
          <Route
            path="photos"
            element={<Feed type="photos" emptyTitle="Hiện tại chưa có bài viết nào TT.  " />}
          />
          <Route
            path="community"
            element={<Feed type="community" emptyTitle="Hiện tại chưa có bài viết nào TT.  " />}
          />
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
    </BrowserRouter>
  )
}
