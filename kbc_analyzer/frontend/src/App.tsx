import { Sidebar } from "@/components/layout/Sidebar"
import { TopBar } from "@/components/layout/TopBar"

function App() {
  return (
    <>
      {/* Sprint 1 targets 1024px+ only; below that, a plain message rather
          than a half-broken layout. Tailwind's `lg` breakpoint is 1024px,
          so it lines up exactly with the ticket's minimum width. */}
      <div className="hidden h-screen bg-background font-sans lg:flex">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1 overflow-y-auto bg-background p-6">
            {/* S1-05 through S1-08 mount here */}
          </main>
        </div>
      </div>

      <div className="flex h-screen items-center justify-center bg-background p-6 text-center lg:hidden">
        <p className="text-text-secondary">
          This dashboard is best viewed on a desktop screen (1024px or wider).
        </p>
      </div>
    </>
  )
}

export default App
