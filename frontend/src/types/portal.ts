/** Matches the shape returned by GET /api/runs */
export interface Run {
  runId: string
  timestamp: string | null
  inputFile: string | null
}

/** Matches the shape returned by GET /api/users */
export interface User {
  id: string
  email: string
  name: string
  role: 'owner' | 'tech' | 'customer'
  created_at: string | null
}
