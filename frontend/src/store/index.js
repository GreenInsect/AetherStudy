/**
 * 全局状态管理 - Zustand
 * 管理用户认证、画像、对话历史、资源等全局状态
 */

import { create } from 'zustand'

const TOKEN_KEY = 'edumind_token'
const USER_KEY  = 'edumind_user'

function loadAuth() {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    const user  = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
    return { token, user }
  } catch {
    return { token: null, user: null }
  }
}

const { token: savedToken, user: savedUser } = loadAuth()

export const useAppStore = create((set, get) => ({
  // ===== 用户认证 =====
  token: savedToken,
  user: savedUser,
  isAuthenticated: !!savedToken,

  setAuth: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    set({ token, user, isAuthenticated: true, userId: user.id })
  },

  clearAuth: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    set({
      token: null, user: null, isAuthenticated: false,
      userId: null, profile: null, profileCompleteness: 0,
      chatMessages: [], currentResources: [], learningPath: null,
    })
  },

  userId: savedUser?.id || null,

  // ===== 学生画像 =====
  profile: null,
  profileCompleteness: 0,

  setProfile: (profile) => set({
    profile,
    profileCompleteness: calcCompleteness(profile)
  }),

  // ===== 对话 =====
  chatMessages: [],
  chatMode: 'general',

  addChatMessage: (msg) => set(state => ({
    chatMessages: [...state.chatMessages, msg]
  })),

  clearChat: () => set({ chatMessages: [] }),

  setChatMode: (mode) => set({ chatMode: mode }),

  // ===== 资源生成 =====
  generationTasks: {},
  currentResources: [],

  addGenerationTask: (taskId, task) => set(state => ({
    generationTasks: { ...state.generationTasks, [taskId]: task }
  })),

  updateGenerationTask: (taskId, updates) => set(state => ({
    generationTasks: {
      ...state.generationTasks,
      [taskId]: { ...state.generationTasks[taskId], ...updates }
    }
  })),

  addResource: (resource) => set(state => ({
    currentResources: [...state.currentResources, resource]
  })),

  clearResources: () => set({ currentResources: [] }),

  // ===== 学习路径 =====
  learningPath: null,
  setLearningPath: (path) => set({ learningPath: path }),

  // ===== UI状态 =====
  sidebarOpen: true,
  toggleSidebar: () => set(state => ({ sidebarOpen: !state.sidebarOpen })),

  activeResourceType: null,
  setActiveResourceType: (type) => set({ activeResourceType: type }),
}))


function calcCompleteness(profile) {
  if (!profile) return 0
  const fields = ['major', 'cognition_style', 'learning_goals', 'weak_points', 'learning_pace', 'completed_topics']
  const filled = fields.filter(f => {
    const v = profile[f]
    return v && (Array.isArray(v) ? v.length > 0 : true)
  })
  return filled.length / fields.length
}
