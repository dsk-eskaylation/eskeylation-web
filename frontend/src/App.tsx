import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Home } from './pages/Home'
import { Music } from './pages/Music'
import { Feed } from './pages/Feed'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="music" element={<Music />} />
          <Route
            path="photos"
            element={<Feed type="photos" emptyTitle="Chưa có ảnh" />}
          />
          <Route
            path="community"
            element={<Feed type="community" emptyTitle="Chưa có bài viết" />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
