import axios, { AxiosInstance } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const registerRepository = (data: {
  repo_url?: string | null
  local_path: string
  status?: string
}) => api.post('/repositories', data)

export const listRepositories = () => api.get('/repositories')

export const getRepository = (id: number) => api.get(`/repositories/${id}`)

export const startAnalysis = (repoId: number) =>
  api.post(`/analysis/${repoId}`)

export const getAnalysis = (jobId: number) =>
  api.get(`/analysis/${jobId}`)

export const getGraph = (repoId: number) =>
  api.get(`/graph/${repoId}`)

export const getRisk = (repoId: number) =>
  api.get(`/risk/${repoId}`)

export const getImpact = (repoId: number, target: string, targetFile?: string) =>
  api.get(`/impact/${repoId}`, { params: { target, target_file: targetFile } })

export const getSummary = (repoId: number) =>
  api.get(`/repositories/${repoId}/summary`)
