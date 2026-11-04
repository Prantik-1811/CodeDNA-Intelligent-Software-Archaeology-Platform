import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ImpactReport } from '../types'
import { RefreshCw, Search, Terminal, AlertCircle } from 'lucide-react'

const scoreColor = (score: number) => {
  if (score >= 70) return 'text-red-600 font-bold'
  if (score >= 45) return 'text-orange-600 font-bold'
  if (score >= 20) return 'text-yellow-600 font-bold'
  return 'text-green-600 font-bold'
}

export default function ChangeImpact() {
  const [report, setReport] = useState<ImpactReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [target, setTarget] = useState('authenticate_user')
  const [targetFile, setTargetFile] = useState('')

  useEffect(() => {
    loadImpact()
  }, [target, targetFile])

  const loadImpact = async () => {
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
      const res = await api.get(`/impact/${repoId}`, {
        params: { target, target_file: targetFile || undefined },
      })
      setReport(res.data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load impact report')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96">
        <RefreshCw className="w-10 h-10 text-blue-600 animate-spin mb-4" />
        <p className="text-gray-600">Analyzing change impact...</p>
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

  if (!report) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <Terminal className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg">No impact data available</p>
        <p className="text-sm">Enter a function or file to analyze its change impact.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Change Impact Explorer</h1>
            <p className="text-gray-600 mt-1">
              Identify which components are affected when you modify a function or file.
            </p>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Function name (e.g. authenticate_user)"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none w-64"
            />
            <input
              type="text"
              placeholder="File path (optional)"
              value={targetFile}
              onChange={(e) => setTargetFile(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none w-64"
            />
            <button
              onClick={loadImpact}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              <Search className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 font-semibold uppercase mb-1">Risk Score</div>
            <div className={`text-2xl font-bold ${scoreColor(report.risk_score)}`}>
              {report.risk_score}
            </div>
            <div className={`text-xs font-semibold capitalize ${report.risk_level.includes('critical') || report.risk_level.includes('high') ? 'text-red-600' : report.risk_level === 'medium' ? 'text-yellow-600' : 'text-green-600'}`}>
              {report.risk_level}
            </div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 font-semibold uppercase mb-1">Direct Callers</div>
            <div className="text-2xl font-bold text-gray-900">{report.direct_callers.length}</div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 font-semibold uppercase mb-1">Affected Tests</div>
            <div className="text-2xl font-bold text-gray-900">{report.affected_tests.length}</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Direct Callers</h2>
          {report.direct_callers.length === 0 ? (
            <p className="text-gray-500 text-sm">No direct callers found.</p>
          ) : (
            <ul className="space-y-3">
              {report.direct_callers.map((c, i) => (
                <li key={i} className="p-3 bg-gray-50 rounded border border-gray-200">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium text-gray-900">{c.label}</div>
                      <div className="text-xs text-gray-500">{c.file_path}:{c.line}</div>
                    </div>
                    <div className={`text-xs font-bold ${scoreColor(c.impact_score)}`}>
                      {c.impact_score.toFixed(1)}
                    </div>
                  </div>
                  <div className="text-xs text-gray-600 mt-1">
                    {c.impact_reasons.join(', ')}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Review Components</h2>
          {report.review_components.length === 0 ? (
            <p className="text-gray-500 text-sm">No review components identified.</p>
          ) : (
            <ul className="space-y-3">
              {report.review_components.slice(0, 8).map((c, i) => (
                <li key={i} className="p-3 bg-gray-50 rounded border border-gray-200">
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-medium text-gray-900 capitalize">{c.type}</div>
                      <div className="text-sm text-gray-900">{c.label}</div>
                      <div className="text-xs text-gray-500">{c.file_path}</div>
                    </div>
                    <div className={`text-xs font-bold ${scoreColor(c.impact_score)}`}>
                      {c.impact_score.toFixed(1)}
                    </div>
                  </div>
                  <div className="text-xs text-gray-600 mt-1">
                    {c.impact_reasons.slice(0, 2).join(', ')}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Affected Tests</h2>
          {report.affected_tests.length === 0 ? (
            <p className="text-gray-500 text-sm">No affected tests identified.</p>
          ) : (
            <ul className="space-y-3">
              {report.affected_tests.map((t, i) => (
                <li key={i} className="p-3 bg-blue-50 rounded border border-blue-100">
                  <div className="font-medium text-gray-900">{t.label}</div>
                  <div className="text-xs text-gray-500">{t.file_path}</div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Co-Changing Files</h2>
          {report.co_changing_files.length === 0 ? (
            <p className="text-gray-500 text-sm">No co-changing files found.</p>
          ) : (
            <ul className="space-y-3">
              {report.co_changing_files.map((c, i) => (
                <li key={i} className="p-3 bg-purple-50 rounded border border-purple-100">
                  <div className="font-medium text-gray-900">{c.label}</div>
                  <div className="text-xs text-gray-500">{c.file_path}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
