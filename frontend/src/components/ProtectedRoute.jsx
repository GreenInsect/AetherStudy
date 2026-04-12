import { Navigate, useLocation } from 'react-router-dom'
import { useAppStore } from '../store'

/**
 * 路由守卫：未登录时重定向到 /login，并记录原目标路径
 * 用法：<Route element={<ProtectedRoute />}> ... </Route>
 */
export function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAppStore()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  return children
}

/**
 * 管理员路由守卫：非管理员重定向到 /app/chat
 */
export function AdminRoute({ children }) {
  const { isAuthenticated, user } = useAppStore()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  if (!user?.is_admin) {
    return <Navigate to="/app/chat" replace />
  }
  return children
}
