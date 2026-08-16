import { MessageCircle } from "lucide-react"

const SUGGESTIONS = [
  "How much did I spend this month?",
  "What's my biggest expense category?",
  "Am I within my budgets?",
  "Compare this month to last month",
]

interface ChatEmptyStateProps {
  onSuggestionClick: (text: string) => void
}

// Shown only before the first message — the suggestion chips pre-fill AND
// send immediately on click, not just populate the input.
export function ChatEmptyState({ onSuggestionClick }: ChatEmptyStateProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="flex flex-col items-center gap-2">
        <MessageCircle className="size-8 text-primary" />
        <h2 className="text-lg font-semibold text-text-primary">Chat with your finances</h2>
        <p className="text-sm text-text-secondary">Ask anything about your spending</p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onSuggestionClick(suggestion)}
            className="cursor-pointer rounded-full border border-border bg-card px-3.5 py-1.5 text-sm text-text-primary transition-colors hover:bg-primary/10 hover:text-primary"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}
