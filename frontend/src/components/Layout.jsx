import { useState, useRef, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  MessageSquare, BookOpen, Map, User, BarChart2,
  ChevronLeft, ChevronRight, Zap, Menu,
  LogOut, Settings, Shield, ChevronDown
} from 'lucide-react'
import { useAppStore } from '../store'
import { apiLogout } from '../api'

const NAV_ITEMS = [
  { to: '/app/chat',          icon: MessageSquare, label: '智能对话' },
  { to: '/app/resources',     icon: BookOpen,      label: '学习资源' },
  { to: '/app/learning-path', icon: Map,           label: '学习路径' },
  { to: '/app/assessment',    icon: BarChart2,      label: '学习评估' },
  { to: '/app/profile',       icon: User,          label: '我的画像' },
]

export default function Layout() {
  const { sidebarOpen, toggleSidebar, profile, profileCompleteness, user, clearAuth } = useAppStore()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [loggingOut, setLoggingOut] = useState(false)
  const menuRef = useRef(null)

  // 点击外部关闭用户菜单
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleLogout = async () => {
    setLoggingOut(true)
    try {
      await apiLogout()
    } finally {
      clearAuth()
      navigate('/login', { replace: true })
    }
  }

  const avatarChar = user?.username?.[0]?.toUpperCase() || 'U'

  return (
    <div className="layout-root">
      {/* ===== 侧边栏 ===== */}
      <aside className={`sidebar ${sidebarOpen ? 'sidebar--open' : 'sidebar--collapsed'}`}>
        {/* Logo */}
        <div className="sidebar-header">
          <div className="sidebar-logo" onClick={() => navigate('/')}>
            <div className="logo-icon"><Zap size={20} /></div>
            {sidebarOpen && <span className="logo-text">AetherStudy AI</span>}
          </div>
          <button className="sidebar-toggle" onClick={toggleSidebar}>
            {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        </div>

        {/* 导航菜单 */}
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-item ${isActive ? 'nav-item--active' : ''}`}
            >
              <Icon size={20} className="nav-icon" />
              {sidebarOpen && <span className="nav-label">{label}</span>}
            </NavLink>
          ))}

          {/* 管理员入口 */}
          {user?.is_admin && (
            <NavLink
              to="/app/admin"
              className={({ isActive }) => `nav-item nav-item--admin ${isActive ? 'nav-item--active' : ''}`}
            >
              <Shield size={20} className="nav-icon" />
              {sidebarOpen && <span className="nav-label">用户管理</span>}
            </NavLink>
          )}
        </nav>

        {/* 画像完整度 */}
        {sidebarOpen && (
          <div className="profile-progress-card">
            <div className="profile-progress-header">
              <User size={14} />
              <span>画像完整度</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${Math.round(profileCompleteness * 100)}%` }} />
            </div>
            <span className="progress-label">{Math.round(profileCompleteness * 100)}% 已完成</span>
            {profileCompleteness < 1 && (
              <button className="btn-complete-profile" onClick={() => navigate('/app/chat')}>
                完善画像 →
              </button>
            )}
          </div>
        )}
      </aside>

      {/* ===== 主内容区 ===== */}
      <div className="main-wrapper">
        {/* 顶部导航 */}
        <header className="topbar">
          <button className="topbar-menu-btn" onClick={toggleSidebar}>
            <Menu size={20} />
          </button>

          <div className="topbar-right">
            {/* 用户头像 + 下拉菜单 */}
            <div className="user-menu-wrap" ref={menuRef}>
              <button
                className="topbar-user-btn"
                onClick={() => setUserMenuOpen(v => !v)}
              >
                {/* user?.username?.[0]?.toUpperCase() || 'U' */}
                <div className="topbar-avatar">{avatarChar}</div>
                {sidebarOpen && (
                  <>
                    <span className="topbar-username">{user?.username}</span>
                    <ChevronDown size={14} className={`topbar-chevron ${userMenuOpen ? 'rotated' : ''}`} />
                  </>
                )}
              </button>

              {userMenuOpen && (
                <div className="user-dropdown">
                  {/* 用户信息头 */}
                  <div className="dropdown-user-info">
                    <div className="dropdown-avatar">{avatarChar}</div>
                    <div>
                      <div className="dropdown-username">{user?.username}</div>
                      <div className="dropdown-email">{user?.email}</div>
                    </div>
                  </div>

                  <div className="dropdown-divider" />

                  <button
                    className="dropdown-item"
                    onClick={() => { navigate('/app/account'); setUserMenuOpen(false) }}
                  >
                    <Settings size={15} />
                    账户设置
                  </button>

                  {user?.is_admin && (
                    <button
                      className="dropdown-item"
                      onClick={() => { navigate('/app/admin'); setUserMenuOpen(false) }}
                    >
                      <Shield size={15} />
                      用户管理
                    </button>
                  )}

                  <div className="dropdown-divider" />

                  <button
                    className="dropdown-item dropdown-item--danger"
                    onClick={handleLogout}
                    disabled={loggingOut}
                  >
                    <LogOut size={15} />
                    {loggingOut ? '退出中...' : '退出登录'}
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* 页面内容 */}
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
