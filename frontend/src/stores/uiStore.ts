/** Panel layout and transient notices. */

import { create } from 'zustand'

export type BottomTab = 'terminal' | 'events' | 'packets'
export type RightTab = 'config' | 'mission'

export interface Toast {
  id: number
  text: string
  tone: 'info' | 'success' | 'error'
}

interface UiState {
  toast: Toast | null
  bottomTab: BottomTab
  rightTab: RightTab
  bottomOpen: boolean

  /** True when there is room for three columns; kept in sync by the layout hook. */
  wide: boolean
  /**
   * null means "follow the window": panels are open on a wide screen and
   * closed on a narrow one. A toggle pins an explicit choice.
   */
  sidebarOpen: boolean | null
  inspectorOpen: boolean | null

  notify: (text: string, tone?: Toast['tone']) => void
  dismissToast: () => void
  setBottomTab: (tab: BottomTab) => void
  setRightTab: (tab: RightTab) => void
  toggleBottom: () => void
  toggleSidebar: () => void
  toggleInspector: () => void
  setWide: (wide: boolean) => void
}

let toastId = 0

export const useUiStore = create<UiState>()((set) => ({
  toast: null,
  bottomTab: 'terminal',
  rightTab: 'config',
  bottomOpen: true,
  wide: true,
  sidebarOpen: null,
  inspectorOpen: null,

  notify: (text, tone = 'info') => {
    toastId += 1
    set({ toast: { id: toastId, text, tone } })
  },
  dismissToast: () => set({ toast: null }),
  setBottomTab: (bottomTab) => set({ bottomTab, bottomOpen: true }),
  setRightTab: (rightTab) => set({ rightTab, inspectorOpen: true }),
  toggleBottom: () => set((state) => ({ bottomOpen: !state.bottomOpen })),
  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !(state.sidebarOpen ?? state.wide) })),
  toggleInspector: () =>
    set((state) => ({ inspectorOpen: !(state.inspectorOpen ?? state.wide) })),
  setWide: (wide) => set({ wide }),
}))

export const selectSidebarOpen = (state: UiState) => state.sidebarOpen ?? state.wide
export const selectInspectorOpen = (state: UiState) => state.inspectorOpen ?? state.wide
