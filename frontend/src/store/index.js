/**
 * 全局状态管理 - Zustand
 * 管理用户认证、画像、对话历史、资源等全局状态
 */

import { create } from 'zustand'

const TOKEN_KEY = 'AetherStudy_token'
const USER_KEY = 'AetherStudy_user'

function loadAuth() {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    const user = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
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
      chatMessages: [], sessions: [], activeSessionId: null, activeMessages: [],
      currentResources: [], learningPath: null,
    })
  },

  userId: savedUser?.id || null,

  // ===== 聊天会话列表 =====
  sessions: [],            // SessionItem[]，侧边栏展示用
  sessionsLoaded: false,   // 是否已从后端加载过

  setSessions: (sessions) => set({ sessions, sessionsLoaded: true }),

  addSession: (session) => set(state => ({
    sessions: [session, ...state.sessions]
  })),

  removeSession: (sessionId) => set(state => ({
    sessions: state.sessions.filter(s => s.id !== sessionId),
    // 如果删除的是当前活跃会话，清空
    activeSessionId: state.activeSessionId === sessionId ? null : state.activeSessionId,
    activeMessages: state.activeSessionId === sessionId ? [] : state.activeMessages,
  })),

  updateSessionMeta: (sessionId, updates) => set(state => ({
    sessions: state.sessions.map(s =>
      s.id === sessionId ? { ...s, ...updates } : s
    )
  })),

  clearAllSessions: () => set({ sessions: [], activeSessionId: null, activeMessages: [] }),

  // ===== 当前活跃会话 =====
  activeSessionId: null,
  activeMessages: [],      // MessageItem[]（当前会话的完整消息历史）

  setActiveSession: (sessionId, messages = []) => set({
    activeSessionId: sessionId,
    activeMessages: messages,
  }),

  appendMessage: (message) => set(state => ({
    activeMessages: [...state.activeMessages, message],
  })),

  // 流式输出期间更新最后一条 AI 消息（通过 tempId 追踪）
  upsertStreamingMessage: (tempId, content) => set(state => {
    const existing = state.activeMessages.find(m => m.id === tempId)
    if (existing) {
      return {
        activeMessages: state.activeMessages.map(m =>
          m.id === tempId ? { ...m, content } : m
        )
      }
    }
    return {
      activeMessages: [...state.activeMessages, {
        id: tempId, role: 'assistant', content, created_at: new Date().toISOString()
      }]
    }
  }),

  // 流结束后用真实 ID 替换临时 ID
  finalizeStreamingMessage: (tempId, realId, finalContent) => set(state => ({
    activeMessages: state.activeMessages.map(m =>
      m.id === tempId ? { ...m, id: realId, content: finalContent } : m
    )
  })),


  // ===== 学生画像 =====
  profile: null,
  profileCompleteness: 0,

  setProfile: (newProfile) => set((state) => {
    const oldProfile = state.profile || {};
    const mergedProfile = { ...oldProfile };

    Object.keys(newProfile).forEach(key => {
      const newValue = newProfile[key];
      if (newValue !== null && newValue !== undefined) {
        mergedProfile[key] = newValue;
      }
    });
    return {
      profile: mergedProfile,
      profileCompleteness: calcCompleteness(mergedProfile)
    };
  }),

  // ===== 对话 =====
  chatMessages: [],
  chatMode: 'general',
  setChatMode: (mode) => set({ chatMode: mode }),

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
  const fields = ['major', 'cognition_style', 'description', 'learning_goals', 'weak_points', 'learning_pace', 'completed_topics']
  const filled = fields.filter(f => {
    const v = profile[f]
    return v && (Array.isArray(v) ? v.length > 0 : true)
  })
  return filled.length / fields.length
}
