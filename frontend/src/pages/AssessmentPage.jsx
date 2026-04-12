import { useState } from 'react'
import { BarChart2, CheckCircle2, XCircle, Clock, TrendingUp, Award, RefreshCw, Send } from 'lucide-react'
import { useAppStore } from '../store'
import { submitQuiz } from '../api'

// 模拟题目数据
const DEMO_QUIZ = {
  resource_id: 'demo-quiz-001',
  title: '机器学习基础 - 综合测验',
  questions: [
    {
      id: 1, type: 'single_choice',
      question: '下列哪种算法属于无监督学习？',
      options: ['线性回归', 'K-Means聚类', '支持向量机', '决策树'],
      answer: 'B', difficulty: 'easy'
    },
    {
      id: 2, type: 'single_choice',
      question: '过拟合（Overfitting）的主要原因是什么？',
      options: ['模型过于简单', '训练数据不足或模型过于复杂', '学习率太小', '特征数量太少'],
      answer: 'B', difficulty: 'medium'
    },
    {
      id: 3, type: 'single_choice',
      question: '在神经网络中，ReLU激活函数的表达式是？',
      options: ['f(x) = 1/(1+e^-x)', 'f(x) = max(0, x)', 'f(x) = tanh(x)', 'f(x) = x'],
      answer: 'B', difficulty: 'medium'
    },
    {
      id: 4, type: 'single_choice',
      question: '交叉验证（Cross-Validation）的主要用途是？',
      options: ['加速模型训练', '评估模型泛化性能', '降低特征维度', '处理缺失值'],
      answer: 'B', difficulty: 'hard'
    },
    {
      id: 5, type: 'single_choice',
      question: '梯度下降中，学习率过大会导致什么问题？',
      options: ['收敛速度太慢', '局部最优', '损失函数震荡甚至发散', '内存溢出'],
      answer: 'C', difficulty: 'medium'
    }
  ]
}

// 模拟评估报告
const DEMO_REPORT = {
  score: 80,
  accuracy_rate: 0.8,
  time_spent: 342,
  weak_areas: ['深度学习细节', '高级优化技巧'],
  strong_areas: ['基础概念', '监督学习理解'],
  recommendations: [
    '建议重点练习深度学习相关题目',
    '可以尝试实操代码案例加深理解',
    '梯度下降部分需要加强'
  ],
  next_steps: ['生成深度学习专项练习', '查看梯度下降动画讲解', '完成代码实操案例']
}

export default function AssessmentPage() {
  const { userId } = useAppStore()
  const [phase, setPhase] = useState('intro') // intro | quiz | result
  const [answers, setAnswers] = useState({})
  const [startTime, setStartTime] = useState(null)
  const [report, setReport] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [currentQ, setCurrentQ] = useState(0)

  const startQuiz = () => {
    setPhase('quiz')
    setStartTime(Date.now())
    setCurrentQ(0)
    setAnswers({})
  }

  const selectAnswer = (qId, option) => {
    setAnswers(prev => ({ ...prev, [qId]: option }))
  }

  const nextQuestion = () => {
    if (currentQ < DEMO_QUIZ.questions.length - 1) {
      setCurrentQ(c => c + 1)
    }
  }

  const submitAnswers = async () => {
    setSubmitting(true)
    try {
      const submissionAnswers = DEMO_QUIZ.questions.map(q => ({
        question_id: q.id,
        answer: answers[q.id] || '',
        time_spent_seconds: Math.round((Date.now() - startTime) / 1000 / DEMO_QUIZ.questions.length)
      }))
      // const result = await submitQuiz(userId, DEMO_QUIZ.resource_id, submissionAnswers)
      setReport(DEMO_REPORT) // 模拟
      setPhase('result')
    } catch (e) {
      console.error(e)
    } finally {
      setSubmitting(false)
    }
  }

  const allAnswered = DEMO_QUIZ.questions.every(q => answers[q.id])

  return (
    <div className="assessment-page">
      {/* 介绍阶段 */}
      {phase === 'intro' && (
        <div className="assessment-intro">
          <div className="intro-icon"><BarChart2 size={40} /></div>
          <h1>学习效果评估</h1>
          <p>通过智能测验，全面评估你的知识掌握情况，获得个性化学习建议</p>

          <div className="quiz-info-cards">
            <div className="quiz-info-card">
              <Clock size={20} />
              <span>约 5-10 分钟</span>
            </div>
            <div className="quiz-info-card">
              <BarChart2 size={20} />
              <span>{DEMO_QUIZ.questions.length} 道题目</span>
            </div>
            <div className="quiz-info-card">
              <TrendingUp size={20} />
              <span>多维度评估</span>
            </div>
          </div>

          <div className="quiz-meta-card">
            <h3>{DEMO_QUIZ.title}</h3>
            <div className="difficulty-dist">
              <span className="diff-easy">简单 × 1</span>
              <span className="diff-medium">中等 × 3</span>
              <span className="diff-hard">困难 × 1</span>
            </div>
          </div>

          <button className="btn-start-quiz" onClick={startQuiz}>
            开始测验
          </button>
        </div>
      )}

      {/* 答题阶段 */}
      {phase === 'quiz' && (
        <div className="quiz-area">
          <div className="quiz-progress-bar">
            <div
              className="quiz-progress-fill"
              style={{ width: `${((currentQ + 1) / DEMO_QUIZ.questions.length) * 100}%` }}
            />
          </div>

          <div className="quiz-counter">
            题目 {currentQ + 1} / {DEMO_QUIZ.questions.length}
          </div>

          {/* 题目导航点 */}
          <div className="q-nav-dots">
            {DEMO_QUIZ.questions.map((_, i) => (
              <button
                key={i}
                className={`q-dot ${i === currentQ ? 'q-dot--current' : ''} ${answers[i + 1] ? 'q-dot--answered' : ''}`}
                onClick={() => setCurrentQ(i)}
              />
            ))}
          </div>

          {/* 当前题目 */}
          <div className="question-card">
            <div className="q-header">
              <span className={`q-difficulty diff-${DEMO_QUIZ.questions[currentQ].difficulty}`}>
                {DEMO_QUIZ.questions[currentQ].difficulty === 'easy' ? '简单' :
                  DEMO_QUIZ.questions[currentQ].difficulty === 'medium' ? '中等' : '困难'}
              </span>
            </div>
            <p className="q-text">{DEMO_QUIZ.questions[currentQ].question}</p>

            <div className="q-options">
              {DEMO_QUIZ.questions[currentQ].options.map((opt, i) => {
                const letter = String.fromCharCode(65 + i)
                const selected = answers[DEMO_QUIZ.questions[currentQ].id] === letter
                return (
                  <button
                    key={i}
                    className={`option-btn ${selected ? 'option-btn--selected' : ''}`}
                    onClick={() => selectAnswer(DEMO_QUIZ.questions[currentQ].id, letter)}
                  >
                    <span className="option-letter">{letter}</span>
                    <span>{opt}</span>
                  </button>
                )
              })}
            </div>

            <div className="q-actions">
              {currentQ < DEMO_QUIZ.questions.length - 1 ? (
                <button
                  className="btn-next-q"
                  onClick={nextQuestion}
                  disabled={!answers[DEMO_QUIZ.questions[currentQ].id]}
                >
                  下一题 →
                </button>
              ) : (
                <button
                  className="btn-submit-quiz"
                  onClick={submitAnswers}
                  disabled={!allAnswered || submitting}
                >
                  <Send size={16} />
                  {submitting ? '提交中...' : '提交答案'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 结果阶段 */}
      {phase === 'result' && report && (
        <div className="result-area">
          <div className="result-header">
            <Award size={40} className="result-award" />
            <h1>评估完成！</h1>
          </div>

          {/* 核心分数 */}
          <div className="score-display">
            <div className="score-ring">
              <svg viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" strokeWidth="8" />
                <circle
                  cx="60" cy="60" r="50" fill="none"
                  stroke={report.score >= 80 ? '#10b981' : report.score >= 60 ? '#6366f1' : '#f59e0b'}
                  strokeWidth="8"
                  strokeDasharray={`${2 * Math.PI * 50}`}
                  strokeDashoffset={`${2 * Math.PI * 50 * (1 - report.score / 100)}`}
                  strokeLinecap="round"
                  transform="rotate(-90 60 60)"
                />
                <text x="60" y="65" textAnchor="middle" className="score-ring-text">{report.score}</text>
              </svg>
            </div>
            <p className="score-label">综合得分</p>
          </div>

          <div className="result-grid">
            {/* 强项 */}
            <div className="result-card result-card--green">
              <div className="result-card-title">
                <CheckCircle2 size={18} />
                <span>掌握良好</span>
              </div>
              <div className="tag-list">
                {report.strong_areas.map((a, i) => (
                  <span key={i} className="profile-tag profile-tag--green">{a}</span>
                ))}
              </div>
            </div>

            {/* 弱项 */}
            <div className="result-card result-card--orange">
              <div className="result-card-title">
                <XCircle size={18} />
                <span>需要加强</span>
              </div>
              <div className="tag-list">
                {report.weak_areas.map((a, i) => (
                  <span key={i} className="profile-tag profile-tag--red">{a}</span>
                ))}
              </div>
            </div>

            {/* 建议 */}
            <div className="result-card result-card--full">
              <div className="result-card-title">
                <TrendingUp size={18} />
                <span>个性化学习建议</span>
              </div>
              <ul className="recommendations-list">
                {report.recommendations.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* 下一步操作 */}
          <div className="next-steps-row">
            <a href="/app/resources" className="btn-next-step">
              生成专项练习
            </a>
            <button className="btn-next-step btn-secondary" onClick={() => setPhase('intro')}>
              <RefreshCw size={15} />
              再次测验
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
