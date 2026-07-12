import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings, Key, Trash2, User, Eye, EyeOff, AlertCircle, CheckCircle2, Shield, Cpu } from 'lucide-react'
import { useAppStore } from '../store'
import {
  apiUpdateMe,
  apiChangePassword,
  apiDeleteMe,
  apiLogout,
  apiGetLLMSettings,
  apiUpdateLLMSettings,
} from '../api'

const DEFAULT_LLM_FORM = {
  provider: 'OpenAI',
  model: 'gpt-5.4',
  review_model: 'gpt-5.5',
  base_url: 'https://api.dstopology.com/v1',
  api_key: '',
  wire_api: 'responses',
  reasoning_effort: 'xhigh',
  disable_response_storage: true,
  network_access: 'enabled',
  context_window: 400000,
  auto_compact_token_limit: 360000,
}

export default function AccountPage() {
  const navigate = useNavigate()
  const { user, setAuth, clearAuth } = useAppStore()

  const [llmForm, setLlmForm] = useState(DEFAULT_LLM_FORM)
  const [llmHasKey, setLlmHasKey] = useState(false)
  const [llmLoading, setLlmLoading] = useState(false)
  const [llmMsg, setLlmMsg] = useState(null)

  useEffect(() => {
    let mounted = true
    apiGetLLMSettings()
      .then(settings => {
        if (!mounted) return
        setLlmHasKey(Boolean(settings.has_api_key))
        setLlmForm({
          provider: settings.provider || DEFAULT_LLM_FORM.provider,
          model: settings.model || DEFAULT_LLM_FORM.model,
          review_model: settings.review_model || DEFAULT_LLM_FORM.review_model,
          base_url: settings.base_url || DEFAULT_LLM_FORM.base_url,
          api_key: '',
          wire_api: settings.wire_api || DEFAULT_LLM_FORM.wire_api,
          reasoning_effort: settings.reasoning_effort || DEFAULT_LLM_FORM.reasoning_effort,
          disable_response_storage: Boolean(settings.disable_response_storage),
          network_access: settings.network_access || DEFAULT_LLM_FORM.network_access,
          context_window: settings.context_window || DEFAULT_LLM_FORM.context_window,
          auto_compact_token_limit: settings.auto_compact_token_limit || DEFAULT_LLM_FORM.auto_compact_token_limit,
        })
      })
      .catch(err => {
        if (mounted) setLlmMsg({ type: 'error', text: err.message })
      })
    return () => { mounted = false }
  }, [])

  const handleUpdateLLM = async (e) => {
    e.preventDefault()
    setLlmLoading(true)
    setLlmMsg(null)
    try {
      const payload = {
        ...llmForm,
        context_window: Number(llmForm.context_window),
        auto_compact_token_limit: Number(llmForm.auto_compact_token_limit),
      }
      if (!payload.api_key.trim()) delete payload.api_key
      const updated = await apiUpdateLLMSettings(payload)
      setLlmHasKey(Boolean(updated.has_api_key))
      setLlmForm(f => ({ ...f, api_key: '' }))
      setLlmMsg({ type: 'success', text: '模型配置已保存' })
    } catch (err) {
      setLlmMsg({ type: 'error', text: err.message })
    } finally {
      setLlmLoading(false)
    }
  }

  const applyCodexPreset = () => {
    setLlmForm(f => ({
      ...f,
      provider: 'OpenAI',
      model: 'gpt-5.4',
      review_model: 'gpt-5.5',
      base_url: 'https://api.dstopology.com/v1',
      wire_api: 'responses',
      reasoning_effort: 'xhigh',
      disable_response_storage: true,
      network_access: 'enabled',
      context_window: 400000,
      auto_compact_token_limit: 360000,
    }))
  }

  // 基本信息编辑
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
      setAuth(localStorage.getItem('AetherStudy_token'), updated)
      setInfoMsg({ type: 'success', text: '信息更新成功' })
    } catch (err) {
      setInfoMsg({ type: 'error', text: err.message })
    } finally {
      setInfoLoading(false)
    }
  }

  //  修改密码
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

  // 注销账户
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

        {/* ── 模型配置 ── */}
        <div className="account-card">
          <div className="account-card-title">
            <Cpu size={18} />
            <span>模型配置</span>
          </div>

          <form className="account-form" onSubmit={handleUpdateLLM}>
            <div className="llm-status-row">
              <span className={`llm-key-badge ${llmHasKey ? 'ok' : 'warn'}`}>
                {llmHasKey ? '已配置 API Key' : '未配置 API Key'}
              </span>
              <button type="button" className="btn-cancel" onClick={applyCodexPreset}>
                使用 Codex 配置预设
              </button>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Provider</label>
                <input
                  className="auth-input"
                  value={llmForm.provider}
                  onChange={e => setLlmForm(f => ({ ...f, provider: e.target.value }))}
                  placeholder="OpenAI"
                />
              </div>
              <div className="form-group">
                <label>Wire API</label>
                <select
                  className="auth-input"
                  value={llmForm.wire_api}
                  onChange={e => setLlmForm(f => ({ ...f, wire_api: e.target.value }))}
                >
                  <option value="responses">Responses API</option>
                  <option value="chat_completions">Chat Completions</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label>BASE_URL</label>
              <input
                className="auth-input"
                value={llmForm.base_url}
                onChange={e => setLlmForm(f => ({ ...f, base_url: e.target.value }))}
                placeholder="https://api.dstopology.com/v1"
              />
            </div>

            <div className="form-group">
              <label>OPENAI_API_KEY</label>
              <div className="pwd-input-wrap">
                <input
                  className="auth-input"
                  type={showPwd.llm ? 'text' : 'password'}
                  value={llmForm.api_key}
                  onChange={e => setLlmForm(f => ({ ...f, api_key: e.target.value }))}
                  placeholder={llmHasKey ? '留空则保留已保存的 Key' : '输入 sk-...'}
                  autoComplete="off"
                />
                <button type="button" className="pwd-toggle" onClick={() => togglePwd('llm')}>
                  {showPwd.llm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>主模型 model</label>
                <input
                  className="auth-input"
                  value={llmForm.model}
                  onChange={e => setLlmForm(f => ({ ...f, model: e.target.value }))}
                  placeholder="gpt-5.4"
                />
              </div>
              <div className="form-group">
                <label>结构化/评审模型 review_model</label>
                <input
                  className="auth-input"
                  value={llmForm.review_model}
                  onChange={e => setLlmForm(f => ({ ...f, review_model: e.target.value }))}
                  placeholder="gpt-5.5"
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Reasoning Effort</label>
                <input
                  className="auth-input"
                  value={llmForm.reasoning_effort}
                  onChange={e => setLlmForm(f => ({ ...f, reasoning_effort: e.target.value }))}
                  placeholder="xhigh"
                />
              </div>
              <div className="form-group">
                <label>Network Access</label>
                <select
                  className="auth-input"
                  value={llmForm.network_access}
                  onChange={e => setLlmForm(f => ({ ...f, network_access: e.target.value }))}
                >
                  <option value="enabled">enabled</option>
                  <option value="disabled">disabled</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Context Window</label>
                <input
                  className="auth-input"
                  type="number"
                  min="1000"
                  value={llmForm.context_window}
                  onChange={e => setLlmForm(f => ({ ...f, context_window: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label>Auto Compact Token Limit</label>
                <input
                  className="auth-input"
                  type="number"
                  min="1000"
                  value={llmForm.auto_compact_token_limit}
                  onChange={e => setLlmForm(f => ({ ...f, auto_compact_token_limit: e.target.value }))}
                />
              </div>
            </div>

            <label className="llm-check-row">
              <input
                type="checkbox"
                checked={llmForm.disable_response_storage}
                onChange={e => setLlmForm(f => ({ ...f, disable_response_storage: e.target.checked }))}
              />
              <span>禁用响应存储 store=false</span>
            </label>

            {llmMsg && (
              <div className={`account-msg account-msg--${llmMsg.type}`}>
                {llmMsg.type === 'success' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
                {llmMsg.text}
              </div>
            )}

            <button
              type="submit"
              className="btn-account-save"
              disabled={llmLoading || !llmForm.model || !llmForm.base_url}
            >
              {llmLoading ? '保存中...' : '保存模型配置'}
            </button>
          </form>
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
