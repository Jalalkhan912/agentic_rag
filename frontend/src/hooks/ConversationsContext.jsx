import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { chatApi } from '../api/client'

const ConversationsContext = createContext(null)

export function ConversationsProvider({ children }) {
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const res = await chatApi.listConversations()
      setConversations(res.data.conversations)
    } catch {
      // sidebar isn't critical — fail silently
    } finally {
      setLoading(false)
    }
  }, [])

  // Load on mount
  useEffect(() => { refresh() }, [refresh])

  return (
    <ConversationsContext.Provider value={{ conversations, loading, refresh }}>
      {children}
    </ConversationsContext.Provider>
  )
}

export function useConversations() {
  const ctx = useContext(ConversationsContext)
  if (!ctx) throw new Error('useConversations must be used inside ConversationsProvider')
  return ctx
}
