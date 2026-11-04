import { useEffect, useState } from 'react'
import { api } from '../api'
import type { GraphData } from '../types'
import { RefreshCw, Terminal, AlertCircle } from 'lucide-react'

export default function DependencyGraph() {
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadGraph()
  }, [])

  const loadGraph = async () => {
    try {
      setLoading(true)
      // Get the first registered repository or use a default
      const reposRes = await api.get('/repositories')
      const repos = reposRes.data
      if (repos.length === 0) {
        setError('No repositories registered. Register one first.')
        setLoading(false)
        return
      }
      const repoId = repos[0].id
      const res = await api.get(`/graph/${repoId}`)
      setGraph(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load graph')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96">
        <RefreshCw className="w-10 h-10 text-blue-600 animate-spin mb-4" />
        <p className="text-gray-600">Loading dependency graph...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <AlertCircle className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg">{error}</p>
        <button
          onClick={loadGraph}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <Terminal className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg">No graph data available</p>
        <p className="text-sm">Run an analysis first to generate the dependency graph.</p>
      </div>
    )
  }

  const width = 800
  const height = 500
  const centerX = width / 2
  const centerY = height / 2
  const radius = Math.min(width, height) * 0.35

  // Simple circular layout
  const positionedNodes = graph.nodes.map((node, i) => {
    const angle = (i / graph.nodes.length) * 2 * Math.PI
    return {
      ...node,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    }
  })

  const nodeColor = (type: string) => {
    switch (type) {
      case 'file': return '#3b82f6'
      case 'function': return '#10b981'
      case 'class': return '#8b5cf6'
      default: return '#6b7280'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dependency Graph</h1>
          <p className="text-gray-600 mt-1">
            Visualize file-level dependencies, function calls, and class inheritance.
          </p>
        </div>
        <button
          onClick={loadGraph}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="bg-white rounded-lg shadow border border-gray-200 p-1">
        <div className="relative w-full h-[500px]">
          <svg width={width} height={height} className="w-full h-full">
            {/* Edges */}
            {graph.edges.map((edge, i) => {
              const sourceNode = positionedNodes.find((n) => n.id === edge.source)
              const targetNode = positionedNodes.find((n) => n.id === edge.target)
              if (!sourceNode || !targetNode) return null
              return (
                <line
                  key={`e-${i}`}
                  x1={sourceNode.x}
                  y1={sourceNode.y}
                  x2={targetNode.x}
                  y2={targetNode.y}
                  stroke="#cbd5e1"
                  strokeWidth={1}
                  markerEnd="url(#arrowhead)"
                />
              )
            })}
            {/* Nodes */}
            {positionedNodes.map((node, i) => {
              const color = nodeColor(node.type)
              return (
                <g key={`n-${i}`} transform={`translate(${node.x},${node.y})`}>
                  <circle
                    r={node.type === 'file' ? 10 : 7}
                    fill={color}
                    stroke="white"
                    strokeWidth={2}
                    cursor="pointer"
                  />
                  <text
                    x={0}
                    y={node.type === 'file' ? -14 : -10}
                    fontSize={10}
                    fill="#6b7280"
                    textAnchor="middle"
                    pointerEvents="none"
                  >
                    {node.label.length > 12 ? node.label.slice(0, 12) + '...' : node.label}
                  </text>
                </g>
              )
            })}
            <defs>
              <marker
                id="arrowhead"
                markerWidth="10"
                markerHeight="7"
                refX="9"
                refY="3.5"
                orient="auto"
              >
                <polygon points="0 0, 10 3.5, 0 7" fill="#cbd5e1" />
              </marker>
            </defs>
          </svg>
          <div className="absolute bottom-4 left-4 bg-white p-3 rounded-lg shadow border border-gray-200 z-10">
            <h3 className="text-xs font-semibold text-gray-900 mb-2 uppercase tracking-wider">Legend</h3>
            <div className="flex gap-4 text-xs text-gray-600">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-blue-500" />
                File
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                Function
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-purple-500" />
                Class
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-2 uppercase tracking-wider">Nodes</h3>
          <p className="text-2xl font-bold text-gray-900">{graph.nodes.length}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-2 uppercase tracking-wider">Edges</h3>
          <p className="text-2xl font-bold text-gray-900">{graph.edges.length}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-2 uppercase tracking-wider">Cycles</h3>
          <p className={`text-2xl font-bold ${graph.cycles.length > 0 ? 'text-red-600' : 'text-green-600'}`}>
            {graph.cycles.length}
          </p>
        </div>
      </div>
    </div>
  )
}
