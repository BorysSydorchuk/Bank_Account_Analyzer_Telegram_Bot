import { useState } from "react"
import { Check, ChevronDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { cn } from "@/lib/utils"

interface CategoryFilterDropdownProps {
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
}

export function CategoryFilterDropdown({ options, selected, onChange }: CategoryFilterDropdownProps) {
  const [open, setOpen] = useState(false)

  function toggle(category: string) {
    onChange(selected.includes(category) ? selected.filter((c) => c !== category) : [...selected, category])
  }

  const label = selected.length === 0 ? "All categories" : `${selected.length} categor${selected.length === 1 ? "y" : "ies"}`

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          {label}
          <ChevronDown className="size-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-1" align="start">
        {options.length === 0 ? (
          <p className="px-2 py-1.5 text-sm text-text-secondary">No categories yet</p>
        ) : (
          options.map((category) => (
            <button
              key={category}
              type="button"
              onClick={() => toggle(category)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
            >
              <span
                className={cn(
                  "flex size-4 shrink-0 items-center justify-center rounded border",
                  selected.includes(category) ? "border-primary bg-primary text-primary-foreground" : "border-border"
                )}
              >
                {selected.includes(category) && <Check className="size-3" />}
              </span>
              <span className="truncate">{category}</span>
            </button>
          ))
        )}
      </PopoverContent>
    </Popover>
  )
}
