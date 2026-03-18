import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, BookOpen, User, FileSearch, ChevronDown, ChevronUp, Loader2, Sparkles } from 'lucide-react'
import { chatApi } from '../api/client'
import { useConversations } from '../hooks/ConversationsContext'
import styles from './ChatPage.module.css'

export default function ChatPage() {
  const { conversationId } = useParams()
  const navigate = useNavigate()

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)
  const [currentConvId, setCurrentConvId] = useState(conversationId || null)

  const { refresh: refreshSidebar } = useConversations()

  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    setCurrentConvId(conversationId || null)
    if (!conversationId) { setMessages([]); return }
    chatApi.getConversation(conversationId)
      .then(res => setMessages(res.data.messages))
      .catch(() => setMessages([]))
  }, [conversationId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }, [input])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setError(null)
    setSending(true)

    const optimistic = { id: `tmp-${Date.now()}`, role: 'user', content: text, created_at: new Date().toISOString() }
    setMessages(prev => [...prev, optimistic])

    try {
      const res = await chatApi.sendMessage(text, currentConvId)
      const { conversation_id, message, sources } = res.data
      if (!currentConvId) {
        setCurrentConvId(conversation_id)
        navigate(`/chat/${conversation_id}`, { replace: true })
        refreshSidebar()   // ← new conversation → update the sidebar immediately
      }
      setMessages(prev => [...prev, { ...message, sources }])
    } catch (err) {
      setError(err.message)
      setMessages(prev => prev.filter(m => m.id !== optimistic.id))
    } finally {
      setSending(false)
      textareaRef.current?.focus()
    }
  }, [input, sending, currentConvId, navigate])

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  const isEmpty = messages.length === 0

  return (
    <div className={styles.page}>
      {/* Top bar */}
      <div className={styles.topbar}>
        <div className={styles.topbarLeft}>
          <span className={styles.topbarTitle}>
            {isEmpty ? 'New conversation' : messages[0]?.content?.slice(0, 48) + '…'}
          </span>
        </div>
        <div className={styles.topbarRight}>
          <span className={styles.topbarBadge}>
            <Sparkles size={10} /> GPT-4o · RAG Agent
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className={styles.messages}>
        {isEmpty && <EmptyState />}

        {messages.map((msg, i) => (
          <MessageBubble key={msg.id} msg={msg} index={i} />
        ))}

        {sending && (
          <div className={`${styles.row} ${styles.assistantRow}`}>
            <div className={styles.avatar}>
              <BookOpen size={13} strokeWidth={1.5} />
            </div>
            <div className={styles.thinkingBubble}>
              <Loader2 size={13} className={styles.spin} />
              <span>Thinking</span>
              <span className={styles.thinkingDots}>
                <span>.</span><span>.</span><span>.</span>
              </span>
            </div>
          </div>
        )}

        {error && <div className={styles.errorBar}>{error}</div>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className={styles.inputWrap}>
        <div className={styles.inputShell}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about your documents…"
            rows={1}
            disabled={sending}
          />
          <button className={styles.sendBtn} onClick={sendMessage} disabled={!input.trim() || sending}>
            <Send size={14} />
          </button>
        </div>
        <p className={styles.inputHint}>
          ↵ send &nbsp;·&nbsp; ⇧↵ newline &nbsp;·&nbsp; Agent retrieves documents autonomously
        </p>
      </div>
    </div>
  )
}

/* ── Empty state ── */
function EmptyState() {
  const suggestions = [
    'Summarise the key findings in my documents',
    'What are the main topics covered?',
    'Compare the approaches described across documents',
  ]
  return (
    <div className={styles.empty}>
      <div className={styles.emptyGlyph}>
        <BookOpen size={28} strokeWidth={1} />
      </div>
      <h2 className={styles.emptyTitle}>What would you like to know?</h2>
      <p className={styles.emptySubtitle}>
        The agent searches your document library when relevant,<br />
        and answers from memory when it doesn't need to.
      </p>
      <div className={styles.suggestions}>
        {suggestions.map((s, i) => (
          <div key={i} className={styles.suggestion}>{s}</div>
        ))}
      </div>
    </div>
  )
}

/* ── Message bubble ── */
function MessageBubble({ msg, index }) {
  const isUser = msg.role === 'user'
  const sources = msg.sources || msg.retrieved_chunks || []
  const [showSources, setShowSources] = useState(false)

  return (
    <div
      className={`${styles.row} ${isUser ? styles.userRow : styles.assistantRow}`}
      style={{ animationDelay: `${index * 0.03}s` }}
    >
      <div className={styles.avatar}>
        {isUser
          ? <User size={13} strokeWidth={1.5} />
          : <BookOpen size={13} strokeWidth={1.5} />
        }
      </div>

      <div className={styles.bubbleWrap}>
        <div className={`${styles.bubble} ${isUser ? styles.userBubble : styles.assistantBubble}`}>
          {isUser
            ? <p>{msg.content}</p>
            : <div className={styles.markdown}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              </div>
          }
        </div>

        {sources.length > 0 && (
          <div className={styles.sources}>
            <button className={styles.sourcesToggle} onClick={() => setShowSources(!showSources)}>
              <FileSearch size={11} />
              <span>{sources.length} source{sources.length > 1 ? 's' : ''} retrieved</span>
              {showSources ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            </button>

            {showSources && (
              <div className={styles.sourceList}>
                {sources.map((src, i) => (
                  <div key={i} className={styles.sourceCard}>
                    <div className={styles.sourceMeta}>
                      <span className={styles.sourceDocName}>{src.document_name}</span>
                      {src.page_number && <span className={styles.sourceTag}>p.{src.page_number}</span>}
                      <span className={styles.sourceScore}>{(src.similarity_score * 100).toFixed(0)}%</span>
                    </div>
                    <p className={styles.sourceText}>{src.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
