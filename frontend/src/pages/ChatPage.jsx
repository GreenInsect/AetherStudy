import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Send, Bot, User, Sparkles, BookOpen, Plus,
  Trash2, Edit3, Check, X, MessageSquare, Loader2,
  ChevronRight, MoreHorizontal
} from 'lucide-react'
import { useAppStore } from '../store'
import {
  streamChat,
  apiListSessions, apiCreateSession, apiGetSession,
  apiDeleteSession, apiRenameSession, apiClearAllSessions,
  streamChatMessage, updateProfile
} from '../api'
import { useNavigate } from 'react-router-dom'
import TextareaAutosize from 'react-textarea-autosize';

const QUICK_PROMPTS = [
  '我是计算机专业大三学生，想学机器学习',
  '帮我分析一下我的学习薄弱点',
  '我对数据结构中的图算法不太理解',
  '为我生成一份Python进阶学习计划',
]

const MODES = [
  { id: 'general', label: '智能对话', desc: '通用问答与学习辅导' },
  { id: 'profile_building', label: '画像构建', desc: '完善你的学习画像' },
  { id: 'tutoring', label: '专项辅导', desc: '针对具体知识点答疑' },
]

export default function ChatPage() {
  const {
    userId, profile, setProfile, chatMode, setChatMode,
    sessions, sessionsLoaded, setSessions, addSession, removeSession,
    updateSessionMeta, clearAllSessions,
    activeSessionId, activeMessages, setActiveSession,
    appendMessage, upsertStreamingMessage, finalizeStreamingMessage,
  } = useAppStore()

  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [sessionLoading, setSessionLoading] = useState(false) // 切换会话时加载消息
  const messagesEndRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!sessionsLoaded) {
      loadSessions()
    }
  }, [])

  const loadSessions = async () => {
    setSessionsLoading(true)
    try {
      const data = await apiListSessions()
      console.log('[*] klog: 加载会话列表成功 data: ', data)
      setSessions(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('加载会话失败', e)
    } finally {
      setSessionsLoading(false)
    }
  }

  // ── 滚动到底部 ─────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeMessages])

  // ── 新建会话 ───────────────────────────────────────────────────
  const handleNewSession = async () => {
    try {
      const session = await apiCreateSession(chatMode)
      addSession(session)
      setActiveSession(session.id, [])
    } catch (e) {
      console.error('新建会话失败', e)
    }
  }

  // ── 切换会话（从后端加载消息） ─────────────────────────────────
  const handleSelectSession = async (sessionId) => {
    if (sessionId === activeSessionId || streaming) return
    setSessionLoading(true)
    try {
      const data = await apiGetSession(sessionId)
      setActiveSession(data.id, data.messages || [])
      // 同步模式
      if (data.mode) setChatMode(data.mode)
    } catch (e) {
      console.error('加载会话消息失败', e)
    } finally {
      setSessionLoading(false)
    }
  }

  // ── 删除会话 ───────────────────────────────────────────────────
  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation()
    try {
      await apiDeleteSession(sessionId)
      removeSession(sessionId)
    } catch (e) {
      console.error('删除会话失败', e)
    }
  }

  const sendMessage = async (text = input) => {
    if (!text.trim() || streaming) return
    setInput('')

    // 如果没有活跃会话，自动新建
    let sessionId = activeSessionId
    if (!sessionId) {
      try {
        const session = await apiCreateSession(chatMode)
        console.log('[*] klog : 自动新建会话成功 session: ', session)
        addSession(session)
        setActiveSession(session.id, [])
        sessionId = session.id
      } catch (e) {
        console.error('自动新建会话失败', e)
        return
      }
    }

    // 立即追加用户消息到本地
    const userMsg = {
      id: `local-user-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    appendMessage(userMsg)
    setStreaming(true)

    const tempAiId = `streaming-ai-${Date.now()}`

    try {
      let fullContent = ''
      let realAiId = null
      let newTitle = null

      for await (const event of streamChatMessage(sessionId, text, chatMode)) {
        if (event.type === 'delta') {
          fullContent += event.content
          upsertStreamingMessage(tempAiId, fullContent)
        } else if (event.type === 'done') {
          realAiId = event.ai_message_id
          newTitle = event.new_title
          if (chatMode === 'profile_building' && event.extracted_features) {
            console.log('收到AI消息中的画像特征:', event.extracted_features)
            try {
              const result = await updateProfile(userId, `User: ${text}\nAssistant: ${fullContent}`, event.extracted_features)
              console.log('画像更新结果:result', result)  // 调试日志
              if (result) {
                setProfile(result.profile)
                console.log('本地画像状态已同步')
              }
            } catch (err) {
              console.error('画像更新失败:', err)
            }
          }
        }
      }
      if (realAiId) {
        finalizeStreamingMessage(tempAiId, realAiId, fullContent)
      } else {
        // upsertStreamingMessage(tempAiId, null)
        console.warn('!!!!! Error 未收到AI消息ID，无法最终确定消息身份 !!!')
      }
      // 更新侧边栏会话元信息（标题、最后消息预览）
      const preview = fullContent.slice(0, 60) + (fullContent.length > 60 ? '…' : '')
      updateSessionMeta(sessionId, {
        last_message: preview,
        updated_at: new Date().toISOString(),
        ...(newTitle ? { title: newTitle } : {}),
      })
    } catch (e) {
      appendMessage({
        id: `err-${Date.now()}`, session_id: sessionId,
        role: 'assistant', content: '抱歉，发送失败，请稍后重试。',
        created_at: new Date().toISOString(),
      })
    } finally {
      setStreaming(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }
  const hasActiveSession = !!activeSessionId

  return (
    <div className="chat-page-v2">
      {/* ── 左：历史会话面板 ── */}
      <div className="chat-history-panel">
        <div className="history-panel-header">
          <span className="history-panel-title">历史对话</span>
          <button className="btn-new-chat" onClick={handleNewSession} title="新建对话">
            <Plus size={16} />
          </button>
        </div>

        <div className="history-list">
          {sessionsLoading && (
            <div className="history-loading">
              <Loader2 size={16} className="spin" />
              <span>加载中...</span>
            </div>
          )}

          {!sessionsLoading && sessions.length === 0 && (
            <div className="history-empty">
              <MessageSquare size={28} />
              <p>暂无历史对话</p>
              <button className="btn-start-chat" onClick={handleNewSession}>
                开始第一次对话
              </button>
            </div>
          )}

          {sessions.map(session => (
            <SessionItem
              key={session.id}
              session={session}
              active={session.id === activeSessionId}
              onSelect={() => handleSelectSession(session.id)}
              onDelete={(e) => handleDeleteSession(e, session.id)}
              onRename={(newTitle) => {
                apiRenameSession(session.id, newTitle)
                  .then(() => updateSessionMeta(session.id, { title: newTitle }))
              }}
            />
          ))}
        </div>

        {sessions.length > 0 && (
          <button
            className="btn-clear-all"
            onClick={async () => {
              if (!confirm('确定要清空所有历史对话吗？此操作不可撤销。')) return
              await apiClearAllSessions()
              clearAllSessions()
            }}
          >
            <Trash2 size={13} />
            清空所有对话
          </button>
        )}
      </div>

      {/* ── 中：消息区 ── */}
      <div className="chat-main">
        {/* 模式选择 */}
        <div className="chat-mode-bar">
          {MODES.map(m => (
            <button
              key={m.id}
              className={`mode-btn ${chatMode === m.id ? 'mode-btn--active' : ''}`}
              onClick={() => setChatMode(m.id)}
              disabled={streaming}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* 消息区域 */}
        <div className="chat-messages">
          {/* 没有活跃会话时的欢迎界面 */}
          {!hasActiveSession && (
            <div className="chat-welcome">
              <div className="welcome-icon"><Bot size={32} /></div>
              <h2>你好，我是 AetherStudy AI</h2>
              <p>我可以帮你建立学习画像、生成学习资源、规划学习路径</p>
              <div className="quick-prompts">
                {QUICK_PROMPTS.map(p => (
                  <button key={p} className="quick-prompt-btn" onClick={() => sendMessage(p)}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 切换会话时 loading */}
          {sessionLoading && (
            <div className="session-loading">
              <Loader2 size={22} className="spin" />
              <span>加载历史消息...</span>
            </div>
          )}

          {/* 消息气泡 */}
          {!sessionLoading && activeMessages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}

          {/* 流式输出时的打字指示器（仅在还没文字时显示） */}
          {streaming && activeMessages.length > 0 &&
            activeMessages[activeMessages.length - 1]?.role === 'user' && (
              <div className="msg-row msg-row--ai">
                <div className="msg-avatar msg-avatar--ai"><Bot size={16} /></div>
                <div className="msg-bubble msg-bubble--ai">
                  <div className="typing-indicator">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入区 */}
        <div className="chat-input-area">
          <div className="chat-input-box">
            <TextareaAutosize
              className="chat-input"
              placeholder={hasActiveSession ? '输入你的问题...' : '输入消息，自动创建新对话...'}
              minRows={1}
              maxRows={10}
              value={input}
              onChange={e => {
                setInput(e.target.value);
                e.target.style.height = 'auto';
                e.target.style.height = `${e.target.scrollHeight}px`; // 根据内容高度撑开
              }}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={streaming || sessionLoading}
            />
            <button
              className="send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || streaming || sessionLoading}
            >
              {streaming ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
            </button>
          </div>
          <p className="chat-hint">Enter 发送 · Shift+Enter 换行</p>
        </div>
      </div>

      {/* ── 右：功能面板 ── */}
      <div className="chat-sidebar">
        <ProfileSummaryCard profile={profile} />
        <div className="chat-actions-card">
          <h3>快捷操作</h3>
          <button className="action-btn" onClick={() => navigate('/app/resources')}>
            <BookOpen size={16} />生成学习资源
          </button>
          <button className="action-btn" onClick={() => {
            setChatMode('profile_building')
            sendMessage('请帮我完善学习画像')
          }}>
            <Sparkles size={16} />完善学习画像
          </button>
          <button className="action-btn" onClick={handleNewSession}>
            <Plus size={16} />新建对话
          </button>
        </div>
      </div>
    </div>
  )
}

// ── 会话条目组件 ──────────────────────────────────────────────────
function SessionItem({ session, active, onSelect, onDelete, onRename }) {
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(session.title)
  const [menuOpen, setMenuOpen] = useState(false)
  const inputRef = useRef(null)
  const menuRef = useRef(null)

  useEffect(() => {
    if (editing) inputRef.current?.focus()
  }, [editing])

  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const confirmRename = () => {
    if (editTitle.trim() && editTitle !== session.title) {
      onRename(editTitle.trim())
    } else {
      setEditTitle(session.title)
    }
    setEditing(false)
    setMenuOpen(false)
  }

  const formatTime = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    const now = new Date()
    const diffDays = Math.floor((now - d) / 86400000)
    if (diffDays === 0) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    if (diffDays === 1) return '昨天'
    if (diffDays < 7) return `${diffDays}天前`
    return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
  }

  return (
    <div
      className={`history-item ${active ? 'history-item--active' : ''}`}
      onClick={onSelect}
    >
      <div className="history-item-icon">
        <MessageSquare size={14} />
      </div>

      <div className="history-item-body">
        {editing ? (
          <input
            ref={inputRef}
            className="history-rename-input"
            value={editTitle}
            onChange={e => setEditTitle(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') confirmRename()
              if (e.key === 'Escape') { setEditTitle(session.title); setEditing(false) }
            }}
            onClick={e => e.stopPropagation()}
          />
        ) : (
          <span className="history-item-title">{session.title}</span>
        )}
        <span className="history-item-preview">{session.last_message || '暂无消息'}</span>
      </div>

      <div className="history-item-meta">
        <span className="history-item-time">{formatTime(session.updated_at)}</span>
        {editing ? (
          <div className="rename-actions" onClick={e => e.stopPropagation()}>
            <button className="rename-confirm" onClick={confirmRename}><Check size={13} /></button>
            <button className="rename-cancel" onClick={() => { setEditTitle(session.title); setEditing(false) }}>
              <X size={13} />
            </button>
          </div>
        ) : (
          <div className="history-item-actions" ref={menuRef} onClick={e => e.stopPropagation()}>
            <button
              className="history-menu-btn"
              onClick={() => setMenuOpen(v => !v)}
            >
              <MoreHorizontal size={14} />
            </button>
            {menuOpen && (
              <div className="history-dropdown">
                <button onClick={() => { setEditing(true); setMenuOpen(false) }}>
                  <Edit3 size={13} /> 重命名
                </button>
                <button className="danger" onClick={(e) => { setMenuOpen(false); onDelete(e) }}>
                  <Trash2 size={13} /> 删除
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── 消息气泡 ──────────────────────────────────────────────────────
function MessageBubble({ msg }) {
  const isAI = msg.role === 'assistant'
  const isStreaming = msg.id?.startsWith('streaming-ai-')
  return (
    <div className={`msg-row ${isAI ? 'msg-row--ai' : 'msg-row--user'}`}>
      <div className={`msg-avatar ${isAI ? 'msg-avatar--ai' : 'msg-avatar--user'}`}>
        {isAI ? <Bot size={16} /> : <User size={16} />}
      </div>
      <div className={`msg-bubble ${isAI ? 'msg-bubble--ai' : 'msg-bubble--user'}`}>
        {isAI ? (
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
            {isStreaming && <span className="cursor-blink">|</span>}
          </div>
        ) : (
          <p>{msg.content}</p>
        )}
      </div>
    </div>
  )
}

// ── 画像摘要卡 ────────────────────────────────────────────────────
function ProfileSummaryCard({ profile }) {
  if (!profile) {
    return (
      <div className="profile-summary-card">
        <h3>学习画像</h3>
        <p className="no-profile-hint">通过对话建立你的学习画像，获得更精准的个性化推荐</p>
      </div>
    )
  }
  return (
    <div className="profile-summary-card">
      <h3>学习画像摘要</h3>
      <div className="profile-dims">
        {[
          ['专业', profile.major],
          ['学校', profile.school],
          ['年级', profile.grade],
          ['认知风格', profile.cognition_style],
          ['学习节奏', profile.learning_pace],
          ['薄弱点', profile.weak_points?.join('、')],
          ['学习目标', profile.learning_goals?.join('、')],
          ['描述', profile.description],
        ].map(([label, value]) => (
          <div key={label} className="profile-dim">
            <span className="dim-label">{label}</span>
            <span className="dim-value">{value || '未设置'}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
