import { useState } from 'react'
import { Map, CheckCircle2, Circle, Lock, ChevronRight, Clock, BookOpen, Zap, ArrowRight } from 'lucide-react'
import { useAppStore } from '../store'
import { generateLearningPath, updateLearningProgress } from '../api'

const MOCK_PATH = {
  course: '机器学习基础',
  total_steps: 5,
  estimated_total_hours: 20,
  current_step: 1,
  steps: [
    {
      step_no: 1, title: '数学基础导入', status: 'completed',
      description: '线性代数、微积分、概率统计基础回顾',
      resource_types: ['document', 'mind_map'],
      estimated_hours: 3, prerequisites: []
    },
    {
      step_no: 2, title: '机器学习核心概念', status: 'in_progress',
      description: '监督/非监督学习、模型评估、过拟合与正则化',
      resource_types: ['document', 'video_script', 'quiz'],
      estimated_hours: 5, prerequisites: ['step_1']
    },
    {
      step_no: 3, title: '经典算法精讲', status: 'pending',
      description: '线性回归、决策树、SVM、聚类算法',
      resource_types: ['document', 'code_case', 'quiz'],
      estimated_hours: 6, prerequisites: ['step_2']
    },
    {
      step_no: 4, title: '深度学习入门', status: 'pending',
      description: '神经网络、反向传播、CNN/RNN基础',
      resource_types: ['video_script', 'code_case'],
      estimated_hours: 4, prerequisites: ['step_3']
    },
    {
      step_no: 5, title: '综合项目实战', status: 'pending',
      description: '完整ML项目流程：数据处理→建模→评估→部署',
      resource_types: ['code_case', 'quiz'],
      estimated_hours: 2, prerequisites: ['step_4']
    },
  ]
}

const RESOURCE_ICONS = {
  document: '📄', mind_map: '🗺️', quiz: '📝',
  video_script: '🎬', code_case: '💻', reading: '📚'
}

const STATUS_CONFIG = {
  completed: { label: '已完成', color: '#10b981', icon: CheckCircle2 },
  in_progress: { label: '学习中', color: '#6366f1', icon: Circle },
  pending: { label: '未开始', color: '#94a3b8', icon: Lock },
}

export default function LearningPathPage() {
  const { userId, learningPath, setLearningPath, profile } = useAppStore()
  const [course, setCourse] = useState('')
  const [generating, setGenerating] = useState(false)
  const [activeStep, setActiveStep] = useState(null)
  const path = learningPath || MOCK_PATH

  const handleGenerate = async () => {
    if (!course.trim()) return
    setGenerating(true)
    try {
      const result = await generateLearningPath(userId, course)
      setLearningPath(result)
    } catch (e) {
      console.error(e)
    } finally {
      setGenerating(false)
    }
  }

  const completedSteps = path.steps.filter(s => s.status === 'completed').length
  const progressPct = Math.round((completedSteps / path.total_steps) * 100)

  return (
    <div className="lp-page">
      {/* 页面标题 + 生成控制 */}
      <div className="lp-header">
        <div className="lp-title">
          <Map size={22} />
          <div>
            <h1>个性化学习路径</h1>
            <p>基于你的画像动态规划，科学分步学习</p>
          </div>
        </div>
        <div className="lp-generate-row">
          <input
            className="form-input"
            placeholder="输入课程名称，重新规划路径..."
            value={course}
            onChange={e => setCourse(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleGenerate()}
          />
          <button className="btn-generate-sm" onClick={handleGenerate} disabled={generating || !course.trim()}>
            <Zap size={15} />
            {generating ? '规划中...' : '生成路径'}
          </button>
        </div>
      </div>

      <div className="lp-body">
        {/* 左侧：路径总览 */}
        <div className="lp-overview">
          {/* 进度卡片 */}
          <div className="lp-progress-card">
            <div className="lp-course-title">{path.course}</div>
            <div className="lp-progress-ring-area">
              <svg className="progress-ring" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="32" fill="none" stroke="#e2e8f0" strokeWidth="6" />
                <circle
                  cx="40" cy="40" r="32" fill="none" stroke="#6366f1" strokeWidth="6"
                  strokeDasharray={`${2 * Math.PI * 32}`}
                  strokeDashoffset={`${2 * Math.PI * 32 * (1 - progressPct / 100)}`}
                  strokeLinecap="round"
                  transform="rotate(-90 40 40)"
                />
                <text x="40" y="45" textAnchor="middle" className="ring-text">{progressPct}%</text>
              </svg>
            </div>
            <div className="lp-meta">
              <div className="lp-meta-item">
                <Clock size={14} />
                <span>{path.estimated_total_hours}h 预计学时</span>
              </div>
              <div className="lp-meta-item">
                <CheckCircle2 size={14} />
                <span>{completedSteps}/{path.total_steps} 步骤完成</span>
              </div>
            </div>
          </div>

          {/* 步骤列表 */}
          <div className="lp-steps">
            {path.steps.map((step, idx) => {
              const cfg = STATUS_CONFIG[step.status]
              const Icon = cfg.icon
              return (
                <div key={step.step_no}>
                  <button
                    className={`lp-step ${step.status} ${activeStep === idx ? 'lp-step--active' : ''}`}
                    onClick={() => setActiveStep(activeStep === idx ? null : idx)}
                  >
                    <div className="step-indicator" style={{ color: cfg.color }}>
                      <Icon size={18} />
                    </div>
                    <div className="step-info">
                      <div className="step-title-row">
                        <span className="step-no">Step {step.step_no}</span>
                        <span className="step-status-badge" style={{ background: `${cfg.color}20`, color: cfg.color }}>
                          {cfg.label}
                        </span>
                      </div>
                      <span className="step-name">{step.title}</span>
                    </div>
                    <ChevronRight size={16} className={`step-arrow ${activeStep === idx ? 'rotated' : ''}`} />
                  </button>

                  {/* 步骤连接线 */}
                  {idx < path.steps.length - 1 && (
                    <div className="step-connector" style={{ background: step.status === 'completed' ? '#10b981' : '#e2e8f0' }} />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* 右侧：步骤详情 */}
        <div className="lp-detail">
          {activeStep !== null ? (
            <StepDetail step={path.steps[activeStep]} />
          ) : (
            <div className="lp-detail-placeholder">
              <Map size={40} />
              <h3>点击左侧步骤查看详情</h3>
              <p>每个学习步骤包含目标说明、推荐资源和练习内容</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StepDetail({ step }) {
  const cfg = STATUS_CONFIG[step.status]
  const navigate = (url) => window.location.href = url

  return (
    <div className="step-detail-card">
      <div className="step-detail-header">
        <div>
          <h2>{step.title}</h2>
          <span className="step-status-badge lg" style={{ background: `${cfg.color}20`, color: cfg.color }}>
            {cfg.label}
          </span>
        </div>
        <div className="step-hours">
          <Clock size={16} />
          <span>{step.estimated_hours}h</span>
        </div>
      </div>

      <p className="step-desc">{step.description}</p>

      {/* 前置条件 */}
      {step.prerequisites.length > 0 && (
        <div className="step-prereqs">
          <h4>前置条件</h4>
          {step.prerequisites.map(p => (
            <span key={p} className="prereq-tag">{p}</span>
          ))}
        </div>
      )}

      {/* 推荐资源类型 */}
      <div className="step-resources-section">
        <h4>本阶段推荐资源</h4>
        <div className="step-resource-chips">
          {step.resource_types.map(t => (
            <div key={t} className="resource-type-chip">
              <span>{RESOURCE_ICONS[t]}</span>
              <span>{t}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="step-actions">
        <a href="/app/resources" className="btn-step-action btn-step-primary">
          <BookOpen size={16} />
          生成本阶段资源
          <ArrowRight size={16} />
        </a>
        {step.status === 'in_progress' && (
          <button className="btn-step-action btn-step-secondary">
            <CheckCircle2 size={16} />
            标记为已完成
          </button>
        )}
        {step.status === 'pending' && (
          <button className="btn-step-action btn-step-secondary">
            开始学习
          </button>
        )}
      </div>
    </div>
  )
}
