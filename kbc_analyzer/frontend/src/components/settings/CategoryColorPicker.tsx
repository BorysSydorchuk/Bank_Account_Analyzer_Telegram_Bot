import { useState, type ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { ApiError } from "@/lib/api"

interface CategoryColorPickerProps {
  color: string
  // Returning a promise (not firing a mutation and forgetting about it) is
  // what lets this component close itself on success and stay open with a
  // specific inline error on failure — see the S3-06 WHEN DONE explanation
  // for why user colors go through the exact same validate-and-reject path
  // as the AI's own colors.
  onSave: (color: string) => Promise<unknown>
  saveLabel?: string
  children: ReactNode
}

export function CategoryColorPicker({ color, onSave, saveLabel = "Save", children }: CategoryColorPickerProps) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(color)
  const [isSaving, setIsSaving] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  function handleOpenChange(next: boolean) {
    if (next) {
      setDraft(color)
      setErrorMessage(null)
    }
    setOpen(next)
  }

  async function save() {
    setIsSaving(true)
    setErrorMessage(null)
    try {
      await onSave(draft)
      setOpen(false)
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "Could not save this color.")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent className="w-60">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              aria-label="Pick a color"
              className="size-9 shrink-0 cursor-pointer rounded-md border border-border bg-transparent p-0"
            />
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="#RRGGBB"
              className="h-9 flex-1 rounded-md border border-border bg-background px-2 font-mono text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </div>
          <div className="h-8 rounded-md border border-border" style={{ backgroundColor: draft }} />
          {errorMessage && <p className="text-xs text-danger">{errorMessage}</p>}
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setOpen(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button size="sm" onClick={save} disabled={isSaving}>
              {isSaving ? "Saving…" : saveLabel}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
