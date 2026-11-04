import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Repository } from '../types'
import { Plus, ArrowRight, LayoutList, Terminal } from 'lucide-react'

export default function RepositoryList() {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [loading, setLoading] = useState(true)
  const [newPath, setNewPath] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    api
      .get('/repositories')
      .then((res) => setRepositories(res.data))
      .finally(() => setLoading(false))
  }, [])

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newPath.trim()) return
    try {
      await api.post('/repositories', {
        local_path: newPath,
        repo_url: null,
        status: 'registered',
      })
      setNewPath('')
      const res = await api.get('/repositories')
      setRepositories(res.data)
    } catch (err) {
      console.error('Failed to register repository', err)
    }
  }

  const handleAnalyze = (id: number) => {
    navigate(`/repositories/${id}`)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Repositories</h1>
          <p className="text-gray-600 mt-1">
            Register and analyze software repositories.
          </p>
        </div>
        <form onSubmit={handleRegister} className="flex gap-2 max-w-md">
          <input
            type="text"
            placeholder="Local directory path"
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:outline-none"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            disabled={!newPath.trim()}
          >
            <Plus className="w-4 h-4 mr-2" /> Register
          </button>
        </form>
      </div>

      {repositories.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-500">
          <Terminal className="w-16 h-16 mb-4 opacity-50" />
          <p className="text-lg">No repositories registered yet</p>
          <p className="text-sm">Register a local directory to begin analysis.</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Path</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                <th className="px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {repositories.map((repo) => (
                <tr key={repo.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <LayoutList className="w-4 h-4 text-gray-400" />
                      <span className="text-gray-900 font-medium truncate">{repo.local_path}</span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      Registered {new Date(repo.created_at).toLocaleDateString()}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                      repo.status === 'analyzed'
                        ? 'bg-green-100 text-green-700'
                        : repo.status === 'running'
                          ? 'bg-yellow-100 text-yellow-700 animate-pulse'
                          : 'bg-gray-100 text-gray-700'
                    }`}>
                      {repo.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => handleAnalyze(repo.id)}
                      className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      Analyze <ArrowRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
