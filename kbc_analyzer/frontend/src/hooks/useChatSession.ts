import { useCallback, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

import { streamChat } from "@/lib/api"
import type { ChatHistoryEntry, ChatRole } from "@/lib/types"

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  createdAt: Date
  isStreaming: boolean
  isInterrupted: boolean
}

// Owns the whole /chat conversation: message list, streaming state, and the
// SSE plumbing (via lib/api.ts's streamChat). History is React state only
// (S4-06/S4-07: backend is stateless, no chat_messages table) — a page
// refresh or navigating away loses it, by design.
export function useChatSession() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const cancelRef = useRef<(() => void) | null>(null)

  // Aborts an in-flight stream on unmount so a response that arrives after
  // the user has navigated away doesn't keep writing to stale state.
  useEffect(() => () => cancelRef.current?.(), [])

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming) return

      // Prior turns only — trimmed does NOT include the new message, which
      // the backend takes as a separate field.
      const history: ChatHistoryEntry[] = messages.map((m) => ({ role: m.role, content: m.content }))

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmed,
        createdAt: new Date(),
        isStreaming: false,
        isInterrupted: false,
      }
      const assistantId = crypto.randomUUID()
      const assistantMessage: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: new Date(),
        isStreaming: true,
        isInterrupted: false,
      }

      setMessages((prev) => [...prev, userMessage, assistantMessage])
      setIsStreaming(true)

      cancelRef.current = streamChat(trimmed, history, {
        onToken: (token) => {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + token } : m)))
        },
        onDone: () => {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m)))
          setIsStreaming(false)
          cancelRef.current = null
        },
        onError: (message, hadPartialResponse) => {
          if (hadPartialResponse) {
            // Ticket: keep partial text + an inline "Response interrupted"
            // marker (rendered by MessageBubble from isInterrupted, not from
            // the raw error text — the marker copy is fixed regardless of
            // what actually failed).
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false, isInterrupted: true } : m))
            )
          } else {
            // Nothing rendered yet (e.g. no API key configured) — no empty
            // bubble to leave behind; surface the real, already
            // Settings-directing backend message as a toast instead.
            setMessages((prev) => prev.filter((m) => m.id !== assistantId))
            toast.error(message)
          }
          setIsStreaming(false)
          cancelRef.current = null
        },
      })
    },
    [messages, isStreaming]
  )

  const clearConversation = useCallback(() => {
    cancelRef.current?.()
    cancelRef.current = null
    setMessages([])
    setIsStreaming(false)
  }, [])

  return { messages, isStreaming, sendMessage, clearConversation }
}
