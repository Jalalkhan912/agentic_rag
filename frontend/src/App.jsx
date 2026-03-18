import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ConversationsProvider } from './hooks/ConversationsContext'
import Layout from './components/layout/Layout'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'

export default function App() {
  return (
    <BrowserRouter>
      <ConversationsProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:conversationId" element={<ChatPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
          </Route>
        </Routes>
      </ConversationsProvider>
    </BrowserRouter>
  )
}
