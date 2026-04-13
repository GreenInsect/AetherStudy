import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Zap, Eye, EyeOff, LogIn, AlertCircle } from 'lucide-react'
import { apiLogin, getMyProfile, apiListSessions } from '../api'
import { useAppStore } from '../store'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setAuth, setProfile, setSessions } = useAppStore()

  const [identifier, setIdentifier] = useState('')  // 用户名或邮箱
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!identifier.trim() || !password) return
    setError('')
    setLoading(true)
    try {
      const data = await apiLogin(identifier.trim(), password)
      setAuth(data.access_token, data.user)

      try {
        const profileData = await getMyProfile()
        if (profileData) {
          setProfile(profileData.profile)
          console.log('画像数据加载成功')
          console.log('登录后获取画像数据:', profileData)  // 调试日志          
        }else {
          console.warn('画像数据加载失败，返回数据不正确:', profileData)
          setProfile(null)  // 设置为 null 或默认值以避免后续错误
        }
        const data = await apiListSessions()
        if(data && Array.isArray(data)){
          setSessions(Array.isArray(data) ? data : [])        
          console.log('[*] klog: 登录后加载会话列表成功 data: ', data)
        } else {
          console.warn('[*] klog: 登录后加载会话列表失败，返回数据格式不正确: ', data)
          setSessions([])  // 设置为空数组以避免后续错误
        }
      } catch (profileErr) {
        // 画像获取失败通常不应阻止登录成功，只需记录错误
        console.error('登录后拉取画像/会话列表失败:', profileErr)
      }


      navigate('/app/chat', { replace: true })
    } catch (err) {
      setError(err.message || '登录失败，请检查账号和密码')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      {/* 背景装饰 */}
      <div className="auth-bg-deco" />

      <div className="auth-container">
        {/* Logo */}
        <div className="auth-logo" onClick={() => navigate('/')}>
          <div className="logo-icon"><Zap size={20} /></div>
          <span>AetherStudy AI</span>
        </div>

        <div className="auth-card">
          <div className="auth-card-header">
            <h1>欢迎回来</h1>
            <p>登录你的 AetherStudy AI 账户</p>
          </div>

          {error && (
            <div className="auth-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label>用户名或邮箱</label>
              <input
                className="auth-input"
                type="text"
                placeholder="输入用户名或邮箱"
                value={identifier}
                onChange={e => setIdentifier(e.target.value)}
                autoFocus
                autoComplete="username"
              />
            </div>

            <div className="form-group">
              <div className="label-row">
                <label>密码</label>
              </div>
              <div className="pwd-input-wrap">
                <input
                  className="auth-input"
                  type={showPwd ? 'text' : 'password'}
                  placeholder="输入密码"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button type="button" className="pwd-toggle" onClick={() => setShowPwd(v => !v)}>
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn-auth-submit"
              disabled={loading || !identifier.trim() || !password}
            >
              {loading ? (
                <span className="auth-loading-dots">登录中<span>.</span><span>.</span><span>.</span></span>
              ) : (
                <><LogIn size={18} /> 登录</>
              )}
            </button>
          </form>

          <div className="auth-divider"><span>没有账户？</span></div>

          <Link to="/register" className="btn-auth-secondary">
            创建新账户
          </Link>
        </div>

        <p className="auth-footer-tip">
          <Link to="/">← 返回首页</Link>
        </p>
      </div>
    </div>
  )
}
