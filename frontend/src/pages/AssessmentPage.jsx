import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Database,
  Eye,
  FileText,
  Globe2,
  History,
  Loader2,
  Plus,
  Trash2,
  Upload,
  Wand2,
} from 'lucide-react'
import {
  apiCreateSubject,
  apiDeleteStudyQuiz,
  apiDeleteSubjectDocument,
  apiGenerateStudyQuiz,
  apiGetStudyQuiz,
  apiListStudyQuizzes,
  apiListSubjectDocuments,
  apiListSubjects,
  apiStudyDebugLog,
  apiUploadSubjectDocument,
} from '../api'

const QUESTION_TYPES = [
  { id: 'single_choice', label: '单选题' },
  { id: 'multiple_choice', label: '多选题' },
  { id: 'true_false', label: '判断题' },
  { id: 'fill_blank', label: '填空题' },
  { id: 'short_answer', label: '简答题' },
  { id: 'mixed', label: '混合题型' },
]

const DIFFICULTIES = [
  { id: 'easy', label: '入门' },
  { id: 'medium', label: '中级' },
  { id: 'hard', label: '进阶' },
]

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function typeLabel(type) {
  return QUESTION_TYPES.find(item => item.id === type)?.label || type
}

function difficultyLabel(difficulty) {
  return DIFFICULTIES.find(item => item.id === difficulty)?.label || difficulty
}

function answerText(answer) {
  if (Array.isArray(answer)) return answer.join('、')
  if (typeof answer === 'boolean') return answer ? '正确' : '错误'
  return String(answer ?? '')
}

export default function AssessmentPage() {
  const [subjects, setSubjects] = useState([])
  const [selectedSubjectId, setSelectedSubjectId] = useState('')
  const [documents, setDocuments] = useState([])
  const [history, setHistory] = useState([])
  const [currentQuiz, setCurrentQuiz] = useState(null)
  const [newSubjectName, setNewSubjectName] = useState('')
  const [newSubjectDesc, setNewSubjectDesc] = useState('')
  const [topic, setTopic] = useState('')
  const [questionType, setQuestionType] = useState('single_choice')
  const [count, setCount] = useState(5)
  const [difficulty, setDifficulty] = useState('medium')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const selectedSubject = useMemo(
    () => subjects.find(subject => subject.id === selectedSubjectId),
    [subjects, selectedSubjectId],
  )

  const loadSubjects = async () => {
    await apiStudyDebugLog('load_subjects_start', {
      selectedBefore: selectedSubjectId,
    })
    const data = await apiListSubjects()
    const list = data?.subjects || []
    await apiStudyDebugLog('load_subjects_done', {
      subjectCount: list.length,
      selectedBefore: selectedSubjectId,
      firstSubjectId: list[0]?.id || null,
      subjects: list.map(subject => ({
        id: subject.id,
        name: subject.name,
        documentCount: subject.document_count,
        quizCount: subject.quiz_count,
      })),
    })
    setSubjects(list)
    setSelectedSubjectId(prev => prev || list[0]?.id || '')
  }

  const loadSubjectData = async (subjectId) => {
    await apiStudyDebugLog('load_subject_data_start', { subjectId })
    if (!subjectId) {
      setDocuments([])
      setHistory([])
      await apiStudyDebugLog('load_subject_data_skipped', { reason: 'empty_subject_id' })
      return
    }
    const [docsData, quizzesData] = await Promise.all([
      apiListSubjectDocuments(subjectId),
      apiListStudyQuizzes(subjectId),
    ])
    await apiStudyDebugLog('load_subject_data_done', {
      subjectId,
      documentCount: docsData?.documents?.length || 0,
      quizCount: quizzesData?.quizzes?.length || 0,
      documents: (docsData?.documents || []).map(doc => ({
        id: doc.id,
        filename: doc.filename,
        fileType: doc.file_type,
        charCount: doc.char_count,
      })),
    })
    setDocuments(docsData?.documents || [])
    setHistory(quizzesData?.quizzes || [])
  }

  useEffect(() => {
    loadSubjects().catch(e => setError(e.message || '加载学科失败'))
  }, [])

  useEffect(() => {
    loadSubjectData(selectedSubjectId).catch(e => setError(e.message || '加载资料失败'))
  }, [selectedSubjectId])

  const createSubject = async () => {
    if (!newSubjectName.trim()) return
    setBusy('subject')
    setError('')
    try {
      await apiStudyDebugLog('create_subject_start', {
        name: newSubjectName.trim(),
        descriptionChars: newSubjectDesc.trim().length,
      })
      const created = await apiCreateSubject(newSubjectName.trim(), newSubjectDesc.trim())
      await apiStudyDebugLog('create_subject_done', created)
      setNewSubjectName('')
      setNewSubjectDesc('')
      await loadSubjects()
      setSelectedSubjectId(created.id)
    } catch (e) {
      await apiStudyDebugLog('create_subject_error', {
        message: e.message,
        stack: e.stack,
      })
      setError(e.message || '创建学科失败')
    } finally {
      setBusy('')
    }
  }

  const uploadFiles = async (event) => {
    const files = Array.from(event.target.files || [])
    if (!selectedSubjectId || files.length === 0) return
    setBusy('upload')
    setError('')
    try {
      await apiStudyDebugLog('upload_files_start', {
        selectedSubjectId,
        fileCount: files.length,
        files: files.map(file => ({
          name: file.name,
          size: file.size,
          type: file.type,
          lastModified: file.lastModified,
        })),
      })
      for (const file of files) {
        await apiStudyDebugLog('upload_file_before_api', {
          selectedSubjectId,
          name: file.name,
          size: file.size,
          type: file.type,
        })
        const uploaded = await apiUploadSubjectDocument(selectedSubjectId, file)
        await apiStudyDebugLog('upload_file_after_api', uploaded)
      }
      await loadSubjectData(selectedSubjectId)
      await loadSubjects()
      await apiStudyDebugLog('upload_files_done', { selectedSubjectId, fileCount: files.length })
    } catch (e) {
      await apiStudyDebugLog('upload_files_error', {
        selectedSubjectId,
        message: e.message,
        stack: e.stack,
      })
      setError(e.message || '上传资料失败')
    } finally {
      event.target.value = ''
      setBusy('')
    }
  }

  const generateQuiz = async () => {
    if (!selectedSubjectId || !topic.trim()) return
    setBusy('generate')
    setError('')
    const payload = {
      subject_id: selectedSubjectId,
      topic: topic.trim(),
      question_type: questionType,
      count: Number(count),
      difficulty,
    }
    try {
      await apiStudyDebugLog('generate_quiz_start', {
        payload,
        selectedSubjectName: selectedSubject?.name || null,
        documentCount: documents.length,
        documents: documents.map(doc => ({
          id: doc.id,
          filename: doc.filename,
          fileType: doc.file_type,
          charCount: doc.char_count,
        })),
      })
      const quiz = await apiGenerateStudyQuiz(payload)
      await apiStudyDebugLog('generate_quiz_done', {
        quizId: quiz.id,
        questionCount: quiz.questions?.length || 0,
        localSourceCount: quiz.local_sources?.length || 0,
        webSourceCount: quiz.web_sources?.length || 0,
        webSources: (quiz.web_sources || []).map(source => ({
          title: source.title,
          url: source.url,
        })),
      })
      setCurrentQuiz(quiz)
      await loadSubjectData(selectedSubjectId)
      await loadSubjects()
    } catch (e) {
      await apiStudyDebugLog('generate_quiz_error', {
        payload,
        selectedSubjectName: selectedSubject?.name || null,
        documentCount: documents.length,
        message: e.message,
        stack: e.stack,
      })
      setError(e.message || '生成题目失败')
    } finally {
      setBusy('')
    }
  }

  const openHistory = async (quizId) => {
    setBusy(`history-${quizId}`)
    setError('')
    try {
      const quiz = await apiGetStudyQuiz(quizId)
      setCurrentQuiz(quiz)
    } catch (e) {
      setError(e.message || '打开历史题目失败')
    } finally {
      setBusy('')
    }
  }

  const deleteDocument = async (doc) => {
    if (!window.confirm(`确定删除资料「${doc.filename}」吗？本地文件和向量索引会一起删除。`)) return
    setBusy(`delete-doc-${doc.id}`)
    setError('')
    try {
      await apiStudyDebugLog('delete_document_start', {
        documentId: doc.id,
        filename: doc.filename,
        subjectId: selectedSubjectId,
      })
      await apiDeleteSubjectDocument(doc.id)
      await apiStudyDebugLog('delete_document_done', { documentId: doc.id })
      await loadSubjectData(selectedSubjectId)
      await loadSubjects()
    } catch (e) {
      await apiStudyDebugLog('delete_document_error', {
        documentId: doc.id,
        message: e.message,
        stack: e.stack,
      })
      setError(e.message || '删除资料失败')
    } finally {
      setBusy('')
    }
  }

  const deleteQuiz = async (item) => {
    if (!window.confirm(`确定删除历史题目「${item.title}」吗？`)) return
    setBusy(`delete-quiz-${item.id}`)
    setError('')
    try {
      await apiStudyDebugLog('delete_quiz_start', {
        quizId: item.id,
        title: item.title,
        subjectId: item.subject_id,
      })
      await apiDeleteStudyQuiz(item.id)
      await apiStudyDebugLog('delete_quiz_done', { quizId: item.id })
      if (currentQuiz?.id === item.id) setCurrentQuiz(null)
      await loadSubjectData(selectedSubjectId)
      await loadSubjects()
    } catch (e) {
      await apiStudyDebugLog('delete_quiz_error', {
        quizId: item.id,
        message: e.message,
        stack: e.stack,
      })
      setError(e.message || '删除历史题目失败')
    } finally {
      setBusy('')
    }
  }

  const canGenerate = selectedSubjectId && topic.trim() && documents.length > 0 && busy !== 'generate'

  return (
    <div className="study-page">
      <section className="study-hero">
        <div className="study-hero-copy">
          <div className="study-eyebrow">
            <Database size={16} />
            <span>本地资料 + 联网资料共同出题</span>
          </div>
          <h1>学科题库生成</h1>
          <p>先按学科上传 Markdown 或 PDF 资料，再指定题型和数量生成题目。题目会保存到本地历史，答案默认隐藏。</p>
        </div>
        <div className="study-hero-stats">
          <div>
            <strong>{subjects.length}</strong>
            <span>学科</span>
          </div>
          <div>
            <strong>{documents.length}</strong>
            <span>当前资料</span>
          </div>
          <div>
            <strong>{history.length}</strong>
            <span>历史题组</span>
          </div>
        </div>
      </section>

      {error && (
        <div className="study-alert">
          <AlertCircle size={17} />
          <pre className="study-error-text">{error}</pre>
        </div>
      )}

      <div className="study-grid">
        <aside className="study-sidebar-panel">
          <div className="study-panel-title">
            <BookOpen size={18} />
            <span>学科</span>
          </div>

          <div className="subject-create-box">
            <input
              className="form-input"
              placeholder="新增学科，如机器学习"
              value={newSubjectName}
              onChange={e => setNewSubjectName(e.target.value)}
            />
            <input
              className="form-input"
              placeholder="简介，可选"
              value={newSubjectDesc}
              onChange={e => setNewSubjectDesc(e.target.value)}
            />
            <button className="btn-study-secondary" onClick={createSubject} disabled={!newSubjectName.trim() || busy === 'subject'}>
              {busy === 'subject' ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
              创建学科
            </button>
          </div>

          <div className="subject-list">
            {subjects.map(subject => (
              <button
                key={subject.id}
                className={`subject-item ${subject.id === selectedSubjectId ? 'subject-item--active' : ''}`}
                onClick={() => setSelectedSubjectId(subject.id)}
              >
                <span>{subject.name}</span>
                <small>{subject.document_count || 0} 份资料 · {subject.quiz_count || 0} 套题</small>
              </button>
            ))}
            {subjects.length === 0 && <p className="study-empty-small">先创建一个学科。</p>}
          </div>
        </aside>

        <main className="study-main-panel">
          <section className="study-card">
            <div className="study-card-header">
              <div>
                <h2>{selectedSubject?.name || '请选择学科'}</h2>
                <p>上传资料后才能生成题目；出题时会强制同时使用本地资料和联网资料。</p>
              </div>
              <label className={`btn-study-upload ${!selectedSubjectId ? 'disabled' : ''}`}>
                {busy === 'upload' ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
                上传资料
                <input
                  type="file"
                  accept=".md,.markdown,.txt,.pdf"
                  multiple
                  disabled={!selectedSubjectId || busy === 'upload'}
                  onChange={uploadFiles}
                />
              </label>
            </div>

            <div className="document-list">
              {documents.map(doc => (
                <div key={doc.id} className="document-chip">
                  <FileText size={15} />
                  <span>{doc.filename}</span>
                  <small>
                    {doc.file_type.toUpperCase()} · {doc.char_count} 字符 · {doc.chunk_count || 0} 块
                    {doc.vector_index_ready ? ' · 向量已建' : ' · 待建向量'}
                  </small>
                  <button
                    type="button"
                    className="study-icon-danger"
                    title="删除资料"
                    disabled={busy === `delete-doc-${doc.id}`}
                    onClick={() => deleteDocument(doc)}
                  >
                    {busy === `delete-doc-${doc.id}` ? <Loader2 size={13} className="spin" /> : <Trash2 size={13} />}
                  </button>
                </div>
              ))}
              {selectedSubjectId && documents.length === 0 && (
                <p className="study-empty-small">暂无资料。支持 md、markdown、txt、PDF。</p>
              )}
            </div>
          </section>

          <section className="study-card">
            <div className="study-card-header">
              <div>
                <h2>生成题目</h2>
                <p>题型和数量由你指定，生成结果自动进入历史记录。</p>
              </div>
            </div>

            <div className="quiz-builder-grid">
              <div className="form-field">
                <label>考查主题 *</label>
                <input
                  className="form-input"
                  placeholder="例如：决策树、反向传播、贝叶斯公式"
                  value={topic}
                  onChange={e => setTopic(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label>题型</label>
                <select className="form-select" value={questionType} onChange={e => setQuestionType(e.target.value)}>
                  {QUESTION_TYPES.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </div>
              <div className="form-field">
                <label>数量</label>
                <input
                  className="form-input"
                  type="number"
                  min="1"
                  max="30"
                  value={count}
                  onChange={e => setCount(e.target.value)}
                />
              </div>
              <div className="form-field">
                <label>难度</label>
                <select className="form-select" value={difficulty} onChange={e => setDifficulty(e.target.value)}>
                  {DIFFICULTIES.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </div>
            </div>

            <button className="btn-study-primary" onClick={generateQuiz} disabled={!canGenerate}>
              {busy === 'generate' ? <Loader2 size={17} className="spin" /> : <Wand2 size={17} />}
              {busy === 'generate' ? '正在查询资料并生成...' : '生成并保存题目'}
            </button>
          </section>

          {currentQuiz ? <QuizViewer quiz={currentQuiz} /> : (
            <section className="study-empty-state">
              <Wand2 size={42} />
              <h3>还没有当前题组</h3>
              <p>选择学科、上传资料，然后生成题目。</p>
            </section>
          )}
        </main>

        <aside className="study-history-panel">
          <div className="study-panel-title">
            <History size={18} />
            <span>历史题目</span>
          </div>
          <div className="history-list">
            {history.map(item => (
              <div key={item.id} className="history-item-row">
                <button className="history-item history-item-main" onClick={() => openHistory(item.id)}>
                  <span>{item.title}</span>
                  <small>{typeLabel(item.question_type)} · {item.count}题 · {formatTime(item.created_at)}</small>
                  {busy === `history-${item.id}` && <Loader2 size={14} className="spin" />}
                </button>
                <button
                  type="button"
                  className="study-icon-danger"
                  title="删除历史题目"
                  disabled={busy === `delete-quiz-${item.id}`}
                  onClick={() => deleteQuiz(item)}
                >
                  {busy === `delete-quiz-${item.id}` ? <Loader2 size={13} className="spin" /> : <Trash2 size={13} />}
                </button>
              </div>
            ))}
            {history.length === 0 && <p className="study-empty-small">暂无历史题目。</p>}
          </div>
        </aside>
      </div>
    </div>
  )
}

function QuizViewer({ quiz }) {
  return (
    <section className="study-card quiz-viewer">
      <div className="study-card-header">
        <div>
          <h2>{quiz.title}</h2>
          <p>{quiz.subject_name} · {typeLabel(quiz.question_type)} · {quiz.count}题 · {difficultyLabel(quiz.difficulty)}</p>
        </div>
        <div className="quiz-source-badge">
          <Globe2 size={15} />
          <span>{quiz.web_sources?.length || 0} 个联网来源</span>
        </div>
      </div>

      <div className="source-strip">
        <div>
          <strong>本地资料</strong>
          {(quiz.local_sources || []).slice(0, 3).map(source => (
            <span key={`${source.document_id}-${source.filename}`}>{source.filename}</span>
          ))}
        </div>
        <div>
          <strong>联网资料</strong>
          {(quiz.web_sources || []).slice(0, 3).map(source => (
            <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
          ))}
        </div>
      </div>

      <div className="generated-question-list">
        {(quiz.questions || []).map(question => (
          <QuestionCard key={question.id} question={question} />
        ))}
      </div>
    </section>
  )
}

function QuestionCard({ question }) {
  const [showAnswer, setShowAnswer] = useState(false)

  return (
    <article className="generated-question-card">
      <div className="generated-question-head">
        <span>Q{question.seq_no}</span>
        <small>{typeLabel(question.type)}</small>
      </div>
      <p className="generated-question-prompt">{question.prompt}</p>

      {question.options?.length > 0 && (
        <div className="generated-options">
          {question.options.map((option, index) => (
            <div key={option} className="generated-option">
              <span>{String.fromCharCode(65 + index)}</span>
              <p>{option}</p>
            </div>
          ))}
        </div>
      )}

      <button className="answer-toggle" onClick={() => setShowAnswer(v => !v)}>
        {showAnswer ? <ChevronDown size={15} /> : <Eye size={15} />}
        {showAnswer ? '隐藏答案' : '查看答案'}
      </button>

      {showAnswer && (
        <div className="answer-panel">
          <div className="answer-line">
            <CheckCircle2 size={16} />
            <strong>答案：{answerText(question.answer)}</strong>
          </div>
          <p>{question.explanation}</p>
          <div className="citation-grid">
            <span><FileText size={14} />{question.local_citation}</span>
            <span><Globe2 size={14} />{question.web_citation}</span>
          </div>
        </div>
      )}
    </article>
  )
}
