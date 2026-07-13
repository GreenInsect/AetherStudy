import { useState, useEffect } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Database,
  FileText,
  FolderOpen,
  RefreshCw,
  Search,
  Shield,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Upload,
  Users,
} from 'lucide-react'
import { useAppStore } from '../store'
import {
  apiAdminDeleteUser,
  apiDeleteAdminKnowledge,
  apiListAdminKnowledge,
  apiListUsers,
  apiReindexAdminKnowledge,
  apiToggleUserStatus,
  apiUploadAdminKnowledge,
} from '../api'

export default function AdminPage() {
  const { user: currentUser } = useAppStore()
  const [activeTab, setActiveTab] = useState('knowledge')
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [actionLoading, setActionLoading] = useState(null) // userId of ongoing action
  const [deleteTarget, setDeleteTarget] = useState(null)   // user to confirm delete
  const [knowledge, setKnowledge] = useState({ root: '', document_count: 0, summary: {}, documents: [] })
  const [knowledgeLoading, setKnowledgeLoading] = useState(true)
  const [knowledgeAction, setKnowledgeAction] = useState(null)
  const [knowledgeSubject, setKnowledgeSubject] = useState('机器学习')
  const [knowledgeFiles, setKnowledgeFiles] = useState([])
  const [knowledgeResult, setKnowledgeResult] = useState(null)

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

  const fetchKnowledge = async () => {
    setKnowledgeLoading(true)
    setError('')
    try {
      const data = await apiListAdminKnowledge()
      setKnowledge(data || { root: '', document_count: 0, summary: {}, documents: [] })
    } catch (err) {
      setError(err.message || '加载管理员知识库失败')
    } finally {
      setKnowledgeLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
    fetchKnowledge()
  }, [])

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

  const handleKnowledgeUpload = async () => {
    if (!knowledgeSubject.trim() || knowledgeFiles.length === 0) return
    setKnowledgeAction('upload')
    setError('')
    setKnowledgeResult(null)
    try {
      const result = await apiUploadAdminKnowledge(knowledgeSubject.trim(), knowledgeFiles)
      setKnowledgeResult(result)
      setKnowledgeFiles([])
      await fetchKnowledge()
    } catch (err) {
      setError(err.message || '上传管理员知识库资料失败')
    } finally {
      setKnowledgeAction(null)
    }
  }

  const handleKnowledgeReindex = async (force = false) => {
    setKnowledgeAction(force ? 'force-reindex' : 'reindex')
    setError('')
    setKnowledgeResult(null)
    try {
      const result = await apiReindexAdminKnowledge(force)
      setKnowledgeResult(result)
      await fetchKnowledge()
    } catch (err) {
      setError(err.message || '重建管理员知识库索引失败')
    } finally {
      setKnowledgeAction(null)
    }
  }

  const handleKnowledgeDelete = async (doc) => {
    if (!window.confirm(`删除管理员知识库资料「${doc.filename}」？删除后将不再参与 RAG。`)) return
    setKnowledgeAction(`delete-${doc.id}`)
    setError('')
    try {
      await apiDeleteAdminKnowledge(doc.id)
      await fetchKnowledge()
    } catch (err) {
      setError(err.message || '删除管理员知识库资料失败')
    } finally {
      setKnowledgeAction(null)
    }
  }

  const totalActive = users.filter(u => u.is_active).length
  const knowledgeDocs = knowledge.documents || []
  const knowledgeSubjects = Object.entries(knowledge.summary || {})
  const knowledgeResultCounts = knowledgeResult?.status_counts || {}
  const knowledgeFailedCount = knowledgeResultCounts.failed || 0
  const knowledgeSuccessCount = (knowledgeResult?.results || []).filter(item => item.status !== 'failed').length

  return (
    <div className="admin-page">
      {/* 页头 */}
      <div className="admin-header">
        <div className="admin-title">
          <Shield size={22} />
          <div>
            <h1>管理员控制台</h1>
            <p>管理用户账户与服务器端持久知识库</p>
          </div>
        </div>
        <button
          className="btn-refresh"
          onClick={activeTab === 'users' ? fetchUsers : fetchKnowledge}
          disabled={loading || knowledgeLoading}
        >
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          刷新
        </button>
      </div>

      <div className="admin-tabs">
        <button
          className={`admin-tab ${activeTab === 'knowledge' ? 'admin-tab--active' : ''}`}
          onClick={() => setActiveTab('knowledge')}
        >
          <Database size={15} />
          持久知识库
        </button>
        <button
          className={`admin-tab ${activeTab === 'users' ? 'admin-tab--active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <Users size={15} />
          用户管理
        </button>
      </div>

      {error && (
        <div className="auth-error" style={{ marginBottom: 16 }}>
          <AlertCircle size={15} /><span>{error}</span>
        </div>
      )}

      {activeTab === 'knowledge' && (
        <>
          <div className="admin-stats-row">
            <div className="admin-stat-card">
              <Database size={18} />
              <div>
                <div className="stat-num">{knowledge.document_count || 0}</div>
                <div className="stat-lbl">持久资料数</div>
              </div>
            </div>
            <div className="admin-stat-card">
              <FolderOpen size={18} />
              <div>
                <div className="stat-num">{knowledgeSubjects.length}</div>
                <div className="stat-lbl">学科目录数</div>
              </div>
            </div>
            <div className="admin-stat-card admin-stat-card--wide">
              <FileText size={18} />
              <div>
                <div className="stat-num admin-root-path">{knowledge.root || 'backend/storage/admin_knowledge'}</div>
                <div className="stat-lbl">服务器知识库目录</div>
              </div>
            </div>
          </div>

          <section className="admin-knowledge-panel">
            <div className="admin-knowledge-form">
              <div className="form-field">
                <label>学科目录名</label>
                <input
                  className="form-input"
                  value={knowledgeSubject}
                  onChange={e => setKnowledgeSubject(e.target.value)}
                  placeholder="例如：机器学习、深度学习、概率论"
                />
              </div>
              <div className="form-field">
                <label>资料文件</label>
                <label className="admin-file-picker">
                  <Upload size={16} />
                  <span>{knowledgeFiles.length ? `已选择 ${knowledgeFiles.length} 个文件` : '选择 md / txt / PDF'}</span>
                  <input
                    type="file"
                    multiple
                    accept=".md,.markdown,.txt,.pdf"
                    onChange={e => setKnowledgeFiles(Array.from(e.target.files || []))}
                  />
                </label>
              </div>
              <button
                className="btn-study-primary"
                onClick={handleKnowledgeUpload}
                disabled={!knowledgeSubject.trim() || knowledgeFiles.length === 0 || knowledgeAction === 'upload'}
              >
                {knowledgeAction === 'upload' ? <RefreshCw size={16} className="spin" /> : <Upload size={16} />}
                上传并索引
              </button>
            </div>
            <p className="admin-kb-hint">
              上传后会保存到 <strong>{knowledge.root || 'backend/storage/admin_knowledge'}/学科名/文件名</strong>，一级目录名作为 subject_name，并立即构建向量库。
            </p>
            <div className="admin-knowledge-actions">
              <button className="btn-study-secondary" onClick={() => handleKnowledgeReindex(false)} disabled={Boolean(knowledgeAction)}>
                <RefreshCw size={15} className={knowledgeAction === 'reindex' ? 'spin' : ''} />
                扫描目录增量索引
              </button>
              <button className="btn-study-secondary" onClick={() => handleKnowledgeReindex(true)} disabled={Boolean(knowledgeAction)}>
                <RefreshCw size={15} className={knowledgeAction === 'force-reindex' ? 'spin' : ''} />
                强制重建全部索引
              </button>
            </div>
            {knowledgeResult && (
              <div className={`admin-kb-result-panel ${knowledgeFailedCount ? 'admin-kb-result-panel--warn' : 'admin-kb-result-panel--ok'}`}>
                <div className="admin-kb-result-head">
                  {knowledgeFailedCount ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
                  <span>
                    上传完成：成功 {knowledgeSuccessCount} 个，失败 {knowledgeFailedCount} 个
                  </span>
                </div>
                <div className="admin-kb-result-list">
                  {(knowledgeResult.results || []).map((item, index) => (
                    <div key={`${item.filename}-${index}`} className="admin-kb-result-item">
                      <div>
                        <strong>{item.filename}</strong>
                        <small>{item.subject_name} · {item.bytes ? `${(item.bytes / 1024 / 1024).toFixed(2)} MB` : '未写入文件'}</small>
                      </div>
                      <span className={`admin-kb-result-status ${item.status === 'failed' ? 'failed' : 'success'}`}>
                        {item.status === 'failed' ? `失败：${item.error || '未知错误'}` : `成功：${item.status}`}
                      </span>
                    </div>
                  ))}
                </div>
                <pre className="admin-kb-result">{JSON.stringify(knowledgeResult, null, 2)}</pre>
              </div>
            )}
          </section>

          <div className="admin-table-wrap">
            {knowledgeLoading ? (
              <div className="admin-loading">
                <RefreshCw size={24} className="spin" />
                <span>加载知识库...</span>
              </div>
            ) : knowledgeDocs.length === 0 ? (
              <div className="admin-empty">
                <Database size={36} />
                <p>暂无管理员持久资料</p>
              </div>
            ) : (
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>学科</th>
                    <th>文件名</th>
                    <th>类型</th>
                    <th>字符数</th>
                    <th>Chunks</th>
                    <th>向量</th>
                    <th>更新时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {knowledgeDocs.map(doc => (
                    <tr key={doc.id}>
                      <td><span className="admin-badge"><FolderOpen size={12} /> {doc.subject_name}</span></td>
                      <td className="email-cell">{doc.filename}</td>
                      <td>{doc.file_type}</td>
                      <td>{doc.char_count}</td>
                      <td>{doc.chunk_count}</td>
                      <td>
                        <span className={`status-badge ${doc.embedding_provider === 'dashscope' ? 'active' : 'inactive'}`}>
                          {doc.embedding_provider === 'dashscope' ? '百炼' : '轻量'}
                        </span>
                        <div className="admin-kb-model">{doc.embedding_model}</div>
                      </td>
                      <td className="date-cell">{new Date(doc.updated_at).toLocaleString('zh-CN')}</td>
                      <td>
                        <button
                          className="btn-icon-action btn-red"
                          title="删除资料"
                          disabled={knowledgeAction === `delete-${doc.id}`}
                          onClick={() => handleKnowledgeDelete(doc)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {activeTab === 'users' && (
        <>
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
        </>
      )}

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
