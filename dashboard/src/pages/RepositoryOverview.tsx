import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Play, BarChart3, AlertTriangle, Info, FileText } from 'lucide-react'

export default function RepositoryOverview() {
  const { id } = useParams<{ id: string }>()
  const repoId = id ? Number(id) : 0
  const [repo, setRepo] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api
      .get(`/repositories/${repoId}`)
      .then((res) => setRepo(res.data))
      .finally(() => setLoading(false))
  }, [repoId])

  const handleAnalyze = async () => {
    try {
      await api.post(`/analysis/${repoId}`)
      navigate(`/repositories/${repoId}`)
    } catch (err) {
      console.error('Failed to start analysis', err)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!repo) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <AlertTriangle className="w-16 h-16 mb-4 opacity-50" />
        <p className="text-lg">Repository not found</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Repository Overview</h1>
          <p className="text-gray-600 mt-1">{repo.local_path}</p>
        </div>
        <button
          onClick={handleAnalyze}
          disabled={repo.status === 'running'}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play className="w-4 h-4" /> Start Analysis
        </button>
      </div>

      <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
            <div className="text-xs text-blue-600 font-semibold uppercase mb-1">ID</div>
            <div className="text-xl font-semibold text-gray-900">#{repo.id}</div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 font-semibold uppercase mb-1">Status</div>
            <div className={`text-lg font-semibold ${
              repo.status === 'analyzed' ? 'text-green-700' : 'text-gray-700'
            }`}>
              {repo.status.charAt(0).toUpperCase() + repo.status.slice(1)}
            </div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 font-semibold uppercase mb-1">Path</div>
            <div className="text-sm font-medium text-gray-900 truncate" title={repo.local_path}>
              {repo.local_path}
            </div>
          </div>
          <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="text-xs text-gray-600 font-semibold uppercase mb-1">Created</div>
            <div className="text-sm font-medium text-gray-900">
              {new Date(repo.created_at).toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-600" /> Analysis Jobs
          </h2>
          <div className="text-center py-8 text-gray-500">
            <Info className="w-8 h-8 mb-2 opacity-50" />
            <p>No analysis jobs yet. Start an analysis to see results.</p>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-600" /> Quick Links
          </h2>
          <div className="space-y-3">
            <Link
              to="/graph"
              className="flex items-center gap-2 px-4 py-3 bg-gray-50 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-200 transition-colors"
            >
              <BarChart3 className="w-4 h-4 text-blue-600" /> Dependency Graph
            </Link>
            <Link
              to="/risk"
              className="flex items-center gap-2 px-4 py-3 bg-gray-50 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-200 transition-colors"
            >
              <AlertTriangle className="w-4 h-4 text-blue-600" /> Risk Heatmap
            </Link>
            <Link
              to="/impact"
              className="flex items-center gap-2 px-4 py-3 bg-gray-50 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-200 transition-colors"
            >
              <FileText className="w-4 h-4 text-blue-600" /> Change Impact
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
