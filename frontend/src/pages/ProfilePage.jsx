import { useState } from 'react'
import { User, Brain, Target, BookOpen, TrendingUp, Clock, Zap, Edit3, Check, RefreshCw } from 'lucide-react'
import { useAppStore } from '../store'

const COGNITION_STYLES = [
  { id: 'visual', label: '视觉型', desc: '通过图表、思维导图理解知识', emoji: '👁️' },
  { id: 'auditory', label: '听觉型', desc: '通过讲解视频、语音学习', emoji: '👂' },
  { id: 'reading', label: '阅读型', desc: '通过文档、笔记深度理解', emoji: '📖' },
  { id: 'kinesthetic', label: '动手型', desc: '通过实操案例、项目学习', emoji: '🛠️' },
]

const LEARNING_PACES = [
  { id: 'fast', label: '快节奏', desc: '每天2h+，快速推进' },
  { id: 'medium', label: '稳健型', desc: '每天1-2h，循序渐进' },
  { id: 'slow', label: '精深型', desc: '每天<1h，深度钻研' },
]

// 模拟画像数据
const DEMO_PROFILE = {
  major: '计算机科学与技术',
  grade: '大三',
  school: '示例大学',
  cognition_style: 'visual',
  learning_pace: 'medium',
  learning_goals: ['掌握机器学习基础', '完成毕业设计项目', '提升算法能力'],
  current_courses: ['机器学习', '数据结构', '操作系统'],
  weak_points: ['图算法', '动态规划', '概率统计'],
  preferred_resource_types: ['video_script', 'code_case', 'mind_map'],
  study_time_per_day: 90,
  knowledge_foundation: {
    '数学基础': 65, '编程能力': 80, '算法基础': 55,
    '机器学习': 40, '深度学习': 30, '工程实践': 70
  },
  profile_completeness: 0.78
}

export default function ProfilePage() {
  const { profile: storeProfile, setProfile } = useAppStore()
  const profile = storeProfile || DEMO_PROFILE
  const [editingGoal, setEditingGoal] = useState(false)
  const [newGoal, setNewGoal] = useState('')
  const [editingWeak, setEditingWeak] = useState(false)
  const [newWeak, setNewWeak] = useState('')

  const completeness = profile.profile_completeness || 0

  return (
    <div className="profile-page">
      {/* 头部 */}
      <div className="profile-hero">
        <div className="profile-avatar-lg">
          <User size={36} />
        </div>
        <div className="profile-hero-info">
          <h1>{profile.school || '我的学习画像'}</h1>
          <p>{profile.major} · {profile.grade}</p>
          <div className="completeness-bar-row">
            <span>画像完整度</span>
            <div className="completeness-track">
              <div className="completeness-fill" style={{ width: `${Math.round(completeness * 100)}%` }} />
            </div>
            <span className="completeness-pct">{Math.round(completeness * 100)}%</span>
          </div>
        </div>
        <a href="/app/chat" className="btn-refine-profile">
          <Zap size={15} />
          通过对话完善
        </a>
      </div>

      <div className="profile-grid">
        {/* 维度1：认知风格 */}
        <div className="profile-card">
          <div className="card-label">
            <Brain size={16} />
            <span>认知风格</span>
            <span className="dim-badge">维度 1</span>
          </div>
          <div className="cognition-grid">
            {COGNITION_STYLES.map(s => (
              <div key={s.id} className={`cognition-chip ${profile.cognition_style === s.id ? 'cognition-chip--active' : ''}`}>
                <span className="cog-emoji">{s.emoji}</span>
                <span className="cog-label">{s.label}</span>
                <span className="cog-desc">{s.desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 维度2：知识基础雷达 */}
        <div className="profile-card">
          <div className="card-label">
            <TrendingUp size={16} />
            <span>知识基础</span>
            <span className="dim-badge">维度 2</span>
          </div>
          <div className="knowledge-bars">
            {Object.entries(profile.knowledge_foundation || {}).map(([subject, score]) => (
              <div key={subject} className="knowledge-bar-row">
                <span className="kb-subject">{subject}</span>
                <div className="kb-track">
                  <div
                    className="kb-fill"
                    style={{
                      width: `${score}%`,
                      background: score >= 70 ? '#10b981' : score >= 50 ? '#6366f1' : '#f59e0b'
                    }}
                  />
                </div>
                <span className="kb-score">{score}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 维度3：学习目标 */}
        <div className="profile-card">
          <div className="card-label">
            <Target size={16} />
            <span>学习目标</span>
            <span className="dim-badge">维度 3</span>
            <button className="card-edit-btn" onClick={() => setEditingGoal(!editingGoal)}>
              <Edit3 size={13} />
            </button>
          </div>
          <div className="tag-list">
            {(profile.learning_goals || []).map((g, i) => (
              <span key={i} className="profile-tag profile-tag--blue">{g}</span>
            ))}
          </div>
          {editingGoal && (
            <div className="add-tag-row">
              <input
                className="form-input-sm"
                placeholder="添加新目标..."
                value={newGoal}
                onChange={e => setNewGoal(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && newGoal.trim()) {
                    // TODO: 更新画像
                    setNewGoal('')
                    setEditingGoal(false)
                  }
                }}
              />
            </div>
          )}
        </div>

        {/* 维度4：易错点与薄弱点 */}
        <div className="profile-card">
          <div className="card-label">
            <RefreshCw size={16} />
            <span>易错点 / 薄弱点</span>
            <span className="dim-badge">维度 4</span>
            <button className="card-edit-btn" onClick={() => setEditingWeak(!editingWeak)}>
              <Edit3 size={13} />
            </button>
          </div>
          <div className="tag-list">
            {(profile.weak_points || []).map((w, i) => (
              <span key={i} className="profile-tag profile-tag--red">{w}</span>
            ))}
          </div>
          {editingWeak && (
            <div className="add-tag-row">
              <input
                className="form-input-sm"
                placeholder="添加薄弱点..."
                value={newWeak}
                onChange={e => setNewWeak(e.target.value)}
              />
            </div>
          )}
        </div>

        {/* 维度5：学习节奏 */}
        <div className="profile-card">
          <div className="card-label">
            <Clock size={16} />
            <span>学习节奏</span>
            <span className="dim-badge">维度 5</span>
          </div>
          <div className="pace-options">
            {LEARNING_PACES.map(p => (
              <div key={p.id} className={`pace-option ${profile.learning_pace === p.id ? 'pace-option--active' : ''}`}>
                <span className="pace-label">{p.label}</span>
                <span className="pace-desc">{p.desc}</span>
                {profile.learning_pace === p.id && <Check size={14} className="pace-check" />}
              </div>
            ))}
          </div>
          {profile.study_time_per_day && (
            <p className="pace-daily">每日学习时长：约 <strong>{profile.study_time_per_day} 分钟</strong></p>
          )}
        </div>

        {/* 维度6：偏好资源类型 */}
        <div className="profile-card">
          <div className="card-label">
            <BookOpen size={16} />
            <span>资源偏好</span>
            <span className="dim-badge">维度 6</span>
          </div>
          <div className="pref-resource-list">
            {[
              { id: 'document', label: '课程文档', icon: '📄' },
              { id: 'video_script', label: '教学视频', icon: '🎬' },
              { id: 'quiz', label: '练习题目', icon: '📝' },
              { id: 'code_case', label: '代码案例', icon: '💻' },
              { id: 'mind_map', label: '思维导图', icon: '🗺️' },
            ].map(({ id, label, icon }) => (
              <div key={id} className={`pref-chip ${(profile.preferred_resource_types || []).includes(id) ? 'pref-chip--active' : ''}`}>
                <span>{icon}</span>
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 维度7：当前课程（额外维度） */}
        <div className="profile-card profile-card--wide">
          <div className="card-label">
            <BookOpen size={16} />
            <span>当前课程</span>
            <span className="dim-badge">维度 7</span>
          </div>
          <div className="tag-list">
            {(profile.current_courses || []).map((c, i) => (
              <span key={i} className="profile-tag profile-tag--green">{c}</span>
            ))}
          </div>
        </div>
      </div>

      {/* 画像更新提示 */}
      <div className="profile-update-hint">
        <Zap size={16} />
        <p>画像会根据你的学习行为和对话自动更新，也可以<a href="/app/chat">通过对话</a>主动完善</p>
      </div>
    </div>
  )
}
