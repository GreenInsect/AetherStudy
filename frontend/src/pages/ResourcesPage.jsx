import { useState } from 'react'
import { FileText, GitBranch, ClipboardList, BookOpen, Video, Code, Presentation, CreditCard, Zap, CheckCircle2, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAppStore } from '../store'
import { streamGenerateResources } from '../api'

const RESOURCE_TYPES = [
  { id: 'document', label: '课程讲解文档', icon: FileText, color: '#6366f1', agentName: '课程文档专家' },
  { id: 'mind_map', label: '知识思维导图', icon: GitBranch, color: '#0ea5e9', agentName: '知识图谱专家' },
  { id: 'quiz', label: '练习题库', icon: ClipboardList, color: '#10b981', agentName: '题库出题专家' },
  { id: 'reading', label: '拓展阅读', icon: BookOpen, color: '#8b5cf6', agentName: '知识拓展专家' },
  { id: 'video_script', label: '教学视频脚本', icon: Video, color: '#f43f5e', agentName: '视频内容制作专家' },
  { id: 'code_case', label: '代码实操案例', icon: Code, color: '#f59e0b', agentName: '代码实践专家' },
]

export default function ResourcesPage() {
  const { userId, currentResources, addResource, clearResources, addGenerationTask, updateGenerationTask } = useAppStore()

  const [topic, setTopic] = useState('')
  const [course, setCourse] = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [selectedTypes, setSelectedTypes] = useState(['document', 'mind_map', 'quiz'])
  const [generating, setGenerating] = useState(false)
  const [agentStatus, setAgentStatus] = useState({})  // agentId -> status
  const [progress, setProgress] = useState(0)
  const [progressMsg, setProgressMsg] = useState('')

  const toggleType = (id) => {
    setSelectedTypes(prev =>
      prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
    )
  }

  const startGeneration = async () => {
    if (!topic.trim() || selectedTypes.length === 0) return
    clearResources()
    setAgentStatus({})
    setGenerating(true)
    setProgress(0)
    setProgressMsg('正在启动多智能体系统...')

    try {
      for await (const event of streamGenerateResources(userId, topic, selectedTypes, course, difficulty)) {
        if (event.type === 'task_start') {
          setProgressMsg(event.message)
        } else if (event.type === 'agent_start') {
          setAgentStatus(prev => ({ ...prev, [event.agent_id]: 'generating' }))
          setProgressMsg(`${event.agent_name} 正在生成 ${getLabelById(event.resource_type)}...`)
          setProgress(event.progress)
        } else if (event.type === 'resource_ready') {
          setAgentStatus(prev => ({ ...prev, [event.agent_id]: 'done' }))
          addResource(event.resource)
          setProgress(event.progress)
        } else if (event.type === 'task_complete') {
          setProgress(1)
          setProgressMsg(`✅ 全部完成！共生成 ${event.total_resources} 份学习资源`)
        }
      }
    } catch (e) {
      setProgressMsg('生成失败，请重试')
    } finally {
      setGenerating(false)
    }
  }

  const getLabelById = (id) => RESOURCE_TYPES.find(t => t.id === id)?.label || id

  return (
    <div className="resources-page">
      {/* 生成控制面板 */}
      <div className="generate-panel">
        <div className="panel-header">
          <Zap size={20} />
          <h2>多智能体资源生成</h2>
        </div>

        <div className="generate-form">
          <div className="form-row">
            <div className="form-field">
              <label>学习主题 / 知识点 *</label>
              <input
                className="form-input"
                placeholder="例如：机器学习中的反向传播算法"
                value={topic}
                onChange={e => setTopic(e.target.value)}
              />
            </div>
            <div className="form-field">
              <label>所属课程（可选）</label>
              <input
                className="form-input"
                placeholder="例如：深度学习"
                value={course}
                onChange={e => setCourse(e.target.value)}
              />
            </div>
            <div className="form-field form-field--sm">
              <label>难度</label>
              <select className="form-select" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
                <option value="easy">入门</option>
                <option value="medium">中级</option>
                <option value="hard">进阶</option>
              </select>
            </div>
          </div>

          {/* 资源类型选择 */}
          <div className="type-select-area">
            <label>选择生成的资源类型（多选）</label>
            <div className="type-grid">
              {RESOURCE_TYPES.map(({ id, label, icon: Icon, color }) => (
                <button
                  key={id}
                  className={`type-chip ${selectedTypes.includes(id) ? 'type-chip--selected' : ''}`}
                  onClick={() => toggleType(id)}
                  style={selectedTypes.includes(id) ? { borderColor: color, background: `${color}14` } : {}}
                >
                  <Icon size={16} style={{ color: selectedTypes.includes(id) ? color : undefined }} />
                  <span>{label}</span>
                  {selectedTypes.includes(id) && (
                    <CheckCircle2 size={14} style={{ color }} />
                  )}
                </button>
              ))}
            </div>
          </div>

          <button
            className="btn-generate"
            onClick={startGeneration}
            disabled={!topic.trim() || selectedTypes.length === 0 || generating}
          >
            {generating ? <Loader2 size={18} className="spin" /> : <Zap size={18} />}
            {generating ? '生成中...' : `启动生成（${selectedTypes.length}种资源）`}
          </button>
        </div>

        {/* 生成进度 */}
        {(generating || progress > 0) && (
          <div className="generation-progress">
            <div className="progress-track">
              <div className="progress-bar-fill" style={{ width: `${Math.round(progress * 100)}%` }} />
            </div>
            <p className="progress-msg">{progressMsg}</p>

            {/* 智能体状态 */}
            <div className="agents-status">
              {RESOURCE_TYPES.filter(t => selectedTypes.includes(t.id)).map(({ id, agentName, color, icon: Icon }) => {
                const agentId = `agent-${id === 'document' ? 'doc' : id.replace('_', '')}`
                const status = agentStatus[agentId] || agentStatus[`agent-${id}`] || 'waiting'
                return (
                  <div key={id} className={`agent-chip agent-chip--${status}`}>
                    <Icon size={13} style={{ color }} />
                    <span>{agentName}</span>
                    {status === 'generating' && <Loader2 size={12} className="spin" />}
                    {status === 'done' && <CheckCircle2 size={12} style={{ color: '#10b981' }} />}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* 资源卡片展示 */}
      {currentResources.length > 0 && (
        <div className="resources-grid">
          {currentResources.map(resource => (
            <ResourceCard key={resource.id} resource={resource} />
          ))}
        </div>
      )}

      {currentResources.length === 0 && !generating && (
        <div className="resources-empty">
          <BookOpen size={48} />
          <h3>暂无学习资源</h3>
          <p>填写学习主题并选择资源类型，点击「启动生成」开始创建</p>
        </div>
      )}
    </div>
  )
}

function ResourceCard({ resource }) {
  const [expanded, setExpanded] = useState(false)
  const typeConfig = RESOURCE_TYPES.find(t => t.id === resource.type) || {}
  const Icon = typeConfig.icon || FileText

  const renderContent = () => {
    const c = resource.content
    if (!c) return null

    switch (resource.type) {
      case 'document':
        return (
          <div className="resource-content-doc">
            {c.sections?.map((s, i) => (
              <div key={i} className="doc-section">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{s.title}</ReactMarkdown>
                <p>{s.content}</p>
              </div>
            ))}
          </div>
        )
      case 'mind_map':
        return (
          <div className="resource-content-mermaid">
            <pre className="mermaid-code">{c.mermaid_code}</pre>
            <p className="mermaid-hint">💡 使用 mermaid.js 渲染此思维导图</p>
          </div>
        )
      case 'quiz':
        return (
          <div className="resource-content-quiz">
            {c.questions?.map((q, i) => (
              <div key={i} className="quiz-question">
                <p className="q-text"><strong>Q{q.id}.</strong> {q.question}</p>
                {q.options && (
                  <div className="q-options">
                    {q.options.map((o, j) => (
                      <label key={j} className="q-option">
                        <input type="radio" name={`q${q.id}`} />
                        <span>{String.fromCharCode(65 + j)}. {o}</span>
                      </label>
                    ))}
                  </div>
                )}
                <details className="q-answer">
                  <summary>查看答案</summary>
                  <p>答案：{q.answer}</p>
                  <p>解析：{q.explanation}</p>
                </details>
              </div>
            ))}
          </div>
        )
      case 'code_case':
        return (
          <div className="resource-content-code">
            <p className="code-desc">{c.description}</p>
            <pre className="code-block"><code>{c.code}</code></pre>
            <p className="code-explain">{c.explanation}</p>
            {c.run_command && <p className="code-cmd">运行: <code>{c.run_command}</code></p>}
          </div>
        )
      case 'video_script':
        return (
          <div className="resource-content-video">
            <p>预计时长：{c.duration_estimate}</p>
            {c.scenes?.map((s, i) => (
              <div key={i} className="scene-item">
                <strong>场景 {s.scene_no}（{s.duration}）</strong>
                <p>旁白：{s.narration}</p>
                <p>画面：{s.visual}</p>
              </div>
            ))}
          </div>
        )
      default:
        return <pre className="json-fallback">{JSON.stringify(c, null, 2)}</pre>
    }
  }

  return (
    <div className="resource-card">
      <div className="resource-card-header" style={{ borderLeftColor: typeConfig.color }}>
        <div className="resource-card-title">
          <Icon size={18} style={{ color: typeConfig.color }} />
          <h3>{resource.title}</h3>
        </div>
        <button className="expand-btn" onClick={() => setExpanded(!expanded)}>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {expanded && (
        <div className="resource-card-body">
          {renderContent()}
        </div>
      )}
    </div>
  )
}
