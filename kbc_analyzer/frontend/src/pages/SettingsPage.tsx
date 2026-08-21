import { AccountSection } from "@/components/settings/AccountSection"
import { BankConnectionSection } from "@/components/settings/BankConnectionSection"
import { BudgetsSection } from "@/components/settings/BudgetsSection"
import { CategoriesSection } from "@/components/settings/CategoriesSection"
import { ProviderSection } from "@/components/settings/ProviderSection"

export function SettingsPage() {
  return (
    <>
      <header className="flex items-center border-b border-border bg-card px-6 py-4">
        <h1 className="text-xl font-semibold text-text-primary">Settings</h1>
      </header>
      <main className="flex-1 overflow-y-auto bg-background p-6">
        <div className="flex max-w-2xl flex-col gap-6">
          <AccountSection />
          <ProviderSection />
          <BankConnectionSection />
          <CategoriesSection />
          <BudgetsSection />
        </div>
      </main>
    </>
  )
}
