import { useEffect, useMemo, useState } from "react"

interface RepositoryFile {
  path: string
  language: string | null
  size: number
  is_source: boolean
}

interface RepositoryTree {
  files: RepositoryFile[]
}

interface RiskModule {
  path: string
  total_score: number
  risk_level: string
  explanation: string
}

interface RiskReport {
  summary: Record<string, unknown>
  modules: RiskModule[]
}

interface ImpactItem {
  label: string
  file_path: string
  impact_score: number
  reasons?: string[]
}

interface ImpactReport {
  risk_score: number
  risk_level: string
  target_file: string
  direct_callers: ImpactItem[]
  affected_modules: ImpactItem[]
  affected_tests: ImpactItem[]
  co_changing_files: ImpactItem[]
  review_components: ImpactItem[]
  summary: Record<string, unknown>
}

const apiBase = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://127.0.0.1:8001" : "")

function List({ items, empty }: { items: ImpactItem[]; empty: string }) {
  return items.length ? (
    <ul className="mt-3 space-y-2">
      {items.slice(0, 8).map((item) => (
        <li key={`${item.file_path}-${item.label}`} className="rounded-lg border border-white/8 bg-black/20 p-3">
          <p className="truncate font-mono text-xs text-cyan-100">{item.file_path || item.label}</p>
          <p className="mt-1 text-xs text-white/45">
            Impact {item.impact_score.toFixed(1)}
            {item.reasons?.length ? ` · ${item.reasons.join(", ")}` : ""}
          </p>
        </li>
      ))}
    </ul>
  ) : <p className="mt-3 text-sm text-white/35">{empty}</p>
}

export default function ChangeImpactRisk({ repositoryId }: { repositoryId: number }) {
  const [tree, setTree] = useState<RepositoryTree | null>(null)
  const [risk, setRisk] = useState<RiskReport | null>(null)
  const [impact, setImpact] = useState<ImpactReport | null>(null)
  const [target, setTarget] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    Promise.all([
      fetch(`${apiBase}/repositories/${repositoryId}/tree`).then((response) => response.json() as Promise<RepositoryTree>),
      fetch(`${apiBase}/risk/${repositoryId}`).then((response) => response.json() as Promise<RiskReport>),
    ])
      .then(([treeData, riskData]) => {
        if (!active) return
        setTree(treeData)
        setRisk(riskData)
        setTarget(treeData.files.find((file) => file.is_source)?.path ?? treeData.files[0]?.path ?? "")
      })
      .catch(() => {
        if (active) setError("Unable to load change impact and risk data.")
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [repositoryId])

  useEffect(() => {
    if (!target) return
    let active = true
    fetch(`${apiBase}/impact/${repositoryId}?target=${encodeURIComponent(target)}&target_file=${encodeURIComponent(target)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load impact data.")
        return response.json() as Promise<ImpactReport>
      })
      .then((data) => { if (active) setImpact(data) })
      .catch(() => { if (active) setImpact(null) })
    return () => { active = false }
  }, [repositoryId, target])

  const hotspots = useMemo(
    () => tree?.files.filter((file) => /auth|secret|token|password|crypto|security|sql/i.test(file.path)).slice(0, 12) ?? [],
    [tree],
  )
  const dependencyFiles = useMemo(
    () => tree?.files.filter((file) => /(^|\/)(package(-lock)?\.json|requirements.*\.txt|pyproject\.toml|poetry\.lock|go\.mod|cargo\.toml)$/i.test(file.path)) ?? [],
    [tree],
  )

  if (loading) return <p className="mt-10 text-sm text-white/45">Loading impact and risk analysis…</p>
  if (error) return <p className="mt-10 text-sm text-rose-300">{error}</p>

  return (
    <div className="mt-10 space-y-6">
      <section className="rounded-2xl border border-white/10 bg-[#111113] p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-cyan-300/70">Change Impact / Risk</p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <select value={target} onChange={(event) => setTarget(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/30 px-3 py-2 font-mono text-xs text-white">
            {tree?.files.map((file) => <option key={file.path} value={file.path}>{file.path}</option>)}
          </select>
          {impact && <span className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/60">Risk: {impact.risk_level} · {impact.risk_score.toFixed(1)}</span>}
        </div>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div>
            <h2 className="text-lg font-medium">What depends on this?</h2>
            <List items={impact?.direct_callers ?? []} empty="No direct dependents detected." />
          </div>
          <div>
            <h2 className="text-lg font-medium">What could break?</h2>
            <List items={impact?.review_components ?? impact?.affected_modules ?? []} empty="No affected components detected." />
          </div>
          <div>
            <h2 className="text-lg font-medium">Affected files</h2>
            <List items={impact?.co_changing_files ?? []} empty="No co-changing files detected." />
          </div>
          <div>
            <h2 className="text-lg font-medium">Affected modules</h2>
            <List items={impact?.affected_modules ?? []} empty="No affected modules detected." />
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-white/10 bg-[#111113] p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-rose-300/70">Security Analysis</p>
        <p className="mt-2 text-xs text-white/35">Static repository hotspots and dependency manifests. This is triage, not proof of vulnerabilities.</p>
        <div className="mt-5 grid gap-6 lg:grid-cols-3">
          <div>
            <h2 className="text-lg font-medium">Vulnerabilities</h2>
            <List items={(risk?.modules ?? []).filter((module) => module.risk_level.toLowerCase() === "high" || module.risk_level.toLowerCase() === "critical").map((module) => ({ label: module.path, file_path: module.path, impact_score: module.total_score, reasons: [module.explanation] }))} empty="No high-risk modules reported." />
          </div>
          <div>
            <h2 className="text-lg font-medium">Dependency issues</h2>
            <ul className="mt-3 space-y-2">{dependencyFiles.length ? dependencyFiles.map((file) => <li key={file.path} className="rounded-lg border border-white/8 bg-black/20 p-3 font-mono text-xs text-amber-100">{file.path}</li>) : <li className="text-sm text-white/35">No dependency manifests detected.</li>}</ul>
          </div>
          <div>
            <h2 className="text-lg font-medium">Security hotspots</h2>
            <ul className="mt-3 space-y-2">{hotspots.length ? hotspots.map((file) => <li key={file.path} className="rounded-lg border border-white/8 bg-black/20 p-3 font-mono text-xs text-rose-100">{file.path}</li>) : <li className="text-sm text-white/35">No path-based hotspots detected.</li>}</ul>
          </div>
        </div>
      </section>
    </div>
  )
}
