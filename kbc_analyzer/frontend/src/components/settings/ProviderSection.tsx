import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Check, CircleX, ExternalLink, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { usePatchSetting, useSettings } from "@/hooks/useSettings"
import { ApiError, testProviderConnection } from "@/lib/api"
import type { LlmProvider } from "@/lib/types"
import { cn } from "@/lib/utils"

const PROVIDERS: {
  id: LlmProvider
  label: string
  cost: string
  source: string
  keyLabel: string
  keyField: "gemini_api_key" | "anthropic_api_key"
  getKeyUrl: string
}[] = [
  {
    id: "gemini",
    label: "Gemini",
    cost: "Free",
    source: "Google AI Studio",
    keyLabel: "Gemini API Key",
    keyField: "gemini_api_key",
    getKeyUrl: "https://aistudio.google.com/app/apikey",
  },
  {
    id: "claude",
    label: "Claude",
    cost: "~€0.10/run",
    source: "Anthropic",
    keyLabel: "Anthropic API Key",
    keyField: "anthropic_api_key",
    getKeyUrl: "https://console.anthropic.com",
  },
]

export function ProviderSection() {
  const { data } = useSettings()
  const patchMutation = usePatchSetting()

  function selectProvider(id: LlmProvider) {
    if (data?.llm_provider === id) return
    patchMutation.mutate({ key: "llm_provider", value: id })
  }

  const selected = PROVIDERS.find((p) => p.id === data?.llm_provider) ?? PROVIDERS[0]
  const hasKeySaved = data ? data[selected.keyField] !== "" : false

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold text-text-primary">AI Analysis Provider</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <div className="grid grid-cols-2 gap-3">
          {PROVIDERS.map((provider) => {
            const isSelected = data?.llm_provider === provider.id
            return (
              <button
                key={provider.id}
                type="button"
                onClick={() => selectProvider(provider.id)}
                disabled={!data || patchMutation.isPending}
                className={cn(
                  "flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors",
                  isSelected ? "border-primary bg-primary/5" : "border-border hover:bg-muted"
                )}
              >
                <span className="text-sm font-semibold text-text-primary">{provider.label}</span>
                <span className="text-xs text-text-secondary">
                  {provider.cost} · {provider.source}
                </span>
                <span className="mt-1 flex items-center gap-1.5 text-xs text-text-secondary">
                  <span
                    className={cn(
                      "flex size-3.5 items-center justify-center rounded-full border",
                      isSelected ? "border-primary bg-primary text-primary-foreground" : "border-border"
                    )}
                  >
                    {isSelected && <Check className="size-2.5" />}
                  </span>
                  {isSelected ? "Selected" : "Select"}
                </span>
              </button>
            )
          })}
        </div>

        <ApiKeyForm
          key={selected.keyField}
          providerId={selected.id}
          keyLabel={selected.keyLabel}
          keyField={selected.keyField}
          hasKeySaved={hasKeySaved}
          getKeyUrl={selected.getKeyUrl}
        />
      </CardContent>
    </Card>
  )
}

function ApiKeyForm({
  providerId,
  keyLabel,
  keyField,
  hasKeySaved,
  getKeyUrl,
}: {
  providerId: LlmProvider
  keyLabel: string
  keyField: "gemini_api_key" | "anthropic_api_key"
  hasKeySaved: boolean
  getKeyUrl: string
}) {
  // Deliberately never pre-filled from the server (which only ever returns a mask,
  // never the real key) — the field starts empty every time, and Save only ever
  // submits a value the user just typed, so there's no way to accidentally
  // resubmit the mask string as if it were a real key.
  const [value, setValue] = useState("")
  const [saved, setSaved] = useState(false)
  const patchMutation = usePatchSetting()

  // Test and Save are independent actions (S3-07 Item 1) — testing never
  // touches the saved key, and its result is cleared the moment the field
  // changes so a stale "Connected" can't linger next to a since-edited key.
  const testMutation = useMutation({
    mutationFn: () => testProviderConnection(providerId, value),
  })

  function handleSave() {
    setSaved(false)
    patchMutation.mutate(
      { key: keyField, value },
      {
        onSuccess: () => {
          setValue("")
          setSaved(true)
        },
      }
    )
  }

  function handleChange(next: string) {
    setValue(next)
    setSaved(false)
    testMutation.reset()
  }

  // This mutation instance is only ever called with this component's own keyField
  // (a fresh ApiKeyForm — and fresh mutation — mounts per provider, via the `key`
  // prop in ProviderSection), so its error state is always about this field.
  const errorMessage = patchMutation.isError
    ? patchMutation.error instanceof ApiError
      ? patchMutation.error.message
      : "Couldn't save that key. Try again."
    : null

  const testResult = testMutation.data
  const testErrorMessage = testMutation.isError
    ? testMutation.error instanceof ApiError
      ? testMutation.error.message
      : "Couldn't reach the provider. Try again."
    : (testResult && !testResult.connected ? testResult.error_message : null)

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-text-primary" htmlFor={keyField}>
        {keyLabel}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={keyField}
          type="password"
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="Enter your API key..."
          className="h-9 flex-1 rounded-md border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
        <Button
          size="sm"
          variant="outline"
          onClick={() => testMutation.mutate()}
          disabled={!value || testMutation.isPending}
        >
          {testMutation.isPending ? <Loader2 className="size-3.5 animate-spin" /> : "Test connection"}
        </Button>
        <Button size="sm" onClick={handleSave} disabled={!value || patchMutation.isPending}>
          {patchMutation.isPending ? "Saving…" : "Save"}
        </Button>
        {saved && <Check className="size-4 text-success" />}
      </div>
      {testResult?.connected && (
        <p className="flex items-center gap-1.5 text-xs text-success">
          <Check className="size-3.5" />
          Connected
        </p>
      )}
      {testErrorMessage && (
        <p className="flex items-center gap-1.5 text-xs text-danger">
          <CircleX className="size-3.5" />
          {testErrorMessage}
        </p>
      )}
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-secondary">
          {hasKeySaved ? "A key is currently saved." : "No key saved yet."}
        </span>
        <a
          href={getKeyUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-primary hover:underline"
        >
          How to get this key
          <ExternalLink className="size-3" />
        </a>
      </div>
      {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
    </div>
  )
}
