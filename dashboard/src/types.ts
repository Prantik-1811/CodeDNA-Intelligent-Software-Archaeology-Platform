export interface Repository {
  id: number
  repo_url: string | null
  local_path: string
  status: string
  created_at: string
  updated_at: string
}

export interface AnalysisJob {
  id: number
  repo_id: number
  status: string
  result_json: string | null
  error: string | null
  created_at: string
  completed_at: string | null
}

export interface GraphNode {
  id: string
  type: string
  label: string
  file_path: string
  line: number
  language: string | null
}

export interface GraphEdge {
  source: string
  target: string
  type: string
  line: number
  metadata: Record<string, unknown>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  cycles: string[][]
  metrics: Record<string, unknown>
}

export interface RiskFeature {
  name: string
  raw_value: number
  normalized: number
  weight: number
  score: number
  explanation: string
}

export interface ModuleRisk {
  path: string
  total_score: number
  risk_level: string
  investigation_priority: number
  explanation: string
  features: RiskFeature[]
}

export interface RiskReport {
  summary: Record<string, unknown>
  modules: ModuleRisk[]
}

export interface ImpactComponent {
  id: string
  type: string
  label: string
  file_path: string
  line: number
  impact_score: number
  impact_reasons: string[]
  evidence: Record<string, unknown>[]
}

export interface ImpactReport {
  target_type: string
  target_label: string
  target_file: string
  risk_score: number
  risk_level: string
  direct_callers: ImpactComponent[]
  affected_modules: ImpactComponent[]
  affected_tests: ImpactComponent[]
  co_changing_files: ImpactComponent[]
  review_components: ImpactComponent[]
  summary: Record<string, unknown>
}

export interface RepositorySummary {
  repository: {
    id: number
    repo_url: string | null
    local_path: string
    status: string
  }
  message: string
}
