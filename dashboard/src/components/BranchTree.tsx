import { useMemo, useRef, useState } from "react"

interface BranchCommit {
  hash: string
  short_hash: string
  message: string
  author: string
  date: string
  parents: string[]
}

export interface BranchHistory {
  default_branch: string | null
  branches: Array<{ name: string; is_default: boolean; commits: BranchCommit[] }>
}

interface BranchTreeProps { history: BranchHistory; repositoryUrl: string }

const COLORS = ["#49d9ff", "#c084fc", "#fb7185", "#fbbf24", "#34d399", "#818cf8", "#fb923c", "#2dd4bf"]
const LEFT = 190
const STEP_X = 90
const MIN_ZOOM = 0.8
const MAX_ZOOM = 2.4
const VISIBLE_WINDOW = 80
type ViewMode = "branch" | "all"

export default function BranchTree({ history, repositoryUrl }: BranchTreeProps) {
  const [cursor, setCursor] = useState(1)
  const [selectedHash, setSelectedHash] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const [activeBranch, setActiveBranch] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>("branch")
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 })
  const pan = useRef<{ pointerX: number; pointerY: number; x: number; y: number } | null>(null)
  const canvasRef = useRef<HTMLDivElement>(null)

  const model = useMemo(() => {
    const branches = [...history.branches].sort((a, b) => Number(b.is_default) - Number(a.is_default))
    const commits = new Map<string, BranchCommit>()
    branches.forEach((branch) => branch.commits.forEach((commit) => commits.set(commit.hash, commit)))
    const ordered = [...commits.values()].sort((a, b) => Date.parse(a.date) - Date.parse(b.date))
    const index = new Map(ordered.map((commit, i) => [commit.hash, i]))
    const lane = new Map<string, number>()
    branches.forEach((branch, i) => branch.commits.forEach((commit) => {
      if (!lane.has(commit.hash)) lane.set(commit.hash, i)
    }))
    return { branches, ordered, index, lane, width: Math.max(1100, LEFT + ordered.length * STEP_X + 120), height: 520 }
  }, [history])

  const cursorEnd = Math.max(1, Math.floor(cursor * model.ordered.length))
  const allBranchCommits = activeBranch
    ? model.branches.find((branch) => branch.name === activeBranch)?.commits ?? []
    : model.branches[0]?.commits ?? []
  const branchCommits = allBranchCommits.filter((commit) => (model.index.get(commit.hash) ?? 0) < cursorEnd)
  const visibleCommits = branchCommits
  const selected = model.ordered.find((commit) => commit.hash === selectedHash)
  const commitUrl = repositoryUrl.match(/^https:\/\/github\.com\/[^/]+\/[^/]+\/?$/)
    ? `${repositoryUrl.replace(/\/$/, "")}/commit/${selected?.hash ?? ""}`
    : null
  const branchIndex = Math.max(0, model.branches.findIndex((branch) => branch.name === (activeBranch ?? model.branches[0]?.name)))
  const activeBranchData = model.branches[branchIndex]
  const plottedBranches = viewMode === "all" ? model.branches : activeBranchData ? [activeBranchData] : []
  const oldestCommit = allBranchCommits[0]
  const latestCommit = allBranchCommits[allBranchCommits.length - 1]
  const currentCommit = branchCommits[branchCommits.length - 1]
  const point = (commit: BranchCommit) => ({
    x: LEFT + ((model.index.get(commit.hash) ?? 0) - (model.index.get(allBranchCommits[0]?.hash ?? "") ?? 0)) * STEP_X,
    y: activeBranchData?.is_default ? 330 : 330 + (branchIndex % 2 ? 95 : -95),
  })
  const dateLabel = (date: string) => new Date(date).toLocaleDateString(undefined, { month: "short", year: "2-digit" })

  function startPan(event: React.PointerEvent<HTMLDivElement>) {
    if ((event.target as Element).closest("[data-commit]") || (event.target as Element).closest("button") || event.button !== 0) return
    event.preventDefault()
    event.currentTarget.setPointerCapture(event.pointerId)
    pan.current = { pointerX: event.clientX, pointerY: event.clientY, x: viewport.x, y: viewport.y }
  }

  function movePan(event: React.PointerEvent<HTMLDivElement>) {
    if (!pan.current) return
    const dx = event.clientX - pan.current.pointerX
    const dy = event.clientY - pan.current.pointerY
    setViewport({ ...viewport, x: pan.current.x + dx, y: pan.current.y + dy })
  }

  function stopPan(event?: React.PointerEvent<HTMLDivElement>) {
    if (event && event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    pan.current = null
  }

  function zoomAt(event: React.WheelEvent<HTMLDivElement>) {
    if (!event.ctrlKey && !event.metaKey) return
    event.preventDefault()
    const bounds = event.currentTarget.getBoundingClientRect()
    const px = event.clientX - bounds.left
    const py = event.clientY - bounds.top
    const currentViewport = viewport
    const nextZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, currentViewport.zoom * (event.deltaY < 0 ? 1.12 : 0.89)))
    const ratio = nextZoom / currentViewport.zoom
    setViewport({ zoom: nextZoom, x: px - (px - currentViewport.x) * ratio, y: py - (py - currentViewport.y) * ratio })
  }

  return <section className="overflow-hidden rounded-2xl border border-white/10 bg-[#0b0c11] shadow-2xl shadow-cyan-950/10">
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-white/10 px-6 py-5">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.32em] text-cyan-300/70">Repository time machine</p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight">Layers of change</h2>
        <p className="mt-1 text-sm text-white/45">Read the codebase as it evolved. Select any artifact to excavate its story.</p>
      </div>
      <label className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white/60">
        <span aria-hidden="true">⌕</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find commit, author, hash" className="w-48 bg-transparent text-sm text-white outline-none placeholder:text-white/30" />
      </label>
    </header>

    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-white/[0.07] px-6 py-3">
      <div className="flex rounded-lg border border-white/10 bg-white/[0.03] p-1">
        <button onClick={() => setViewMode("branch")} className={`rounded-md px-3 py-1.5 text-xs ${viewMode === "branch" ? "bg-white/10 text-white" : "text-white/45 hover:text-white"}`}>Focus branch</button>
        <button onClick={() => setViewMode("all")} className={`rounded-md px-3 py-1.5 text-xs ${viewMode === "all" ? "bg-white/10 text-white" : "text-white/45 hover:text-white"}`}>All branches</button>
      </div>
      {viewMode === "branch" && model.branches.map((branch, i) => <button key={branch.name} onClick={() => { setActiveBranch(branch.name); setSelectedHash(null) }} className={`flex items-center gap-2 rounded-full px-2.5 py-1 text-xs transition ${branch.name === (activeBranch ?? model.branches[0]?.name) ? "bg-white/10 text-white" : "text-white/40 hover:text-white/75"}`}>
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
        <span>{branch.name}{branch.is_default ? " · primary" : ""}</span>
      </button>)}
      <span className="ml-auto font-mono text-[10px] text-white/35">{viewMode === "all" ? `${model.branches.length} branches · ${model.ordered.length} unique commits` : `${activeBranchData?.name}: ${branchCommits.length} commits`}</span>
    </div>

    <div ref={canvasRef} onPointerDown={startPan} onPointerMove={movePan} onPointerUp={stopPan} onPointerCancel={stopPan} onWheel={zoomAt} className={`relative h-[min(62vh,620px)] min-h-[360px] overflow-hidden bg-[radial-gradient(ellipse_at_50%_0%,rgba(34,211,238,0.08),transparent_55%)] ${pan.current ? "cursor-grabbing" : "cursor-grab"}`}>
      <div className="absolute left-4 top-4 z-10 flex items-center gap-1 rounded-xl border border-white/10 bg-[#11141bcc] p-1 backdrop-blur">
        <button aria-label="Zoom out" onClick={() => setViewport((v) => ({ ...v, zoom: Math.max(MIN_ZOOM, v.zoom / 1.2) }))} className="h-10 w-10 rounded-lg text-xl text-white/80 hover:bg-white/10">−</button>
        <span className="w-14 text-center font-mono text-xs text-white/65">{Math.round(viewport.zoom * 100)}%</span>
        <button aria-label="Zoom in" onClick={() => setViewport((v) => ({ ...v, zoom: Math.min(MAX_ZOOM, v.zoom * 1.2) }))} className="h-10 w-10 rounded-lg text-xl text-white/80 hover:bg-white/10">+</button>
        <button onClick={() => { setViewport({ x: 0, y: 0, zoom: 1 }); setCursor(1); setSelectedHash(null) }} className="rounded-lg px-3 py-2 text-xs text-white/55 hover:bg-white/10 hover:text-white">Reset</button>
      </div>
      <div className="pointer-events-none absolute bottom-3 right-4 z-10 font-mono text-[10px] uppercase tracking-wider text-white/45">Drag to pan · Ctrl + wheel or buttons to zoom</div>
      <svg width="100%" height="100%" viewBox="0 0 1100 520" preserveAspectRatio="none" className="block h-full w-full select-none">
        <defs>
          <pattern id="strata-grid" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="white" opacity=".08" /></pattern>
          {COLORS.map((color, i) => <filter id={`strata-glow-${i}`} key={color} x="-300%" y="-300%" width="700%" height="700%"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>)}
        </defs>
        <rect width="100%" height="100%" fill="url(#strata-grid)" pointerEvents="none" />
        <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.zoom})`}>
        {plottedBranches.map((branch) => {
          const laneIndex = model.branches.findIndex((item) => item.name === branch.name)
          const color = COLORS[laneIndex % COLORS.length]
          const y = viewMode === "all" ? 115 + laneIndex * 55 : branch.is_default ? 330 : 330 + (laneIndex % 2 ? 95 : -95)
          const branchVisible = branch.commits.filter((commit) => (model.index.get(commit.hash) ?? 0) < cursorEnd)
          const branchMarkers = branchVisible.length > VISIBLE_WINDOW ? branchVisible.filter((_, i) => i % Math.ceil(branchVisible.length / VISIBLE_WINDOW) === 0 || i === branchVisible.length - 1) : branchVisible
          const getPoint = (commit: BranchCommit) => viewMode === "all"
            ? { x: LEFT + (model.index.get(commit.hash) ?? 0) * 3, y }
            : point(commit)
          return <g key={branch.name}>
            <line x1={LEFT - 24} x2={model.width} y1={y} y2={y} stroke={color} strokeOpacity=".18" strokeWidth="2" />
            <text x="32" y={y - 10} fill={color} fontSize={viewMode === "all" ? "14" : "20"} fontFamily="sans-serif" fontWeight="600">{branch.name.length > 23 ? `${branch.name.slice(0, 21)}…` : branch.name}</text>
            {branchMarkers.map((commit) => {
              const p = getPoint(commit)
              const isMerge = commit.parents.length > 1
              const active = selectedHash === commit.hash
              const matches = !query || `${commit.message} ${commit.author} ${commit.short_hash}`.toLowerCase().includes(query.toLowerCase())
              return <g key={commit.hash} data-commit role="button" tabIndex={0} aria-label={`${commit.message}, ${commit.author}, ${dateLabel(commit.date)}`} onClick={(event) => { event.stopPropagation(); setSelectedHash(commit.hash) }} onPointerDown={(event) => event.stopPropagation()} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedHash(commit.hash) }} className="cursor-pointer" opacity={matches ? 1 : 0.12}>
                {isMerge && <circle cx={p.x} cy={p.y} r={viewMode === "all" ? "8" : "19"} fill="none" stroke={color} strokeOpacity=".55" strokeWidth="2" />}
                <circle cx={p.x} cy={p.y} r={active ? 12 : viewMode === "all" ? 4 : isMerge ? 11 : 8} fill={active ? "#ffffff" : color} stroke={color} strokeWidth="2" filter={active ? `url(#strata-glow-${laneIndex % COLORS.length})` : undefined} />
                {active && <g><rect x={p.x - 145} y={p.y - 84} width="290" height="54" rx="12" fill="#181b24" stroke={color} strokeOpacity=".75"/><text x={p.x} y={p.y - 61} textAnchor="middle" fill="white" fontSize="15">{commit.message.slice(0, 34)}{commit.message.length > 34 ? "…" : ""}</text><text x={p.x} y={p.y - 42} textAnchor="middle" fill="#a9b2c3" fontSize="11">{commit.short_hash} · {dateLabel(commit.date)}</text></g>}
              </g>
            })}
          </g>
        })}
        {viewMode === "branch" && activeBranchData && visibleCommits.slice(1).filter((_, i) => (i + 1) % Math.max(1, Math.ceil(visibleCommits.length / VISIBLE_WINDOW)) === 0).map((commit) => {
          const index = visibleCommits.findIndex((item) => item.hash === commit.hash)
          const previous = visibleCommits[index - 1]
          const a = point(previous), b = point(commit)
          return <path key={`trail-${previous.hash}-${commit.hash}`} d={`M ${a.x} ${a.y} C ${a.x + (b.x - a.x) * .45} ${a.y - 35}, ${a.x + (b.x - a.x) * .55} ${b.y - 35}, ${b.x} ${b.y}`} fill="none" stroke={COLORS[branchIndex % COLORS.length]} strokeOpacity=".62" strokeWidth="3" />
        })}
        {visibleCommits.length > 1 && <g>{[0, .25, .5, .75, 1].map((fraction) => { const index = Math.min(visibleCommits.length - 1, Math.floor(fraction * (visibleCommits.length - 1))); const commit = visibleCommits[index]; const p = point(commit); return <g key={fraction}><line x1={p.x} x2={p.x} y1="60" y2="450" stroke="white" strokeOpacity=".08"/><text x={p.x} y="470" textAnchor="middle" fill="#a3a9b5" fontSize="13" fontFamily="monospace">{dateLabel(commit.date)}</text></g> })}</g>}
        </g>
      </svg>
    </div>

    <div className="border-t border-white/10 bg-black/25 px-6 py-4">
      <div className="flex items-center gap-4">
        <span className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-cyan-200/65">Rewind history</span>
        <span className="hidden shrink-0 text-xs text-white/45 sm:block">{oldestCommit ? dateLabel(oldestCommit.date) : "—"}</span>
        <input aria-label="Rewind repository history from latest to oldest" type="range" min="0.01" max="1" step="0.01" value={cursor} onChange={(event) => setCursor(Number(event.target.value))} className="h-1.5 flex-1 cursor-pointer accent-cyan-300" />
        <span className="hidden shrink-0 text-xs text-white/45 sm:block">{latestCommit ? dateLabel(latestCommit.date) : "—"}</span>
        <span className="min-w-32 text-right text-xs text-white/65">{currentCommit ? `At ${dateLabel(currentCommit.date)}` : "At start"}</span>
      </div>
      <p className="mt-3 text-xs text-white/40">Move left to rewind toward the first commit. Move right to return to the latest state. In all branches mode, each lane follows its branch through the same repository timeline.</p>
    </div>

    {selected && <aside className="border-t border-cyan-300/15 bg-gradient-to-r from-cyan-950/25 to-transparent px-6 py-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0"><p className="font-mono text-[10px] uppercase tracking-[0.25em] text-cyan-200/65">Excavated commit · {selected.short_hash}</p><h3 className="mt-2 text-lg font-medium text-white">{selected.message}</h3><p className="mt-2 text-sm text-white/50">{selected.author} <span className="px-1 text-white/20">·</span> {new Date(selected.date).toLocaleString()}</p>{commitUrl && <a href={commitUrl} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-2 rounded-lg border border-cyan-300/20 bg-cyan-300/[0.06] px-3 py-2 text-xs font-medium text-cyan-100 transition hover:border-cyan-200/50 hover:bg-cyan-300/10">Open commit on GitHub <span aria-hidden="true">↗</span></a>}</div>
        <button onClick={() => setSelectedHash(null)} className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/55 hover:text-white">Close</button>
      </div>
    </aside>}
  </section>
}
