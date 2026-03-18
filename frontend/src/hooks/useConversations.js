import { useState, useEffect, useCallback } from 'react'
import { chatApi } from '../api/client'

export function useConversations() {
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await chatApi.listConversations()
      setConversations(res.data.conversations)
    } catch {
      // silently ignore — sidebar isn't critical
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { conversations, loading, refresh }
}
