/** Configuration problems reported by the backend's static checks. */

import { create } from 'zustand'

import type { ValidationIssue } from '@/types'

interface ValidationState {
  issues: ValidationIssue[]
  valid: boolean
  checkedAt: number | null
  setResult: (valid: boolean, issues: ValidationIssue[]) => void
  clear: () => void
}

export const useValidationStore = create<ValidationState>()((set) => ({
  issues: [],
  valid: true,
  checkedAt: null,
  setResult: (valid, issues) => set({ valid, issues, checkedAt: Date.now() }),
  clear: () => set({ issues: [], valid: true, checkedAt: null }),
}))

export function issuesForDevice(issues: ValidationIssue[], deviceId: string) {
  return issues.filter((issue) => issue.device_id === deviceId)
}
