/**
 * API 客户端
 * 封装所有后端接口调用，自动附带 JWT Authorization 头
 */

const BASE_URL = '/api'

/** 从 store 获取 token（避免循环依赖，直接读 localStorage）*/
function getToken() {
  return localStorage.getItem('edumind_token')
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

/** 通用 JSON fetch，自动处理 401 */
async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  })
  if (res.status === 401) {
    // Token 失效，清除本地认证并跳转登录
    localStorage.removeItem('edumind_token')
    localStorage.removeItem('edumind_user')
    window.location.href = '/login'
    return
  }
  return res
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
