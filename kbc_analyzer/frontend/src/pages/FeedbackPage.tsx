import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"

import { ApiError, sendFeedback } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export function FeedbackPage() {
  const [message, setMessage] = useState("")

  const feedbackMutation = useMutation({
    mutationFn: () => sendFeedback(message),
    onSuccess: () => {
      setMessage("")
      toast.success("Thanks — your feedback was sent.")
    },
    onError: (error: unknown) => {
      toast.error(error instanceof ApiError ? error.message : "Couldn't send your feedback right now.")
    },
  })

  return (
    <>
      <header className="flex items-center border-b border-border bg-card px-6 py-4">
        <h1 className="text-xl font-semibold text-text-primary">Feedback</h1>
      </header>
      <main className="flex-1 overflow-y-auto bg-background p-6">
        <div className="flex max-w-2xl flex-col gap-6">
          <Card>
            <CardHeader className="gap-1">
              <p className="text-sm text-muted-foreground">
                Found a bug, or something confusing? Send it straight to Borys.
              </p>
            </CardHeader>
            <CardContent>
              <form
                className="flex flex-col gap-3"
                onSubmit={(e) => {
                  e.preventDefault()
                  feedbackMutation.mutate()
                }}
              >
                <textarea
                  aria-label="Feedback message"
                  required
                  minLength={1}
                  maxLength={5000}
                  rows={6}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="What happened, and what did you expect instead?"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                />
                <Button
                  type="submit"
                  size="lg"
                  className="h-10 w-fit"
                  disabled={feedbackMutation.isPending || message.trim().length === 0}
                >
                  {feedbackMutation.isPending ? "Sending…" : "Send feedback"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </main>
    </>
  )
}
