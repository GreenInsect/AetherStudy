import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import { ProtectedRoute, AdminRoute } from './components/ProtectedRoute'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ChatPage from './pages/ChatPage'
import ResourcesPage from './pages/ResourcesPage'
import LearningPathPage from './pages/LearningPathPage'
import ProfilePage from './pages/ProfilePage'
import AssessmentPage from './pages/AssessmentPage'
import AccountPage from './pages/AccountPage'
import AdminPage from './pages/AdminPage'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 公开页面 */}
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* 受保护的应用页面（需登录） */}
        <Route
          path="/app"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/app/chat" replace />} />
          <Route path="chat" element={<ChatPage />} />
          <Route path="resources" element={<ResourcesPage />} />
          <Route path="learning-path" element={<LearningPathPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="assessment" element={<AssessmentPage />} />
          <Route path="account" element={<AccountPage />} />

          {/* 管理员专属页面 */}
          <Route
            path="admin"
            element={
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            }
          />
        </Route>

        {/* 兜底重定向 */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
