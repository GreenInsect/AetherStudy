import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Zap, Eye, EyeOff, UserPlus, AlertCircle, CheckCircle2 } from 'lucide-react'
import { apiRegister } from '../api'
import { useAppStore } from '../store'

function StrengthBar({ password }) {
  const checks = [
    password.length >= 8,
    /[A-Za-z]/.test(password),
    /[0-9]/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ]
  const score = checks.filter(Boolean).length
  const labels = ['', '弱', '中', '强', '极强']
  const colors = ['', '#ef4444', '#f59e0b', '#6366f1', '#10b981']
  if (!password) return null
  return (
    <div className="strength-bar-wrap">
      <div className="strength-segments">
        {[1,2,3,4].map(i => (
          <div
            key={i}
            className="strength-seg"
            style={{ background: i <= score ? colors[score] : '#e2e8f0' }}
          />
        ))}
      </div>
      <span className="strength-label" style={{ color: colors[score] }}>{labels[score]}</span>
    </div>
  )
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const { setAuth } = useAppStore()

  const [form, setForm] = useState({ username: '', email: '', password: '', confirmPassword: '' })
  const [showPwd, setShowPwd] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})

  const update = (field) => (e) => {
    setForm(f => ({ ...f, [field]: e.target.value }))
    setFieldErrors(fe => ({ ...fe, [field]: '' }))
    setError('')
  }

  const validate = () => {
    const errs = {}
    if (!form.username.trim() || form.username.length < 3) errs.username = '用户名至少 3 个字符'
    if (!form.email.includes('@')) errs.email = '请输入有效的邮箱地址'
    if (form.password.length < 8) errs.password = '密码至少 8 位'
    if (!/[A-Za-z]/.test(form.password)) errs.password = '密码需包含字母'
    if (!/[0-9]/.test(form.password)) errs.password = '密码需包含数字'
    if (form.password !== form.confirmPassword) errs.confirmPassword = '两次密码不一致'
    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setError('')
    setLoading(true)
    try {
      const data = await apiRegister(form.username.trim(), form.email.trim(), form.password, form.confirmPassword)
      setAuth(data.access_token, data.user)
      navigate('/app/chat', { replace: true })
    } catch (err) {
      console.error('注册失败:', err)
      setError(err.message || '注册失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  const pwdMatch = form.confirmPassword && form.password === form.confirmPassword

  return (
    <div className="auth-page">
      <div className="auth-bg-deco" />
      <div className="auth-container">
        <div className="auth-logo" onClick={() => navigate('/')}>
          <div className="logo-icon"><Zap size={20} /></div>
          <span>AetherStudy AI</span>
        </div>

        <div className="auth-card">
          <div className="auth-card-header">
            <h1>创建账户</h1>
            <p>开始你的个性化 AI 学习之旅</p>
          </div>

          {error && (
            <div className="auth-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <form className="auth-form" onSubmit={handleSubmit}>
            {/* 用户名 */}
            <div className="form-group">
              <label>用户名</label>
              <input
                className={`auth-input ${fieldErrors.username ? 'auth-input--error' : ''}`}
                type="text"
                placeholder="3-32 个字符，支持中文"
                value={form.username}
                onChange={update('username')}
                autoFocus
                autoComplete="username"
              />
              {fieldErrors.username && <p className="field-error">{fieldErrors.username}</p>}
            </div>

            {/* 邮箱 */}
            <div className="form-group">
              <label>邮箱</label>
              <input
                className={`auth-input ${fieldErrors.email ? 'auth-input--error' : ''}`}
                type="email"
                placeholder="your@email.com"
                value={form.email}
                onChange={update('email')}
                autoComplete="email"
              />
              {fieldErrors.email && <p className="field-error">{fieldErrors.email}</p>}
            </div>

            {/* 密码 */}
            <div className="form-group">
              <label>密码</label>
              <div className="pwd-input-wrap">
                <input
                  className={`auth-input ${fieldErrors.password ? 'auth-input--error' : ''}`}
                  type={showPwd ? 'text' : 'password'}
                  placeholder="至少 8 位，含字母和数字"
                  value={form.password}
                  onChange={update('password')}
                  autoComplete="new-password"
                />
                <button type="button" className="pwd-toggle" onClick={() => setShowPwd(v => !v)}>
                  {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <StrengthBar password={form.password} />
              {fieldErrors.password && <p className="field-error">{fieldErrors.password}</p>}
            </div>

            {/* 确认密码 */}
            <div className="form-group">
              <label>确认密码</label>
              <div className="pwd-input-wrap">
                <input
                  className={`auth-input ${fieldErrors.confirmPassword ? 'auth-input--error' : ''}`}
                  type={showConfirm ? 'text' : 'password'}
                  placeholder="再次输入密码"
                  value={form.confirmPassword}
                  onChange={update('confirmPassword')}
                  autoComplete="new-password"
                />
                <button type="button" className="pwd-toggle" onClick={() => setShowConfirm(v => !v)}>
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
                {pwdMatch && (
                  <CheckCircle2 size={16} className="pwd-match-icon" />
                )}
              </div>
              {fieldErrors.confirmPassword && <p className="field-error">{fieldErrors.confirmPassword}</p>}
            </div>

            <button
              type="submit"
              className="btn-auth-submit"
              disabled={loading}
            >
              {loading ? (
                <span className="auth-loading-dots">注册中<span>.</span><span>.</span><span>.</span></span>
              ) : (
                <><UserPlus size={18} /> 创建账户</>
              )}
            </button>
          </form>

          <div className="auth-divider"><span>已有账户？</span></div>
          <Link to="/login" className="btn-auth-secondary">前往登录</Link>
        </div>

        <p className="auth-footer-tip"><Link to="/">← 返回首页</Link></p>
      </div>
    </div>
  )
}
