import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { MessageSquare, Files, Plus, Trash2, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { chatApi } from '../../api/client'
import { useConversations } from '../../hooks/ConversationsContext'
import { formatDistanceToNow } from 'date-fns'
import styles from './Layout.module.css'

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const { conversations, refresh } = useConversations()

  async function handleNewChat() { navigate('/chat') }

  async function handleDelete(e, id) {
    e.preventDefault()
    e.stopPropagation()
    await chatApi.deleteConversation(id)
    refresh()
    navigate('/chat')
  }

  return (
    <div className={styles.shell}>
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`}>
        <div className={styles.sidebarTop}>
          {!collapsed && (
            <div className={styles.brand}>
              <span className={styles.brandMark}>Archon</span>
              <span className={styles.brandSub}>Document Intelligence</span>
            </div>
          )}
          <button className={styles.collapseBtn} onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
          </button>
        </div>

        <nav className={styles.nav}>
          <NavLink to="/chat" end className={({ isActive }) =>
            `${styles.navItem} ${isActive ? styles.active : ''}`}>
            <MessageSquare size={15} strokeWidth={1.5} />
            {!collapsed && <span>Chat</span>}
          </NavLink>
          <NavLink to="/documents" className={({ isActive }) =>
            `${styles.navItem} ${isActive ? styles.active : ''}`}>
            <Files size={15} strokeWidth={1.5} />
            {!collapsed && <span>Documents</span>}
          </NavLink>
        </nav>

        {!collapsed && (
          <>
            <button className={styles.newChat} onClick={handleNewChat}>
              <Plus size={13} /> New conversation
            </button>

            <div className={styles.convSection}>
              {conversations.length > 0 && (
                <span className={styles.convSectionLabel}>Recent</span>
              )}
              <div className={styles.convList}>
                {conversations.map((conv) => (
                  <NavLink key={conv.id} to={`/chat/${conv.id}`}
                    className={({ isActive }) =>
                      `${styles.convItem} ${isActive ? styles.activeConv : ''}`}>
                    <span className={styles.convTitle}>{conv.title}</span>
                    <span className={styles.convMeta}>
                      {formatDistanceToNow(new Date(conv.updated_at), { addSuffix: true })}
                    </span>
                    <button className={styles.deleteBtn}
                      onClick={(e) => handleDelete(e, conv.id)} title="Delete">
                      <Trash2 size={12} />
                    </button>
                  </NavLink>
                ))}
              </div>
            </div>
          </>
        )}
      </aside>

      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
