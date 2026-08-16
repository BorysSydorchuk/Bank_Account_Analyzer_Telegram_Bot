import { Button } from "@/components/ui/button"
import { ChatEmptyState } from "@/components/chat/ChatEmptyState"
import { ChatInput } from "@/components/chat/ChatInput"
import { MessageThread } from "@/components/chat/MessageThread"
import { useChatSession } from "@/hooks/useChatSession"

export function ChatPage() {
  const { messages, isStreaming, sendMessage, clearConversation } = useChatSession()
  const isEmpty = messages.length === 0

  return (
    <>
      <header className="flex items-center justify-between border-b border-border bg-card px-6 py-4">
        <h1 className="text-xl font-semibold text-text-primary">Chat</h1>
        {!isEmpty && (
          <Button variant="outline" size="sm" onClick={clearConversation}>
            Clear conversation
          </Button>
        )}
      </header>
      <main className="flex min-h-0 flex-1 flex-col bg-background">
        {isEmpty ? <ChatEmptyState onSuggestionClick={sendMessage} /> : <MessageThread messages={messages} />}
        <ChatInput disabled={isStreaming} onSend={sendMessage} />
      </main>
    </>
  )
}
