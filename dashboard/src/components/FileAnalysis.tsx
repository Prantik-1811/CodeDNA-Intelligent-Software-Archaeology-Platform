import { useEffect, useMemo, useState } from "react"

interface RepositoryFile {
  path: string
  name: string
  language: string | null
  size: number
  is_source: boolean
}

interface RepositoryTree {
  files: RepositoryFile[]
  file_count: number
  directory_count: number
}

interface FileCommit {
  short_hash: string
  message: string
  author: string
  date: string
}

interface FileHistory {
  path: string
  commit_count: number
  last_modified: string | null
  last_modified_by: string | null
  contributors: string[]
  commits: FileCommit[]
}

interface FileAnalysisData {
  path: string
  what: string
  why: string
  role: string
  architecture: {
    imports: Array<{ path: string; type: string }>
    referenced_by: Array<{ path: string; type: string }>
  }
}

interface FileAnalysisProps {
  repositoryId: number
}

const apiBase = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://127.0.0.1:8001" : "")

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function FileAnalysis({ repositoryId }: FileAnalysisProps) {
  const [tree, setTree] = useState<RepositoryTree | null>(null)
  const [selectedPath, setSelectedPath] = useState("")
  const [history, setHistory] = useState<FileHistory | null>(null)
  const [analysis, setAnalysis] = useState<FileAnalysisData | null>(null)
  const [query, setQuery] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [historyLoading, setHistoryLoading] = useState(false)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError("")
    fetch(`${apiBase}/repositories/${repositoryId}/tree`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load repository files.")
        return response.json() as Promise<RepositoryTree>
      })
      .then((data) => {
        if (active) {
          setTree(data)
          setSelectedPath(data.files[0]?.path ?? "")
        }
      })
      .catch((loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load repository files.")
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [repositoryId])

  useEffect(() => {
    if (!selectedPath) {
      setHistory(null)
      setAnalysis(null)
      return
    }
    let active = true
    setHistoryLoading(true)
    const path = encodeURIComponent(selectedPath)
    fetch(`${apiBase}/repositories/${repositoryId}/files/history?path=${path}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load file history.")
        return response.json() as Promise<FileHistory>
      })
      .then((data) => {
        if (active) setHistory(data)
      })
      .catch((loadError: unknown) => {
        if (active) setError(loadError instanceof Error ? loadError.message : "Unable to load file history.")
      })
      .finally(() => {
        if (active) setHistoryLoading(false)
      })
    return () => {
      active = false
    }
  }, [repositoryId, selectedPath])

  useEffect(() => {
    if (!selectedPath) return
    let active = true
    fetch(`${apiBase}/repositories/${repositoryId}/files/analysis?path=${encodeURIComponent(selectedPath)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load file analysis.")
        return response.json() as Promise<FileAnalysisData>
      })
      .then((data) => {
        if (active) setAnalysis(data)
      })
      .catch(() => {
        if (active) setAnalysis(null)
      })
    return () => {
      active = false
    }
  }, [repositoryId, selectedPath])

  const files = useMemo(
    () => tree?.files.filter((file) => file.path.toLowerCase().includes(query.toLowerCase())) ?? [],
    [query, tree],
  )

  if (loading) return <p className="mt-10 text-sm text-white/45">Loading files…</p>
  if (error && !tree) return <p className="mt-10 text-sm text-rose-300">{error}</p>
  if (!tree) return null

  return (
    <div className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <section className="rounded-2xl border border-white/10 bg-[#111113] p-6">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-cyan-300/70">Repository files</p>
            <h2 className="mt-2 text-xl font-medium">Choose a file to inspect</h2>
          </div>
          <span className="font-mono text-xs text-white/35">{tree.file_count} files</span>
        </div>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search files"
          className="mt-5 w-full rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-cyan-300/50"
        />
        <div className="mt-4 max-h-[28rem] overflow-auto divide-y divide-white/8">
          {files.map((file) => (
            <button
              key={file.path}
              type="button"
              onClick={() => setSelectedPath(file.path)}
              className={`w-full px-2 py-3 text-left transition hover:bg-white/5 ${
                selectedPath === file.path ? "bg-cyan-300/10" : ""
              }`}
            >
              <p className="truncate font-mono text-sm text-cyan-100">{file.path}</p>
              <p className="mt-1 text-[10px] uppercase tracking-widest text-white/30">
                {file.language || "unknown"} · {formatSize(file.size)}
              </p>
            </button>
          ))}
          {!files.length && <p className="py-6 text-sm text-white/40">No matching files.</p>}
        </div>
      </section>

      <section className="rounded-2xl border border-white/10 bg-[#111113] p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-fuchsia-300/70">Git history</p>
        {historyLoading ? (
          <p className="mt-8 text-sm text-white/45">Loading file history…</p>
        ) : history ? (
          <>
            <h2 className="mt-2 break-all font-mono text-xl text-white">{history.path}</h2>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              {[
                ["Commits", history.commit_count],
                ["Contributors", history.contributors.length],
                ["Last author", history.last_modified_by || "Unknown"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-white/35">{label}</p>
                  <p className="mt-2 truncate text-lg font-semibold">{value}</p>
                </div>
              ))}
            </div>
            <p className="mt-5 text-sm text-white/55">
              Contributors: {history.contributors.join(", ") || "No contributors recorded"}
            </p>
            <ol className="mt-5 divide-y divide-white/8">
              {history.commits.slice(0, 8).map((commit) => (
                <li key={commit.short_hash} className="py-3">
                  <p className="text-sm text-white/80">{commit.message}</p>
                  <p className="mt-1 font-mono text-[10px] text-white/35">
                    {commit.short_hash} · {commit.author} · {new Date(commit.date).toLocaleDateString()}
                  </p>
                </li>
              ))}
            </ol>
            {analysis && (
              <section className="mt-8 border-t border-white/10 pt-6">
                <p className="font-mono text-[10px] uppercase tracking-[0.3em] text-cyan-300/70">AI Analysis</p>
                <div className="mt-4 grid gap-3">
                  {[
                    ["What does this code do?", analysis.what],
                    ["Why does it exist?", analysis.why],
                    ["What role does it play?", analysis.role],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-xl border border-white/10 bg-black/20 p-4">
                      <p className="text-sm font-medium text-white/85">{label}</p>
                      <p className="mt-2 text-sm leading-6 text-white/55">{value}</p>
                    </div>
                  ))}
                  <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                    <p className="text-sm font-medium text-white/85">Explain architecture / relationships</p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <div>
                        <p className="font-mono text-[10px] uppercase tracking-widest text-white/35">Imports</p>
                        <p className="mt-1 text-sm text-cyan-100">
                          {analysis.architecture.imports.map((item) => item.path).join(", ") || "No local imports detected"}
                        </p>
                      </div>
                      <div>
                        <p className="font-mono text-[10px] uppercase tracking-widest text-white/35">Referenced by</p>
                        <p className="mt-1 text-sm text-fuchsia-100">
                          {analysis.architecture.referenced_by.map((item) => item.path).join(", ") || "No references detected"}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-[10px] text-white/30">
                  Generated from static source structure and repository relationships; no code is executed.
                </p>
              </section>
            )}
          </>
        ) : (
          <p className="mt-8 text-sm text-white/45">Select a file to see its history.</p>
        )}
        {error && tree && <p className="mt-4 text-sm text-rose-300">{error}</p>}
      </section>
    </div>
  )
}
