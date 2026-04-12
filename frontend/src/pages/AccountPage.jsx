import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings, Key, Trash2, User, Eye, EyeOff, AlertCircle, CheckCircle2, Shield } from 'lucide-react'
import { useAppStore } from '../store'
import { apiUpdateMe, apiChangePassword, apiDeleteMe, apiLogout } from '../api'

export default function AccountPage() {
  const navigate = useNavigate()
  const { user, setAuth, clearAuth } = useAppStore()

  // ── 基本信息编辑 ──────────────────────────────
  const [infoForm, setInfoForm] = useState({ username: user?.username || '', email: user?.email || '' })
  const [infoLoading, setInfoLoading] = useState(false)
  const [infoMsg, setInfoMsg] = useState(null) // { type: 'success'|'error', text }

  const handleUpdateInfo = async (e) => {
    e.preventDefault()
    setInfoLoading(true)
    setInfoMsg(null)
    try {
      const updated = await apiUpdateMe({
        username: infoForm.username !== user.username ? infoForm.username : undefined,
        email: infoForm.email !== user.email ? infoForm.email : undefined,
      })
      // 更新 store 中的 user 对象
      setAuth(localStorage.getItem('edumind_token'), updated)
      setInfoMsg({ type: 'success', text: '信息更新成功' })
    } catch (err) {
      setInfoMsg({ type: 'error', text: err.message })
    } finally {
      setInfoLoading(false)
    }
  }

  // ── 修改密码 ──────────────────────────────────
  const [pwdForm, setPwdForm] = useState({ old: '', new: '', confirm: '' })
  const [showPwd, setShowPwd] = useState({ old: false, new: false, confirm: false })
  const [pwdLoading, setPwdLoading] = useState(false)
  const [pwdMsg, setPwdMsg] = useState(null)

  const handleChangePwd = async (e) => {
    e.preventDefault()
    if (pwdForm.new !== pwdForm.confirm) {
      setPwdMsg({ type: 'error', text: '两次新密码不一致' })
      return
    }
    setPwdLoading(true)
    setPwdMsg(null)
    try {
      await apiChangePassword(pwdForm.old, pwdForm.new, pwdForm.confirm)
      setPwdMsg({ type: 'success', text: '密码修改成功，请重新登录' })
      setPwdForm({ old: '', new: '', confirm: '' })
      setTimeout(async () => {
        await apiLogout()
        clearAuth()
        navigate('/login')
      }, 1500)
    } catch (err) {
      setPwdMsg({ type: 'error', text: err.message })
    } finally {
      setPwdLoading(false)
    }
  }

  // ── 注销账户 ──────────────────────────────────
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const handleDeleteAccount = async () => {
    if (deleteConfirm !== user?.username) return
    setDeleteLoading(true)
    try {
      await apiDeleteMe()
      clearAuth()
      navigate('/', { replace: true })
    } catch (err) {
      setDeleteLoading(false)
    }
  }

  const togglePwd = (field) => setShowPwd(p => ({ ...p, [field]: !p[field] }))

  return (
    <div className="account-page">
      <div className="account-header">
        <Settings size={22} />
        <div>
          <h1>账户设置</h1>
          <p>管理你的个人信息、密码和账户安全</p>
        </div>
      </div>

      <div className="account-sections">

        {/* ── 基本信息 ── */}
        <div className="account-card">
          <div className="account-card-title">
            <User size={18} />
            <span>基本信息</span>
          </div>

          <form className="account-form" onSubmit={handleUpdateInfo}>
            <div className="form-row">
              <div className="form-group">
                <label>用户名</label>
                <input
                  className="auth-input"
                  value={infoForm.username}
                  onChange={e => setInfoForm(f => ({ ...f, username: e.target.value }))}
                  placeholder="用户名"
                />
              </div>
              <div className="form-group">
                <label>邮箱</label>
                <input
                  className="auth-input"
                  type="email"
                  value={infoForm.email}
                  onChange={e => setInfoForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="邮箱"
                />
              </div>
            </div>

            {infoMsg && (
              <div className={`account-msg account-msg--${infoMsg.type}`}>
                {infoMsg.type === 'success' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
                {infoMsg.text}
              </div>
            )}

            <button
              type="submit"
              className="btn-account-save"
              disabled={infoLoading}
            >
              {infoLoading ? '保存中...' : '保存更改'}
            </button>
          </form>

          {/* 账户元信息 */}
          <div className="account-meta">
            <div className="meta-item">
              <span className="meta-label">账户 ID</span>
              <span className="meta-value meta-mono">{user?.id?.slice(0, 16)}...</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">注册时间</span>
              <span className="meta-value">{user?.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN') : '—'}</span>
            </div>
            <div className="meta-item">
              <span className="meta-label">上次登录</span>
              <span className="meta-value">{user?.last_login ? new Date(user.last_login).toLocaleString('zh-CN') : '首次登录'}</span>
            </div>
            {user?.is_admin && (
              <div className="meta-item">
                <span className="meta-label">权限</span>
                <span className="admin-badge"><Shield size={12} /> 管理员</span>
              </div>
            )}
          </div>
        </div>

        {/* ── 修改密码 ── */}
        <div className="account-card">
          <div className="account-card-title">
            <Key size={18} />
            <span>修改密码</span>
          </div>

          <form className="account-form" onSubmit={handleChangePwd}>
            {[
              { field: 'old', label: '当前密码', placeholder: '输入当前密码' },
              { field: 'new', label: '新密码', placeholder: '至少 8 位，含字母和数字' },
              { field: 'confirm', label: '确认新密码', placeholder: '再次输入新密码' },
            ].map(({ field, label, placeholder }) => (
              <div className="form-group" key={field}>
                <label>{label}</label>
                <div className="pwd-input-wrap">
                  <input
                    className="auth-input"
                    type={showPwd[field] ? 'text' : 'password'}
                    placeholder={placeholder}
                    value={pwdForm[field]}
                    onChange={e => setPwdForm(f => ({ ...f, [field]: e.target.value }))}
                    autoComplete={field === 'old' ? 'current-password' : 'new-password'}
                  />
                  <button type="button" className="pwd-toggle" onClick={() => togglePwd(field)}>
                    {showPwd[field] ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>
            ))}

            {pwdMsg && (
              <div className={`account-msg account-msg--${pwdMsg.type}`}>
                {pwdMsg.type === 'success' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
                {pwdMsg.text}
              </div>
            )}

            <button
              type="submit"
              className="btn-account-save"
              disabled={pwdLoading || !pwdForm.old || !pwdForm.new || !pwdForm.confirm}
            >
              {pwdLoading ? '修改中...' : '确认修改密码'}
            </button>
          </form>
        </div>

        {/* ── 注销账户 ── */}
        <div className="account-card account-card--danger">
          <div className="account-card-title danger">
            <Trash2 size={18} />
            <span>注销账户</span>
          </div>

          <p className="danger-desc">
            注销后，你的账户、学习画像、资源记录等所有数据将被<strong>永久删除</strong>，无法恢复。请谨慎操作。
          </p>

          {!showDeleteConfirm ? (
            <button
              className="btn-danger-trigger"
              onClick={() => setShowDeleteConfirm(true)}
            >
              我要注销账户
            </button>
          ) : (
            <div className="delete-confirm-area">
              <p className="delete-confirm-hint">
                请输入你的用户名 <strong>{user?.username}</strong> 以确认注销：
              </p>
              <input
                className="auth-input"
                placeholder={`输入 "${user?.username}" 确认`}
                value={deleteConfirm}
                onChange={e => setDeleteConfirm(e.target.value)}
              />
              <div className="delete-confirm-actions">
                <button
                  className="btn-danger-confirm"
                  disabled={deleteConfirm !== user?.username || deleteLoading}
                  onClick={handleDeleteAccount}
                >
                  {deleteLoading ? '注销中...' : '确认永久注销'}
                </button>
                <button
                  className="btn-cancel"
                  onClick={() => { setShowDeleteConfirm(false); setDeleteConfirm('') }}
                >
                  取消
                </button>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
