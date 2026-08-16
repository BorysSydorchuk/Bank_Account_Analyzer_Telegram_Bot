import { useState } from "react"
import { ArrowUp } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const MAX_LENGTH = 500
const COUNTER_THRESHOLD = 400

interface ChatInputProps {
  disabled: boolean
  onSend: (text: string) => void
}

export function ChatInput({ disabled, onSend }: ChatInputProps) {
  const [text, setText] = useState("")

  function send() {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText("")
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="border-t border-border bg-card px-6 py-4">
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, MAX_LENGTH))}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Ask about your spending..."
            rows={2}
            className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm text-text-primary outline-none placeholder:text-text-secondary focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
          />
          {text.length > COUNTER_THRESHOLD && (
            <p
              className={cn(
                "mt-1 text-right text-xs text-text-secondary",
                text.length >= MAX_LENGTH && "text-danger"
              )}
            >
              {text.length}/{MAX_LENGTH}
            </p>
          )}
        </div>
        <Button
          type="button"
          size="icon"
          disabled={disabled || !text.trim()}
          onClick={send}
          aria-label="Send message"
        >
          <ArrowUp className="size-4" />
        </Button>
      </div>
    </div>
  )
}
