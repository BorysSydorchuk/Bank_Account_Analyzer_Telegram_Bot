import { format } from "date-fns"
import ReactMarkdown from "react-markdown"

import type { ChatMessage } from "@/hooks/useChatSession"
import { cn } from "@/lib/utils"

interface MessageBubbleProps {
  message: ChatMessage
}

// One thread entry: user bubbles are plain text (never markdown — nothing
// the user typed should be reinterpreted as formatting), assistant bubbles
// render markdown and carry the streaming cursor / interrupted marker.
export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user"

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("flex max-w-[75%] flex-col gap-1", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "rounded-xl px-4 py-2.5 text-sm",
            isUser
              ? "bg-primary text-primary-foreground"
              : "border border-border bg-card text-text-primary"
          )}
        >
          {isUser ? (
            <span className="whitespace-pre-wrap">{message.content}</span>
          ) : (
            <div
              className={cn(
                "[&>*]:my-1.5 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0",
                "[&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_li]:my-0.5",
                "[&_strong]:font-semibold [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.85em]"
              )}
            >
              <ReactMarkdown>{message.content}</ReactMarkdown>
              {message.isStreaming && (
                <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-text-secondary align-middle" />
              )}
            </div>
          )}
          {message.isInterrupted && (
            <p className="mt-1.5 text-xs text-danger">Response interrupted — please try again</p>
          )}
        </div>
        <span className="px-1 text-[11px] text-text-secondary">{format(message.createdAt, "HH:mm")}</span>
      </div>
    </div>
  )
}
