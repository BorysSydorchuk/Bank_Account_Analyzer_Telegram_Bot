import { useEffect, useRef } from "react"

import type { ChatMessage } from "@/hooks/useChatSession"
import { MessageBubble } from "./MessageBubble"

interface MessageThreadProps {
  messages: ChatMessage[]
}

export function MessageThread({ messages }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Follows the stream: re-scrolls on every token, not just when a new
  // message is added, so the latest text stays in view while it's still
  // arriving.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" })
  }, [messages])

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
