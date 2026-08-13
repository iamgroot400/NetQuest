/**
 * Typed client for the NetQuest API.
 *
 * The base path is always same-origin `/api/v1`: Vite proxies it in
 * development, nginx proxies it in the container. No environment juggling.
 */

import type {
  Challenge,
  ChallengeValidationResponse,
  CommandReference,
  CommandResponse,
  TopologyDocument,
  ValidationResponse,
} from '@/types'

const BASE = '/api/v1'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError('Cannot reach the simulation engine. Is the backend running?', 0)
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new ApiError(detail || `Request failed with ${response.status}`, response.status)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  runCommand: (topology: TopologyDocument, deviceId: string, command: string) =>
    request<CommandResponse>('/simulate/command', {
      method: 'POST',
      body: JSON.stringify({ topology, device_id: deviceId, command }),
    }),

  validateTopology: (topology: TopologyDocument) =>
    request<ValidationResponse>('/topology/validate', {
      method: 'POST',
      body: JSON.stringify(topology),
    }),

  commandReference: () => request<Record<string, CommandReference[]>>('/commands'),

  challenges: () => request<Challenge[]>('/challenges'),

  validateChallenge: (challengeId: string, topology: TopologyDocument) =>
    request<ChallengeValidationResponse>(
      `/challenges/${encodeURIComponent(challengeId)}/validate`,
      { method: 'POST', body: JSON.stringify({ topology }) },
    ),
}
