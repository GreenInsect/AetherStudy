import { useEffect } from 'react'
import { useAppStore } from '../store'
import { getProfile } from '../api'

// 初始化逻辑组件
function AppInitializer({ children }) {
  const { token, userId, profile, setProfile, clearAuth } = useAppStore()

  useEffect(() => {
    const initData = async () => {
      // 只有当有登录令牌且本地 profile 为空时才去拉取
      if (token && userId && !profile) {
        try {
          console.log('正在自动同步学习画像...')
          const data = await getProfile(userId)
          console.log('自动同步画像数据:', data)  // 调试日志
          if (data) {
            setProfile(data.profile)
          }
        } catch (err) {
          console.error('自动同步画像失败:', err)
          // 如果后端返回 401 说明 token 失效了，清理掉本地过期的登录信息
          if (err.status === 401) {
            clearAuth()
          }
        }
      }
    }

    initData()
  }, [token, userId, profile, setProfile, clearAuth])

  return children
}
export default AppInitializer