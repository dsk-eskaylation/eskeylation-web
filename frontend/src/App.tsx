import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Home } from './pages/Home'
import { ContentList } from './pages/ContentList'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route
            path="music"
            element={<ContentList type="music" title="Nghe nhạc" />}
          />
          <Route
            path="photos"
            element={<ContentList type="photos" title="Ảnh" />}
          />
          <Route
            path="community"
            element={<ContentList type="community" title="Cộng đồng" />}
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
