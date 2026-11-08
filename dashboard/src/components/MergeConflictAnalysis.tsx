import { useEffect, useState } from "react"

interface BranchHistory {
  branches: Array<{ name: string }>
}

interface ConflictAnalysis {
  base_branch: string
  compare_branch: string
  conflicting_files: Array<{ path: string; status: string }>
  conflict_relationships: Array<{ files: string[]; relationship: string }>
  developer_discussion: Array<{ branch: string; author: string; message: string; date: string }>
  ai_explanation: string
}

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001"

export default function MergeConflictAnalysis({ repositoryId }: { repositoryId: number }) {
  const [branches, setBranches] = useState<string[]>([])
  const [baseBranch, setBaseBranch] = useState("")
  const [compareBranch, setCompareBranch] = useState("")
  const [analysis, setAnalysis] = useState<ConflictAnalysis | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${apiBase}/repositories/${repositoryId}/branches/history?max_commits=1&max_branches=100`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load branches.")
        return response.json() as Promise<BranchHistory>
      })
      .then((data) => {
        const names = data.branches.map((branch) => branch.name)
        setBranches(names)
        setBaseBranch(names[0] ?? "")
        setCompareBranch(names[1] ?? names[0] ?? "")
      })
      .catch(() => setError("Unable to load repository branches."))
      .finally(() => setLoading(false))
  }, [repositoryId])

  useEffect(() => {
    if (!baseBranch || !compareBranch || baseBranch === compareBranch) {
      setAnalysis(null)
      return
    }
    let active = true
    setError("")
    fetch(`${apiBase}/repositories/${repositoryId}/merge-conflicts?base_branch=${encodeURIComponent(baseBranch)}&compare_branch=${encodeURIComponent(compareBranch)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to analyze merge conflicts.")
        return response.json() as Promise<ConflictAnalysis>
      })
      .then((data) => { if (active) setAnalysis(data) })
      .catch(() => { if (active) setError("Unable to analyze merge conflicts.") })
    return () => { active = false }
  }, [repositoryId, baseBranch, compareBranch])

  if (loading) return <p className="mt-10 text-sm text-white/45">Loading branches…</p>
  if (error && !analysis) return <p className="mt-10 text-sm text-rose-300">{error}</p>

  return (
    <div className="mt-10 space-y-6">
      <section className="rounded-2xl border border-white/10 bg-[#111113] p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-amber-300/70">Merge Conflict Analysis</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <label className="text-xs text-white/45">Base branch
            <select value={baseBranch} onChange={(event) => setBaseBranch(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-white">
              {branches.map((branch) => <option key={branch}>{branch}</option>)}
            </select>
          </label>
          <label className="text-xs text-white/45">Compare branch
            <select value={compareBranch} onChange={(event) => setCompareBranch(event.target.value)} className="mt-2 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-white">
              {branches.map((branch) => <option key={branch}>{branch}</option>)}
            </select>
          </label>
        </div>
      </section>
      {analysis && (
        <>
          <section className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-[#111113] p-6">
              <h2 className="text-lg font-medium">Conflicting files</h2>
              <ul className="mt-4 space-y-2">{analysis.conflicting_files.length ? analysis.conflicting_files.map((file) => <li key={file.path} className="rounded-lg border border-rose-300/20 bg-rose-300/5 p-3 font-mono text-xs text-rose-100">{file.path}</li>) : <li className="text-sm text-white/35">No conflicting files detected.</li>}</ul>
            </div>
            <div className="rounded-2xl border border-white/10 bg-[#111113] p-6">
              <h2 className="text-lg font-medium">Conflict relationships</h2>
              <ul className="mt-4 space-y-2">{analysis.conflict_relationships.length ? analysis.conflict_relationships.map((item) => <li key={item.files.join(":")} className="rounded-lg border border-white/8 bg-black/20 p-3 text-xs text-white/65">{item.files.join(" ↔ ")}<span className="ml-2 text-white/35">({item.relationship})</span></li>) : <li className="text-sm text-white/35">No conflict clusters detected.</li>}</ul>
            </div>
          </section>
          <section className="rounded-2xl border border-white/10 bg-[#111113] p-6">
            <h2 className="text-lg font-medium">Developer discussion</h2>
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">{analysis.developer_discussion.map((item, index) => <li key={`${item.branch}-${index}`} className="rounded-lg border border-white/8 bg-black/20 p-3"><p className="font-mono text-[10px] uppercase tracking-widest text-cyan-300/60">{item.branch} · {item.author}</p><p className="mt-2 text-sm text-white/65">{item.message}</p></li>)}</ul>
          </section>
          <section className="rounded-2xl border border-white/10 bg-[#111113] p-6">
            <h2 className="text-lg font-medium">AI explanation of conflicts</h2>
            <p className="mt-3 text-sm leading-7 text-white/60">{analysis.ai_explanation}</p>
            <p className="mt-3 text-[10px] text-white/30">Generated from Git merge results and branch commit history; no merge is performed.</p>
          </section>
        </>
      )}
    </div>
  )
}
