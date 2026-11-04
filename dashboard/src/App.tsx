import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import RepositoryOverview from './pages/RepositoryOverview'
import RepositoryList from './pages/RepositoryList'
import DependencyGraph from './pages/DependencyGraph'
import RiskHeatmap from './pages/RiskHeatmap'
import ChangeImpact from './pages/ChangeImpact'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 text-gray-900">
        <nav className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center text-white font-bold text-sm">
              CD
            </div>
            <span className="font-bold text-xl text-gray-800 tracking-tight">CodeDNA</span>
          </div>
          <div className="flex items-center gap-2">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              Repositories
            </NavLink>
            <NavLink
              to="/graph"
              className={({ isActive }) =>
                `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              Dependency Graph
            </NavLink>
            <NavLink
              to="/risk"
              className={({ isActive }) =>
                `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              Risk Heatmap
            </NavLink>
            <NavLink
              to="/impact"
              className={({ isActive }) =>
                `px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              Change Impact
            </NavLink>
          </div>
        </nav>

        <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<RepositoryList />} />
            <Route path="/repositories/:id" element={<RepositoryOverview />} />
            <Route path="/graph" element={<DependencyGraph />} />
            <Route path="/risk" element={<RiskHeatmap />} />
            <Route path="/impact" element={<ChangeImpact />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
