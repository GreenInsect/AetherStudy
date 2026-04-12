import { useNavigate } from 'react-router-dom'
import { Zap, BookOpen, Map, Brain, ChevronRight, Sparkles, Users, Target } from 'lucide-react'

const FEATURES = [
  {
    icon: Brain,
    title: '对话式画像构建',
    desc: '通过自然语言对话，自动构建包含6+维度的个性化学习画像',
    color: '#6366f1'
  },
  {
    icon: Sparkles,
    title: '多智能体协同生成',
    desc: '多个专业AI智能体协作，生成文档、思维导图、题库、视频等5+类资源',
    color: '#0ea5e9'
  },
  {
    icon: Map,
    title: '个性化学习路径',
    desc: '依据画像分析，动态规划专属学习路径，精准推送学习内容',
    color: '#10b981'
  },
  {
    icon: Target,
    title: '智能辅导评估',
    desc: '实时答疑解惑，多维度评估学习效果，持续优化学习方案',
    color: '#f59e0b'
  },
]

const STATS = [
  { value: '5+', label: '资源生成类型' },
  { value: '6+', label: '画像维度' },
  { value: '多智能体', label: '架构设计' },
  { value: '实时流式', label: '输出体验' },
]

export default function HomePage() {
  const navigate = useNavigate()

  return (
    <div className="home-page">
      {/* 顶部导航 */}
      <nav className="home-nav">
        <div className="home-nav-inner">
          <div className="home-logo">
            <Zap size={22} />
            <span>AetherStudy AI</span>
          </div>
          <div className="home-nav-links">
            <a href="#features">功能特性</a>
            <a href="#how">工作原理</a>
            <button className="btn-nav-cta" onClick={() => navigate('/app/chat')}>
              立即使用
            </button>
          </div>
        </div>
      </nav>

      {/* Hero 区块 */}
      <section className="hero-section">
        <div className="hero-badge">
          <Sparkles size={13} />
          <span>基于多智能体AI架构</span>
        </div>
        <h1 className="hero-title">
          你的专属
          <br />
          <span className="hero-title-highlight">AI学习伙伴</span>
        </h1>
        <p className="hero-subtitle">
          通过对话理解你的学习需求，多智能体协同生成个性化学习资源，
          <br />
          规划专属学习路径，全面提升学习效率
        </p>
        <div className="hero-actions">
          <button className="btn-hero-primary" onClick={() => navigate('/app/chat')}>
            开始智能学习
            <ChevronRight size={18} />
          </button>
          <button className="btn-hero-secondary" onClick={() => navigate('/app/resources')}>
            查看资源示例
          </button>
        </div>

        {/* 统计数据 */}
        <div className="hero-stats">
          {STATS.map(({ value, label }) => (
            <div key={label} className="stat-item">
              <div className="stat-value">{value}</div>
              <div className="stat-label">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* 功能特性 */}
      <section className="features-section" id="features">
        <div className="section-header">
          <h2>核心功能</h2>
          <p>多智能体协同，打造全方位智能学习体验</p>
        </div>
        <div className="features-grid">
          {FEATURES.map(({ icon: Icon, title, desc, color }) => (
            <div key={title} className="feature-card">
              <div className="feature-icon" style={{ background: `${color}18`, color }}>
                <Icon size={24} />
              </div>
              <h3>{title}</h3>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 工作流程 */}
      <section className="how-section" id="how">
        <div className="section-header">
          <h2>工作原理</h2>
          <p>三步开启个性化学习之旅</p>
        </div>
        <div className="steps-row">
          {[
            { no: '01', title: '对话建立画像', desc: '与AI对话，描述你的专业、目标、困惑，系统自动提取特征构建学习画像' },
            { no: '02', title: '智能体生成资源', desc: '多个专业AI智能体并发工作，为你生成文档、思维导图、题库、视频脚本等学习资料' },
            { no: '03', title: '个性化学习', desc: '获得专属学习路径规划，按序学习并接受实时评估，持续优化学习效果' },
          ].map(({ no, title, desc }) => (
            <div key={no} className="step-card">
              <div className="step-number">{no}</div>
              <h3>{title}</h3>
              <p>{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <h2>准备好开始了吗？</h2>
        <p>立即开始与AI对话，构建你的专属学习画像</p>
        <button className="btn-hero-primary" onClick={() => navigate('/app/chat')}>
          免费开始使用
          <ChevronRight size={18} />
        </button>
      </section>

      {/* 底部 */}
      <footer className="home-footer">
        <div className="footer-logo">
          <Zap size={16} />
          <span>AetherStudy AI</span>
        </div>
        <p>智能学习助手系统 · 多智能体协同架构</p>
      </footer>
    </div>
  )
}
