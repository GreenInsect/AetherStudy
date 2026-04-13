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
    userId, profile, chatMode, setChatMode,
    sessions, sessionsLoaded, setSessions, addSession, removeSession,
    updateSessionMeta, clearAllSessions,
    activeSessionId, activeMessages, setActiveSession,
    appendMessage, upsertStreamingMessage, finalizeStreamingMessage,
  } = useAppStore()
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const messagesEndRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, streamingContent])

  const sendMessage = async (text = input) => {
    if (!text.trim() || streaming) return
    setInput('')

    const userMsg = { role: 'user', content: text }
    addChatMessage(userMsg)
    setStreaming(true)
    setStreamingContent('')

    try {
      let fullContent = ''
      let extractedFeatures = null

      const messages = [...chatMessages, userMsg]
      for await (const event of streamChat(userId, messages, chatMode, profile)) {
        if (event.type === 'delta') {
          fullContent += event.content
          setStreamingContent(fullContent)
        } else if (event.type === 'done') {
          extractedFeatures = event.extracted_features
          console.log('提取到的画像特征:', extractedFeatures)  // 调试日志
        }
      }

      addChatMessage({ role: 'assistant', content: fullContent, extractedFeatures })
      setStreamingContent('')

      if (extractedFeatures) {
        const conversationText = `User: ${text}\nAssistant: ${fullContent}`

        console.log('正在自动更新画像...| extractedFeatures', extractedFeatures)

        try {
          const result = await updateProfile(userId, conversationText, extractedFeatures)
          console.log('画像更新结果:result', result)  // 调试日志
          if (result) {
            setProfile(result.profile)
            console.log('本地画像状态已同步')
          }
        } catch (err) {
          console.error('画像更新失败:', err)
        }
      }

    } catch (e) {
      addChatMessage({ role: 'assistant', content: '抱歉，连接出现问题，请稍后重试。' })
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

  return (
    <div className="chat-page">
      {/* 左侧：对话区 */}
      <div className="chat-main">
        {/* 模式选择 */}
        <div className="chat-mode-bar">
          {MODES.map(m => (
            <button
              key={m.id}
              className={`mode-btn ${chatMode === m.id ? 'mode-btn--active' : ''}`}
              onClick={() => setChatMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* 消息列表 */}
        <div className="chat-messages">
          {chatMessages.length === 0 && (
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

          {chatMessages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}

          {/* 流式输出中的消息 */}
          {streaming && streamingContent && (
            <MessageBubble msg={{ role: 'assistant', content: streamingContent }} streaming />
          )}

          {streaming && !streamingContent && (
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
              minRows={1}
              maxRows={10}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题..."
              disabled={streaming}
            />
            <button
              className="send-btn"
              onClick={() => sendMessage()}
              disabled={!input.trim() || streaming}
            >
              <Send size={18} />
            </button>
          </div>
          <p className="chat-hint">按 Enter 发送，Shift+Enter 换行</p>
        </div>
      </div>

      {/* 右侧：功能面板 */}
      <div className="chat-sidebar">
        {/* 画像摘要 */}
        <ProfileSummaryCard profile={profile} />

        {/* 快捷操作 */}
        <div className="chat-actions-card">
          <h3>快捷操作</h3>
          <button className="action-btn" onClick={() => navigate('/app/resources')}>
            <BookOpen size={16} />
            生成学习资源
          </button>
          <button className="action-btn" onClick={() => {
            setChatMode('profile_building')
            sendMessage('请帮我完善学习画像')
          }}>
            <Sparkles size={16} />
            完善学习画像
          </button>
          <button className="action-btn" onClick={() => navigate('/app/learning-path')}>
            <RefreshCw size={16} />
            重新规划路径
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ msg, streaming = false }) {
  const isAI = msg.role === 'assistant'
  return (
    <div className={`msg-row ${isAI ? 'msg-row--ai' : 'msg-row--user'}`}>
      <div className={`msg-avatar ${isAI ? 'msg-avatar--ai' : 'msg-avatar--user'}`}>
        {isAI ? <Bot size={16} /> : <User size={16} />}
      </div>
      <div className={`msg-bubble ${isAI ? 'msg-bubble--ai' : 'msg-bubble--user'}`}>
        {isAI ? (
          <div className="markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.content}
            </ReactMarkdown>
            {streaming && <span className="cursor-blink">|</span>}
          </div>
        ) : (
          <p>{msg.content}</p>
        )}
      </div>
    </div>
  )
}

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
        <ProfileDim label="专业" value={profile.major || '未设置'} />
        <ProfileDim label="认知风格" value={profile.cognition_style || '未设置'} />
        <ProfileDim label="学习节奏" value={profile.learning_pace || '未设置'} />
        <ProfileDim label="薄弱点" value={profile.weak_points?.join('、') || '未设置'} />
        <ProfileDim label="描述" value={profile.description || '未设置'} />
      </div>
    </div>
  )
}

function ProfileDim({ label, value }) {
  return (
    <div className="profile-dim">
      <span className="dim-label">{label}</span>
      <span className="dim-value">{value}</span>
    </div>
  )
}
