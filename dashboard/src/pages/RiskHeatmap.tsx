import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ModuleRisk } from '../types'
import { RefreshCw, AlertTriangle, Info, AlertCircle } from 'lucide-react'

const levelColor = (level: string) => {
  switch (level) {
    case 'critical': return 'bg-red-100 text-red-700 border border-red-200'
    case 'high': return 'bg-orange-100 text-orange-700 border border-orange-200'
    case 'medium': return 'bg-yellow-100 text-yellow-700 border border-yellow-200'
    default: return 'bg-green-100 text-green-700 border border-green-200'
  }
}

export default function RiskHeatmap() {
  const [report, setReport] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadRisk()
  }, [])

  const loadRisk = async () => {
    try {
      setLoading(true)
      const reposRes = await api.get('/repositories')
      const repos = reposRes.data
      if (repos.length === 0) {
        setError('No repositories registered. Register one first.')
        setLoading(false)
        return
      }
      const repoId = repos[0].id
      const res = await api.get(`/risk/${repoId}`)
      setReport(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load risk report')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96">
        <RefreshCw className="w-10 h-10 text-blue-600 animate-spin mb-4" />
        <p className="text-gray-600">Loading risk heatmap...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <AlertCircle className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg">{error}</p>
      </div>
    )
  }

  if (!report || report.modules.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <Info className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg">No risk data available</p>
        <p className="text-sm">Run an analysis first to generate risk scores.</p>
      </div>
    )
  }

  const modules = report.modules.slice(0, 20)
  const summary = report.summary || {}

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Risk Heatmap</h1>
          <p className="text-gray-600 mt-1">
            Heuristic risk scores for modules based on complexity, change frequency,
            contributors, centrality, bug-fix history, and churn.
          </p>
        </div>
        <button
          onClick={loadRisk}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-1 uppercase tracking-wider">Total Modules</h3>
          <p className="text-2xl font-bold text-gray-900">{summary.total_modules ?? 0}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-1 uppercase tracking-wider">Avg Risk Score</h3>
          <p className="text-2xl font-bold text-gray-900">{summary.average_risk_score ?? 0}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-1 uppercase tracking-wider">Max Risk Score</h3>
          <p className="text-2xl font-bold text-gray-900">{summary.max_risk_score ?? 0}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow border border-gray-200">
          <h3 className="text-xs font-semibold text-gray-900 mb-1 uppercase tracking-wider">Critical/High</h3>
          <p className="text-2xl font-bold text-red-600">
            {(summary.critical_count ?? 0) + (summary.high_count ?? 0)}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Priority</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Module</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Score</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Level</th>
              <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Explanation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {modules.map((m: ModuleRisk, i: number) => (
              <tr key={m.path} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded-full text-xs font-bold ${i < 3 ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-600'}`}>
                    #{m.investigation_priority}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="font-medium text-gray-900 truncate max-w-xs" title={m.path}>
                    {m.path}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="font-mono text-sm font-medium text-gray-900">{m.total_score}</div>
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold ${levelColor(m.risk_level)}`}>
                    {m.risk_level.charAt(0).toUpperCase() + m.risk_level.slice(1)}
                  </span>
                </td>
                <td className="px-6 py-4">
                  <div className="text-sm text-gray-600 truncate max-w-xs" title={m.explanation}>
                    {m.explanation}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modules.length > 0 && (
        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-blue-600" /> Top Risk Details
          </h2>
          <div className="space-y-4">
            {modules.slice(0, 3).map((m: ModuleRisk) => (
              <div key={m.path} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="font-semibold text-gray-900">{m.path}</div>
                    <div className="text-sm text-gray-500">Priority #{m.investigation_priority}</div>
                  </div>
                  <span className={`text-sm font-semibold ${levelColor(m.risk_level)}`}>
                    {m.total_score} - {m.risk_level}
                  </span>
                </div>
                <div className="flex gap-4 mb-3">
                  {m.features.slice(0, 4).map((f: any) => (
                    <div key={f.name} className="flex-1 p-3 bg-white rounded border border-gray-200">
                      <div className="text-xs text-gray-500 uppercase mb-1">{f.name}</div>
                      <div className="text-lg font-mono font-bold text-gray-900">{f.score.toFixed(1)}</div>
                    </div>
                  ))}
                </div>
                <div className="text-xs text-gray-600">{m.explanation}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
