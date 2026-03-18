import { useState, useEffect, useCallback, useRef } from 'react'
import { documentsApi } from '../api/client'

export function useDocuments() {
  const [documents, setDocuments] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const pollingRef = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const res = await documentsApi.list()
      setDocuments(res.data.documents)
      setTotal(res.data.total)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  // Poll while any document is still processing
  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    const hasPending = documents.some(
      (d) => d.status === 'pending' || d.status === 'processing'
    )

    if (hasPending && !pollingRef.current) {
      pollingRef.current = setInterval(refresh, 2500)
    } else if (!hasPending && pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [documents, refresh])

  const deleteDocument = useCallback(
    async (id) => {
      await documentsApi.delete(id)
      await refresh()
    },
    [refresh]
  )

  return { documents, total, loading, refresh, deleteDocument }
}
