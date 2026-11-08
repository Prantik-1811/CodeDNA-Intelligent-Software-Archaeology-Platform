import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import BranchTree, { type BranchHistory } from "@/components/BranchTree"
import LineSidebar from "@/components/LineSidebar"
import PixelBlast from "@/components/PixelBlast"
import FileAnalysis from "@/components/FileAnalysis"
import ChangeImpactRisk from "@/components/ChangeImpactRisk"
import MergeConflictAnalysis from "@/components/MergeConflictAnalysis"
import ProfileCard from "@/components/ProfileCard"

export function App() {
  const [showAnalyzer, setShowAnalyzer] = useState(false)
  const [repoUrl, setRepoUrl] = useState("")
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle")
  const [message, setMessage] = useState("")
  const [dashboard, setDashboard] = useState(false)
  const [repositoryId, setRepositoryId] = useState<number | null>(null)
  const [activeSection, setActiveSection] = useState("Overview")
  const [branchHistory, setBranchHistory] = useState<BranchHistory | null>(null)
  const [historyError, setHistoryError] = useState("")
  const [user, setUser] = useState<{ display_name: string; email: string; provider?: string } | null>(null)
  const [authMode, setAuthMode] = useState<"login" | "register">("login")
  const [authEmail, setAuthEmail] = useState("")
  const [authPassword, setAuthPassword] = useState("")
  const [authName, setAuthName] = useState("")
  const [authError, setAuthError] = useState("")
  const [authLoading, setAuthLoading] = useState(false)

  const apiBase = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://127.0.0.1:8001" : "")

  useEffect(() => {
    fetch(`${apiBase}/auth/me`, { credentials: "include" })
      .then((response) => response.ok ? response.json() : null)
      .then((data) => {
        if (data) setUser(data)
      })
      .catch(() => undefined)
  }, [apiBase])

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAuthLoading(true)
    setAuthError("")
    try {
      const response = await fetch(`${apiBase}/auth/${authMode}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          authMode === "register"
            ? { email: authEmail, password: authPassword, display_name: authName }
            : { email: authEmail, password: authPassword },
        ),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || "Authentication failed.")
      setUser(data)
      setAuthPassword("")
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Authentication failed.")
    } finally {
      setAuthLoading(false)
    }
  }

  async function analyzeRepository(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const url = repoUrl.trim()

    if (!/^https:\/\/github\.com\/[^/]+\/[^/]+\/?$/.test(url)) {
      setStatus("error")
      setMessage("Enter a public GitHub URL, for example https://github.com/owner/repository")
      return
    }

    setStatus("loading")
    setMessage("Checking repository history…")

    try {
      const existingResponse = await fetch(`${apiBase}/repositories`, { credentials: "include" })
      const existing = await existingResponse.json()
      const existingRepository = Array.isArray(existing)
        ? existing.find((repository) => repository.repo_url === url)
        : null

      const response = existingRepository
        ? { ok: true, json: async () => existingRepository }
        : await fetch(`${apiBase}/repositories`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ repo_url: url }),
          })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Unable to analyze repository.")
      }

      setStatus("success")
      setMessage(`${data.name || "Repository"} is ready to explore.`)
      setRepositoryId(data.id)
      setDashboard(true)
    } catch (error) {
      setStatus("error")
      setMessage(error instanceof Error ? error.message : "Unable to analyze repository.")
    }
  }

  useEffect(() => {
    if (!dashboard || repositoryId === null) return
    let active = true
    fetch(`${apiBase}/repositories/${repositoryId}/branches/history?max_commits=300&max_branches=100`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load branch history.")
        return response.json() as Promise<BranchHistory>
      })
      .then((data) => {
        if (active) setBranchHistory(data)
      })
      .catch((error: unknown) => {
        if (active) setHistoryError(error instanceof Error ? error.message : "Unable to load branch history.")
      })
    return () => {
      active = false
    }
  }, [dashboard, repositoryId])

  return (
    dashboard ? (
      <main className="flex min-h-svh bg-[#07070a] text-white">
        <LineSidebar
          items={["Overview", "File Analysis", "Change Impact / Risk", "Merge Conflict Analysis", "Profile"]}
          accentColor="#A855F7"
          textColor="#c4c4c4"
          markerColor="#6c6c6c"
          showIndex
          showMarker
          proximityRadius={100}
          maxShift={30}
          falloff="smooth"
          markerLength={60}
          markerGap={0}
          tickScale={0.5}
          scaleTick
          itemGap={20}
          fontSize={1.1}
          smoothing={100}
          defaultActive={0}
          onItemClick={(_, label) => setActiveSection(label)}
        />
        <section className="flex-1 px-8 py-12 lg:px-14">
          <div className="mx-auto max-w-6xl">
            <p className="font-mono text-xs uppercase tracking-[0.3em] text-purple-400">{activeSection}</p>
            <h1 className="mt-4 text-4xl font-semibold">Your software, mapped.</h1>
            <div className="mt-2 flex items-center justify-between text-xs text-white/40">
              <span>Signed in as {user?.display_name} ({user?.email})</span>
              <button type="button" onClick={async () => { await fetch(`${apiBase}/auth/logout`, { method: "POST", credentials: "include" }); setUser(null); setDashboard(false) }} className="hover:text-white">Sign out</button>
            </div>
            {activeSection === "Overview" ? (
              <div className="mt-10">
                {historyError ? (
                  <p className="text-sm text-rose-300">{historyError}</p>
                ) : branchHistory ? (
                  <BranchTree history={branchHistory} />
                ) : (
                  <p className="text-sm text-white/45">Loading branch history…</p>
                )}
              </div>
            ) : activeSection === "File Analysis" && repositoryId !== null ? (
              <FileAnalysis repositoryId={repositoryId} />
            ) : activeSection === "Change Impact / Risk" && repositoryId !== null ? (
              <ChangeImpactRisk repositoryId={repositoryId} />
            ) : activeSection === "Merge Conflict Analysis" && repositoryId !== null ? (
              <MergeConflictAnalysis repositoryId={repositoryId} />
            ) : activeSection === "Profile" ? (
              <div className="mt-10 flex justify-center">
                <ProfileCard
                  name={user?.display_name || "CodeDNA User"}
                  title={user?.email || "Software Engineer"}
                  handle={user?.email?.split("@")[0] || "codna-user"}
                  status="Online"
                  contactText="Contact"
                  avatarUrl="/path/to/portrait.png"
                  iconUrl="/assets/demo/iconpattern.png"
                  holo={0.8}
                  glare={0.5}
                  tiltStrength={12}
                  parallax={8}
                  radius={16}
                  enableTilt
                  intro
                  showUserInfo
                  enableMobileTilt={false}
                  theme="dark"
                  onContactClick={() => console.log("Contact clicked")}
                />
              </div>
            ) : (
              <p className="mt-4 text-white/55">This section is ready for the next analysis view.</p>
            )}
          </div>
        </section>
      </main>
    ) : (
    <main
      className="relative min-h-svh overflow-hidden text-white"
      style={{ backgroundColor: "#050505" }}
    >
      <div className="absolute inset-0">
        <PixelBlast
          className="opacity-30"
          variant="square"
          pixelSize={4}
          color="#7c3aed"
          accentColor="#22d3ee"
          patternScale={3}
          patternDensity={1.2}
          enableRipples
          rippleSpeed={0.7}
          autoRipple={2}
          autoPauseOffscreen={false}
          speed={0.8}
          transparent={false}
          glow={0.7}
          twinkle={0.35}
          drift={0.8}
          hoverEffect="reveal"
          style={{}}
          variation={undefined}
          dpr={undefined}
        />
      </div>
      <div className="pointer-events-none absolute inset-[-20%] animate-[spin_45s_linear_infinite] bg-[radial-gradient(circle_at_30%_30%,rgba(34,211,238,0.12),transparent_35%),radial-gradient(circle_at_70%_60%,rgba(124,58,237,0.16),transparent_35%)]" />
      <section className="relative z-10 flex min-h-svh items-center justify-center px-6 text-center">
        <div className="max-w-3xl">
          <p className="mb-5 font-mono text-xs uppercase tracking-[0.35em] text-cyan-300/80">
            CodeDNA · software archaeology
          </p>
          <h1 className="text-5xl font-semibold tracking-tight sm:text-7xl">
            See how your code evolved.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-base leading-7 text-white/65 sm:text-lg">
            Explore repositories, branch histories, dependencies, and change impact
            in one living map of your software.
          </p>
          {!user ? (
            <form onSubmit={submitAuth} className="mx-auto mt-9 max-w-md text-left">
              <div className="rounded-2xl border border-white/15 bg-black/60 p-5 backdrop-blur-md">
                <p className="text-center text-sm font-medium">{authMode === "login" ? "Sign in to your workspace" : "Create your workspace"}</p>
                {authMode === "register" && (
                  <input value={authName} onChange={(event) => setAuthName(event.target.value)} placeholder="Display name" required className="mt-4 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/35" />
                )}
                <input type="email" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} placeholder="Email" required className="mt-4 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/35" />
                <input type="password" value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} placeholder="Password (8+ characters)" required minLength={8} className="mt-2 w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm outline-none placeholder:text-white/35" />
                <button type="submit" disabled={authLoading} className="mt-4 w-full rounded-xl bg-white px-5 py-3 text-sm font-medium text-black hover:bg-cyan-200 disabled:opacity-60">{authLoading ? "Please wait…" : authMode === "login" ? "Sign in" : "Create account"}</button>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <a href={`${apiBase}/auth/google/start`} className="rounded-xl border border-white/15 px-3 py-2 text-center text-xs hover:bg-white/10">Google</a>
                  <a href={`${apiBase}/auth/github/start`} className="rounded-xl border border-white/15 px-3 py-2 text-center text-xs hover:bg-white/10">GitHub</a>
                </div>
                {authError && <p role="alert" className="mt-3 text-center text-xs text-rose-300">{authError}</p>}
                <button type="button" onClick={() => { setAuthMode(authMode === "login" ? "register" : "login"); setAuthError("") }} className="mt-4 w-full text-center text-xs text-cyan-300/80">{authMode === "login" ? "Need an account? Register" : "Already have an account? Sign in"}</button>
              </div>
            </form>
          ) : !showAnalyzer ? (
            <button
              type="button"
              onClick={() => setShowAnalyzer(true)}
              className="mt-9 rounded-full border border-white/20 bg-white px-6 py-3 text-sm font-medium text-black transition hover:bg-cyan-200"
            >
              Analyze a repository
            </button>
          ) : (
            <form onSubmit={analyzeRepository} className="mx-auto mt-9 max-w-2xl">
              <div className="flex flex-col gap-2 rounded-2xl border border-white/15 bg-black/60 p-2 backdrop-blur-md sm:flex-row">
                <input
                  autoFocus
                  type="url"
                  value={repoUrl}
                  onChange={(event) => {
                    setRepoUrl(event.target.value)
                    if (status !== "idle") setStatus("idle")
                  }}
                  placeholder="https://github.com/owner/repository"
                  aria-label="GitHub repository URL"
                  className="min-w-0 flex-1 rounded-xl bg-transparent px-4 py-3 text-sm text-white outline-none placeholder:text-white/35"
                />
                <button
                  type="submit"
                  disabled={status === "loading"}
                  className="rounded-xl bg-white px-5 py-3 text-sm font-medium text-black transition hover:bg-cyan-200 disabled:cursor-wait disabled:opacity-60"
                >
                  {status === "loading" ? "Analyzing…" : "Analyze"}
                </button>
              </div>
              <p
                role={status === "error" ? "alert" : "status"}
                className={`mt-3 text-sm ${status === "error" ? "text-rose-300" : status === "success" ? "text-emerald-300" : "text-white/55"}`}
              >
                {message || "Paste a public GitHub repository URL to begin."}
              </p>
            </form>
          )}
        </div>
      </section>
    </main>
    )
  )
}

export default App
