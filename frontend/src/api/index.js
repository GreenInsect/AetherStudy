/**
 * API 客户端
 * 封装所有后端接口调用，自动附带 JWT Authorization 头
 */

const BASE_URL = '/api'

/** 从 store 获取 token（避免循环依赖，直接读 localStorage）*/
function getToken() {
  return localStorage.getItem('AetherStudy_token')
}

/** 构建带鉴权的请求头 */
function authHeaders(extra = {}) {
  const token = getToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

function bearerHeaders(extra = {}) {
  const token = getToken()
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

/** 通用 JSON fetch，自动处理 401 */
async function apiFetch(path, options = {}) {
  console.debug('[AetherStudy API]', 'request', {
    path,
    method: options.method || 'GET',
    hasBody: Boolean(options.body),
  })
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  })
  console.debug('[AetherStudy API]', 'response', {
    path,
    status: res.status,
    ok: res.ok,
    contentType: res.headers.get('content-type'),
  })
  if (res.status === 401) {
    // Token 失效，清除本地认证并跳转登录
    localStorage.removeItem('AetherStudy_token')
    localStorage.removeItem('AetherStudy_user')
    window.location.href = '/login'
    return
  }
  return res
}

function formatApiError(detail, fallback) {
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  const message = detail.message || fallback
  return `${message}\n${JSON.stringify(detail, null, 2)}`
}

// ===== 认证 API =====

export async function apiRegister(username, email, password, confirmPassword) {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username, email,
      password, confirm_password: confirmPassword
    }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '注册失败')
  return data   // TokenResponse
}

export async function apiLogin(identifier, password) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, password }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '登录失败')
  return data   // TokenResponse
}

export async function apiLogout() {
  const res = await apiFetch('/auth/logout', { method: 'POST' })
  return res?.json()
}

export async function apiGetMe() {
  const res = await apiFetch('/auth/me')
  return res?.json()
}

export async function apiUpdateMe(fields) {
  const res = await apiFetch('/auth/me', {
    method: 'PATCH',
    body: JSON.stringify(fields),
  })
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '更新失败')
  return data
}

export async function apiGetLLMSettings() {
  const res = await apiFetch('/auth/me/llm-settings')
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '获取模型配置失败')
  return data
}

export async function apiUpdateLLMSettings(settings) {
  const res = await apiFetch('/auth/me/llm-settings', {
    method: 'PATCH',
    body: JSON.stringify(settings),
  })
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '保存模型配置失败')
  return data
}

export async function apiChangePassword(oldPassword, newPassword, confirmNewPassword) {
  const res = await apiFetch('/auth/me/password', {
    method: 'PATCH',
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
      confirm_new_password: confirmNewPassword,
    }),
  })
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '修改密码失败')
  return data
}

export async function apiDeleteMe() {
  const res = await apiFetch('/auth/me', { method: 'DELETE' })
  return res?.json()
}

// ===== 管理员 API =====

export async function apiListUsers(skip = 0, limit = 50) {
  const res = await apiFetch(`/auth/users?skip=${skip}&limit=${limit}`)
  return res?.json()
}

export async function apiToggleUserStatus(userId, isActive) {
  const res = await apiFetch(`/auth/users/${userId}/status?is_active=${isActive}`, {
    method: 'PATCH',
  })
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '操作失败')
  return data
}

export async function apiAdminDeleteUser(userId) {
  const res = await apiFetch(`/auth/users/${userId}`, { method: 'DELETE' })
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '删除失败')
  return data
}

// ===== 对话 API =====

export async function* streamChat(userId, messages, mode = 'general', profileContext = null) {
  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ user_id: userId, messages, mode, profile_context: profileContext })
  })
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value)
    const lines = chunk.split('\n').filter(l => l.startsWith('data: '))
    for (const line of lines) {
      try { yield JSON.parse(line.slice(6)) } catch {}
    }
  }
}

// ===== 画像 API =====

export async function getProfile(userId) {
  const res = await apiFetch(`/profile/${userId}`)
  return res?.json()
}

export async function getMyProfile() {
  const res = await apiFetch('/profile/me')
  return res?.json()
}

export async function updateProfile(userId, conversationText, extractedFeatures) {
  const res = await apiFetch('/profile/update', {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId,
      conversation_text: conversationText,
      extracted_features: extractedFeatures
    }),
  })
  return res?.json()
}

// ===== 资源生成 API =====

export async function* streamGenerateResources(userId, topic, resourceTypes, course = '', difficulty = 'medium') {
  const response = await fetch(`${BASE_URL}/resources/generate/stream`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ user_id: userId, topic, resource_types: resourceTypes, course, difficulty })
  })
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value)
    const lines = chunk.split('\n').filter(l => l.startsWith('data: '))
    for (const line of lines) {
      try { yield JSON.parse(line.slice(6)) } catch {}
    }
  }
}

export async function getResourceTypes() {
  const res = await apiFetch('/resources/types')
  return res?.json()
}

// ===== 学习路径 API =====

export async function generateLearningPath(userId, course) {
  const res = await apiFetch(`/learning-path/generate?user_id=${userId}&course=${encodeURIComponent(course)}`, {
    method: 'POST',
  })
  return res?.json()
}

export async function updateLearningProgress(userId, stepNo, status) {
  const res = await apiFetch(`/learning-path/${userId}/progress`, {
    method: 'PATCH',
    body: JSON.stringify({ step_no: stepNo, status }),
  })
  return res?.json()
}

// ===== 评估 API =====

export async function submitQuiz(userId, quizResourceId, answers) {
  const res = await apiFetch('/assessment/submit-quiz', {
    method: 'POST',
    body: JSON.stringify({ user_id: userId, quiz_resource_id: quizResourceId, answers }),
  })
  return res?.json()
}

// ===== 学科资料库 / RAG 题库 API =====

export async function apiListSubjects() {
  const res = await apiFetch('/study/subjects')
  return res?.json()
}

export async function apiCreateSubject(name, description = '') {
  const res = await apiFetch('/study/subjects', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  })
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '创建学科失败')
  return data
}

export async function apiListSubjectDocuments(subjectId) {
  const res = await apiFetch(`/study/subjects/${subjectId}/documents`)
  return res?.json()
}

export async function apiDeleteSubjectDocument(documentId) {
  const res = await apiFetch(`/study/documents/${documentId}`, {
    method: 'DELETE',
  })
  const data = await res?.json()
  if (!res?.ok) throw new Error(formatApiError(data?.detail, '删除资料失败'))
  return data
}

export async function apiStudyDebugLog(step, data = {}) {
  try {
    console.debug('[AetherStudy RAG]', step, data)
    await fetch(`${BASE_URL}/study/debug-log`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ step, data }),
    })
  } catch (e) {
    console.debug('[AetherStudy RAG]', 'debug_log_failed', e)
  }
}

export async function apiUploadSubjectDocument(subjectId, file) {
  const form = new FormData()
  form.append('file', file)
  console.debug('[AetherStudy RAG]', 'upload_document_request', {
    subjectId,
    filename: file?.name,
    size: file?.size,
    type: file?.type,
  })
  const res = await fetch(`${BASE_URL}/study/subjects/${subjectId}/documents`, {
    method: 'POST',
    headers: bearerHeaders(),
    body: form,
  })
  if (res.status === 401) {
    localStorage.removeItem('AetherStudy_token')
    localStorage.removeItem('AetherStudy_user')
    window.location.href = '/login'
    return
  }
  const data = await res.json()
  console.debug('[AetherStudy RAG]', 'upload_document_response', {
    status: res.status,
    ok: res.ok,
    data,
  })
  if (!res.ok) throw new Error(formatApiError(data.detail, '上传资料失败'))
  return data
}

export async function apiGenerateStudyQuiz(payload) {
  console.debug('[AetherStudy RAG]', 'generate_quiz_request', payload)
  const res = await apiFetch('/study/quizzes/generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  const data = await res?.json()
  console.debug('[AetherStudy RAG]', 'generate_quiz_response', {
    status: res?.status,
    ok: res?.ok,
    data,
  })
  if (!res?.ok) throw new Error(formatApiError(data?.detail, '生成题目失败'))
  return data
}

export async function apiListStudyQuizzes(subjectId = '') {
  const suffix = subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : ''
  const res = await apiFetch(`/study/quizzes${suffix}`)
  return res?.json()
}

export async function apiGetStudyQuiz(quizId) {
  const res = await apiFetch(`/study/quizzes/${quizId}`)
  const data = await res?.json()
  if (!res?.ok) throw new Error(data?.detail || '获取题目失败')
  return data
}

export async function apiDeleteStudyQuiz(quizId) {
  const res = await apiFetch(`/study/quizzes/${quizId}`, {
    method: 'DELETE',
  })
  const data = await res?.json()
  if (!res?.ok) throw new Error(formatApiError(data?.detail, '删除历史题目失败'))
  return data
}

// ===== 聊天会话 API =====

export async function apiListSessions() {
  const res = await apiFetch('/chat/sessions')
  return res?.json()
}

export async function apiCreateSession(mode = 'general', title = '新对话') {
  const res = await apiFetch('/chat/sessions', {
    method: 'POST',
    body: JSON.stringify({ mode, title }),
  })
  return res?.json()
}

export async function apiGetSession(sessionId) {
  const res = await apiFetch(`/chat/sessions/${sessionId}`)
  return res?.json()
}

export async function apiRenameSession(sessionId, title) {
  const res = await apiFetch(`/chat/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
  return res?.json()
}

export async function apiDeleteSession(sessionId) {
  const res = await apiFetch(`/chat/sessions/${sessionId}`, { method: 'DELETE' })
  return res?.json()
}

export async function apiClearAllSessions() {
  const res = await apiFetch('/chat/sessions', { method: 'DELETE' })
  return res?.json()
}

export async function* streamChatMessage(sessionId, content, mode = 'general') {
  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ session_id: sessionId, content, mode }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || '发送失败')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value)
    const lines = chunk.split('\n').filter(l => l.startsWith('data: '))
    for (const line of lines) {
      try { yield JSON.parse(line.slice(6)) } catch {}
    }
  }
}
