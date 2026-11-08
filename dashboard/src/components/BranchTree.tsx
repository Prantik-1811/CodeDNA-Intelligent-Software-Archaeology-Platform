import { useEffect, useMemo, useRef, useState } from "react"
import type { PointerEvent } from "react"

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
  branches: Array<{
    name: string
    is_default: boolean
    commits: BranchCommit[]
  }>
}

interface BranchTreeProps {
  history: BranchHistory
}

interface Point {
  x: number
  y: number
}

const CARD_WIDTH = 190
const CARD_HEIGHT = 76
const MAX_VISIBLE_COMMITS = 300

export default function BranchTree({ history }: BranchTreeProps) {
  const canvasRef = useRef<SVGSVGElement>(null)
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [selectedHash, setSelectedHash] = useState<string | null>(null)
  const [dragging, setDragging] = useState<string | null>(null)
  const [positions, setPositions] = useState<Record<string, Point>>({})
  const [growthStep, setGrowthStep] = useState(0)
  const [isGrowing, setIsGrowing] = useState(false)
  const panStart = useRef<Point | null>(null)

  const graph = useMemo(() => {
    const commits = new Map<string, BranchCommit>()
    const branchOf = new Map<string, string>()
    const initialPositions: Record<string, Point> = {}
    const defaults = history.branches.filter((branch) => branch.is_default)
    const branches = [...defaults, ...history.branches.filter((branch) => !branch.is_default)]

    branches.forEach((branch) => {
      branch.commits.forEach((commit) => {
        commits.set(commit.hash, commit)
        if (!branchOf.has(commit.hash)) branchOf.set(commit.hash, branch.name)
      })
    })

    const allCommits = Array.from(commits.values()).sort((a, b) => Date.parse(a.date) - Date.parse(b.date))
    const orderedCommits = allCommits.slice(-MAX_VISIBLE_COMMITS)
    const visibleHashes = new Set(orderedCommits.map((commit) => commit.hash))
    const order = new Map(orderedCommits.map((commit, index) => [commit.hash, index + 1]))
    const canvasHeight = Math.max(1180, 220 + orderedCommits.length * 190)
    const branchOffsets = new Map(branches.map((branch, index) => [
      branch.name,
      index === 0 ? 0 : (index % 2 ? 1 : -1) * (390 + Math.ceil(index / 2) * 130),
    ]))

    branches.forEach((branch) => {
      branch.commits.forEach((commit) => {
        if (!visibleHashes.has(commit.hash)) return
        const sequence = order.get(commit.hash) ?? 1
        initialPositions[commit.hash] = {
          x: 505 + (branchOffsets.get(branch.name) ?? 0),
          y: 110 + (orderedCommits.length - sequence) * 190,
        }
      })
    })

    const edges = orderedCommits.flatMap((commit) =>
      commit.parents
        .filter((parent) => visibleHashes.has(parent))
        .map((parent) => ({ source: parent, target: commit.hash })),
    )

    const isDefault = new Map(branches.map((branch) => [branch.name, branch.is_default]))
    return {
      commits: orderedCommits,
      edges,
      branchOf,
      branches,
      initialPositions,
      order,
      isDefault,
      canvasHeight,
      totalCommits: allCommits.length,
    }
  }, [history])

  useEffect(() => {
    setPositions((current) => {
      const next = { ...current }
      let changed = false
      for (const [hash, point] of Object.entries(graph.initialPositions)) {
        if (!next[hash]) {
          next[hash] = point
          changed = true
        }
      }
      return changed ? next : current
    })
  }, [graph.initialPositions])

  useEffect(() => {
    if (!isGrowing) return
    const timer = window.setInterval(() => {
      setGrowthStep((current) => {
        if (current >= graph.commits.length) {
          setIsGrowing(false)
          return current
        }
        return current + 1
      })
    }, 650)
    return () => window.clearInterval(timer)
  }, [graph.commits.length, isGrowing])

  function toCanvasPoint(event: PointerEvent<SVGGElement>) {
    const svg = canvasRef.current
    const transform = svg?.getScreenCTM()?.inverse()
    if (!svg || !transform) return { x: 0, y: 0 }
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(transform)
    return {
      x: (point.x - offset.x) / zoom,
      y: (point.y - offset.y) / zoom,
    }
  }

  function startPan(event: PointerEvent<SVGSVGElement>) {
    if (event.target !== event.currentTarget) return
    panStart.current = { x: event.clientX - offset.x, y: event.clientY - offset.y }
    canvasRef.current?.setPointerCapture(event.pointerId)
  }

  function moveCanvas(event: PointerEvent<SVGSVGElement>) {
    if (panStart.current) {
      setOffset({ x: event.clientX - panStart.current.x, y: event.clientY - panStart.current.y })
    }
  }

  function stopPointer() {
    setDragging(null)
    panStart.current = null
  }

  function curve(source: Point, target: Point) {
    const startX = source.x + CARD_WIDTH / 2
    const startY = source.y
    const endX = target.x + CARD_WIDTH / 2
    const endY = target.y + CARD_HEIGHT
    const bend = Math.max(45, Math.abs(endX - startX) * 0.35)
    return `M ${startX} ${startY} C ${startX + bend} ${startY - 18}, ${endX - bend} ${endY + 18}, ${endX} ${endY}`
  }

  const selected = graph.commits.find((commit) => commit.hash === selectedHash)

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#111113]">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-cyan-300/70">Git history</p>
          <h2 className="mt-2 text-xl font-medium">Living repository tree</h2>
          {graph.totalCommits > MAX_VISIBLE_COMMITS && (
            <p className="mt-2 text-xs text-amber-200/65">
              Showing the latest {MAX_VISIBLE_COMMITS} of {graph.totalCommits} commits for smooth navigation.
            </p>
          )}
        </div>
        <div className="flex items-center gap-3 font-mono text-xs text-white/40">
          <span>seed → commits → branches</span>
          <span>·</span>
          <span>pan canvas</span>
          <span>·</span>
          <span>zoom {Math.round(zoom * 100)}%</span>
        </div>
      </div>

      <svg
        ref={canvasRef}
        viewBox={`0 0 1900 ${graph.canvasHeight}`}
        className="h-[900px] w-full cursor-grab touch-none active:cursor-grabbing"
        onPointerDown={startPan}
        onPointerMove={moveCanvas}
        onPointerUp={stopPointer}
        onPointerLeave={stopPointer}
        onWheel={(event) => {
          setZoom((current) => Math.min(1.8, Math.max(0.55, current - event.deltaY * 0.001)))
        }}
      >
        <defs>
          <pattern id="graph-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" fill="#ffffff" opacity="0.14" />
          </pattern>
          <filter id="node-glow">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <marker id="flow-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M 0 0 L 8 4 L 0 8 Z" fill="#cbd5e1" />
          </marker>
          <style>{`
            @keyframes history-flow {
              to { stroke-dashoffset: -28; }
            }
            .history-flow {
              animation: history-flow 1.2s linear infinite;
            }
            .growth-node {
              transition: opacity 700ms ease, transform 700ms cubic-bezier(0.22, 1, 0.36, 1);
              transform-box: fill-box;
              transform-origin: center;
            }
            .growth-edge {
              transition: opacity 700ms ease;
            }
          `}</style>
        </defs>
        <rect width="100%" height="100%" fill="url(#graph-grid)" />
        <g transform={`translate(${offset.x} ${offset.y}) scale(${zoom})`}>
          {graph.edges.map((edge) => {
            const source = positions[edge.source]
            const target = positions[edge.target]
            if (!source || !target) return null
            const edgeStep = Math.max(graph.order.get(edge.source) ?? 0, graph.order.get(edge.target) ?? 0)
            const edgeVisible = growthStep === 0 || edgeStep <= growthStep
            return (
              <path
                key={`${edge.source}-${edge.target}`}
                d={curve(source, target)}
                fill="none"
                stroke={graph.branchOf.get(edge.target) === history.default_branch ? "#38bdf8" : "#a855f7"}
                strokeOpacity="0.8"
                strokeWidth="2.5"
                strokeDasharray="7 7"
                strokeLinecap="round"
                markerEnd="url(#flow-arrow)"
                className={`history-flow growth-edge ${edgeVisible ? "opacity-100" : "pointer-events-none opacity-0"}`}
              />
            )
          })}
          {graph.commits.map((commit) => {
            const position = positions[commit.hash]
            if (!position) return null
            const step = graph.order.get(commit.hash) ?? 0
            const visible = growthStep === 0 || step <= growthStep
            const isMain = graph.isDefault.get(graph.branchOf.get(commit.hash) ?? "") ?? false
            const active = selectedHash === commit.hash
            return (
              <g
                key={commit.hash}
                transform={`translate(${position.x} ${position.y})`}
                opacity={visible ? 1 : 0}
                onPointerDown={(event) => {
                  event.stopPropagation()
                  event.currentTarget.setPointerCapture(event.pointerId)
                  setDragging(commit.hash)
                  setSelectedHash(commit.hash)
                }}
                onPointerMove={(event) => {
                  if (dragging !== commit.hash) return
                  const point = toCanvasPoint(event)
                  setPositions((current) => ({
                    ...current,
                    [commit.hash]: {
                      x: point.x - CARD_WIDTH / 2,
                      y: point.y - CARD_HEIGHT / 2,
                    },
                  }))
                }}
                onPointerUp={(event) => {
                  event.currentTarget.releasePointerCapture(event.pointerId)
                  stopPointer()
                }}
                onClick={(event) => event.stopPropagation()}
                className={`growth-node cursor-move ${visible ? "scale-100" : "pointer-events-none scale-90"}`}
              >
                {active && <rect x="-5" y="-5" width={CARD_WIDTH + 10} height={CARD_HEIGHT + 10} rx="15" fill={isMain ? "#22d3ee" : "#a855f7"} opacity="0.22" filter="url(#node-glow)" />}
                <rect width={CARD_WIDTH} height={CARD_HEIGHT} rx="14" fill="#101114" stroke={active ? "#ffffff" : isMain ? "#22d3ee" : "#a855f7"} strokeOpacity={active ? 1 : 0.7} strokeWidth="1.5" />
                <circle cx="0" cy={CARD_HEIGHT / 2} r="6" fill="#a5afc0" />
                <circle cx={CARD_WIDTH} cy={CARD_HEIGHT / 2} r="6" fill="#a5afc0" />
                <text x="16" y="21" fill={isMain ? "#67e8f9" : "#d8b4fe"} fontFamily="monospace" fontSize="10" fontWeight="700">STEP {String(graph.order.get(commit.hash) ?? 0).padStart(2, "0")}</text>
                <text x="16" y="42" fill="#f8fafc" fontSize="13" fontWeight="600">{commit.message.slice(0, 24)}{commit.message.length > 24 ? "…" : ""}</text>
                <text x="16" y="60" fill="#94a3b8" fontFamily="monospace" fontSize="10">{commit.short_hash} · {commit.author.slice(0, 16)}</text>
              </g>
            )
          })}
        </g>
      </svg>

      <div className="border-t border-white/10 bg-black/20 px-5 py-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-fuchsia-300/70">Growth timeline</p>
            <p className="mt-1 text-xs text-white/45">
              {growthStep === 0 ? "Live tree" : `Commit ${Math.min(growthStep, graph.commits.length)} of ${graph.commits.length}`}
            </p>
          </div>
          <button
            type="button"
            className="rounded-full border border-white/15 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-white/70 transition hover:border-fuchsia-300/60 hover:text-white"
            onClick={() => {
              if (growthStep >= graph.commits.length || growthStep === 0) setGrowthStep(1)
              setIsGrowing((current) => !current)
            }}
          >
            {isGrowing ? "Pause" : growthStep >= graph.commits.length ? "Replay" : "Play growth"}
          </button>
        </div>
        <input
          aria-label="Repository growth timeline"
          type="range"
          min="0"
          max={graph.commits.length}
          value={growthStep}
          onChange={(event) => {
            setIsGrowing(false)
            setGrowthStep(Number(event.target.value))
          }}
          className="mt-4 h-1 w-full cursor-pointer accent-fuchsia-400"
        />
        <div className="mt-2 flex justify-between font-mono text-[10px] text-white/30">
          <span>origin</span>
          <span>branches emerge</span>
          <span>latest commit</span>
        </div>
      </div>

      {selected && (
        <div className="border-t border-white/10 bg-black/20 px-5 py-4">
          <p className="text-sm text-white/85">{selected.message}</p>
          <p className="mt-1 font-mono text-[11px] text-white/40">
            {selected.author} · {new Date(selected.date).toLocaleString()} · {selected.hash}
          </p>
        </div>
      )}
    </div>
  )
}
