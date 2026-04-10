import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import cyberpunkTheme from './theme'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import Sandboxes from './pages/Sandboxes'
import Templates from './pages/Templates'
import Terminal from './pages/Terminal'

export default function App() {
  return (
    <ConfigProvider theme={cyberpunkTheme} locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sandboxes" element={<Sandboxes />} />
            <Route path="/templates" element={<Templates />} />
          </Route>
          <Route path="/terminal/:sandboxId" element={<Terminal />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}
