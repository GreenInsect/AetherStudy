import { useState, useEffect } from 'react'
import { Shield, Search, Trash2, ToggleLeft, ToggleRight, Users, RefreshCw, AlertCircle } from 'lucide-react'
import { useAppStore } from '../store'
import { apiListUsers, apiToggleUserStatus, apiAdminDeleteUser } from '../api'

export default function AdminPage() {
  const { user: currentUser } = useAppStore()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [actionLoading, setActionLoading] = useState(null) // userId of ongoing action
  const [deleteTarget, setDeleteTarget] = useState(null)   // user to confirm delete

  const fetchUsers = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiListUsers()
      setUsers(Array.isArray(data) ? data : [])
    } catch (err) {
      setError('加载用户列表失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchUsers() }, [])

  const filtered = users.filter(u =>
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase())
  )

  const handleToggleStatus = async (u) => {
    setActionLoading(u.id)
    try {
      const updated = await apiToggleUserStatus(u.id, !u.is_active)
      setUsers(prev => prev.map(x => x.id === u.id ? updated : x))
    } catch (err) {
      setError(err.message)
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async (u) => {
    setActionLoading(u.id)
    try {
      await apiAdminDeleteUser(u.id)
      setUsers(prev => prev.filter(x => x.id !== u.id))
      setDeleteTarget(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setActionLoading(null)
    }
  }

  const totalActive = users.filter(u => u.is_active).length

  return (
    <div className="admin-page">
      {/* 页头 */}
      <div className="admin-header">
        <div className="admin-title">
          <Shield size={22} />
          <div>
            <h1>用户管理</h1>
            <p>管理所有注册用户账户</p>
          </div>
        </div>
        <button className="btn-refresh" onClick={fetchUsers} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          刷新
        </button>
      </div>

      {/* 统计行 */}
      <div className="admin-stats-row">
        <div className="admin-stat-card">
          <Users size={18} />
          <div>
            <div className="stat-num">{users.length}</div>
            <div className="stat-lbl">总用户数</div>
          </div>
        </div>
        <div className="admin-stat-card">
          <div className="stat-dot active" />
          <div>
            <div className="stat-num">{totalActive}</div>
            <div className="stat-lbl">活跃用户</div>
          </div>
        </div>
        <div className="admin-stat-card">
          <div className="stat-dot inactive" />
          <div>
            <div className="stat-num">{users.length - totalActive}</div>
            <div className="stat-lbl">已禁用</div>
          </div>
        </div>
      </div>

      {/* 搜索栏 */}
      <div className="admin-search-bar">
        <Search size={16} />
        <input
          className="admin-search-input"
          placeholder="搜索用户名或邮箱..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {error && (
        <div className="auth-error" style={{ marginBottom: 16 }}>
          <AlertCircle size={15} /><span>{error}</span>
        </div>
      )}

      {/* 用户表格 */}
      <div className="admin-table-wrap">
        {loading ? (
          <div className="admin-loading">
            <RefreshCw size={24} className="spin" />
            <span>加载中...</span>
          </div>
        ) : filtered.length === 0 ? (
          <div className="admin-empty">
            <Users size={36} />
            <p>{search ? '未找到匹配用户' : '暂无用户'}</p>
          </div>
        ) : (
          <table className="admin-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>邮箱</th>
                <th>状态</th>
                <th>权限</th>
                <th>注册时间</th>
                <th>上次登录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => {
                const isSelf = u.id === currentUser?.id
                const busy = actionLoading === u.id
                return (
                  <tr key={u.id} className={!u.is_active ? 'row-disabled' : ''}>
                    <td>
                      <div className="user-cell">
                        <div className="user-avatar-sm">{u.username[0].toUpperCase()}</div>
                        <span>{u.username}</span>
                        {isSelf && <span className="self-badge">我</span>}
                      </div>
                    </td>
                    <td className="email-cell">{u.email}</td>
                    <td>
                      <span className={`status-badge ${u.is_active ? 'active' : 'inactive'}`}>
                        {u.is_active ? '正常' : '已禁用'}
                      </span>
                    </td>
                    <td>
                      {u.is_admin
                        ? <span className="admin-badge"><Shield size={12} /> 管理员</span>
                        : <span className="user-role-badge">普通用户</span>
                      }
                    </td>
                    <td className="date-cell">{new Date(u.created_at).toLocaleDateString('zh-CN')}</td>
                    <td className="date-cell">
                      {u.last_login ? new Date(u.last_login).toLocaleString('zh-CN') : '—'}
                    </td>
                    <td>
                      <div className="action-btns">
                        {/* 启用/禁用 */}
                        <button
                          className={`btn-icon-action ${u.is_active ? 'btn-warn' : 'btn-green'}`}
                          title={u.is_active ? '禁用账户' : '启用账户'}
                          disabled={isSelf || busy}
                          onClick={() => handleToggleStatus(u)}
                        >
                          {u.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                        </button>
                        {/* 删除 */}
                        <button
                          className="btn-icon-action btn-red"
                          title="删除用户"
                          disabled={isSelf || busy}
                          onClick={() => setDeleteTarget(u)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <div className="modal-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-icon danger"><Trash2 size={28} /></div>
            <h2>确认删除用户</h2>
            <p>
              即将删除用户 <strong>{deleteTarget.username}</strong>（{deleteTarget.email}）及其所有数据，此操作<strong>不可撤销</strong>。
            </p>
            <div className="modal-actions">
              <button
                className="btn-danger-confirm"
                onClick={() => handleDelete(deleteTarget)}
                disabled={actionLoading === deleteTarget.id}
              >
                {actionLoading === deleteTarget.id ? '删除中...' : '确认删除'}
              </button>
              <button className="btn-cancel" onClick={() => setDeleteTarget(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
