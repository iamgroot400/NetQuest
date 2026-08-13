import { ReactFlowProvider } from '@xyflow/react'
import { Settings2, Target } from 'lucide-react'
import { useEffect } from 'react'

import { BottomDock } from '@/components/BottomDock'
import { Toaster } from '@/components/Toaster'
import { TopBar } from '@/components/TopBar'
import { Tabs, type TabDefinition } from '@/components/ui/Tabs'
import { ChallengeBriefing } from '@/features/challenges/ChallengeBriefing'
import { ChallengeList } from '@/features/challenges/ChallengeList'
import { MissionComplete } from '@/features/challenges/MissionComplete'
import { ConfigPanel } from '@/features/devices/ConfigPanel'
import { PlaybackControls } from '@/features/packets/PlaybackControls'
import { Canvas } from '@/features/topology/Canvas'
import { DevicePalette } from '@/features/topology/DevicePalette'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { usePlaybackClock } from '@/hooks/usePlaybackClock'
import { useTopologyValidation } from '@/hooks/useTopologyValidation'
import {
  selectInspectorOpen,
  selectSidebarOpen,
  useUiStore,
  type RightTab,
} from '@/stores/uiStore'

/** Below this the canvas gets the whole window and the panels become overlays. */
const WIDE_LAYOUT = '(min-width: 1024px)'

export default function App() {
  usePlaybackClock()
  useTopologyValidation()

  const wide = useMediaQuery(WIDE_LAYOUT)
  const setWide = useUiStore((state) => state.setWide)
  useEffect(() => setWide(wide), [wide, setWide])

  const sidebarOpen = useUiStore(selectSidebarOpen)
  const inspectorOpen = useUiStore(selectInspectorOpen)
  const rightTab = useUiStore((state) => state.rightTab)
  const setRightTab = useUiStore((state) => state.setRightTab)

  const rightTabs: TabDefinition<RightTab>[] = [
    { id: 'config', label: 'Config', icon: <Settings2 size={12} /> },
    { id: 'mission', label: 'Mission', icon: <Target size={12} /> },
  ]

  return (
    <div className="flex h-full flex-col overflow-hidden bg-base">
      <TopBar />

      <div className="relative flex min-h-0 flex-1">
        <aside
          className={`absolute inset-y-0 left-0 z-30 w-60 shrink-0 flex-col overflow-y-auto border-r border-line bg-surface lg:relative ${
            sidebarOpen ? 'flex' : 'hidden'
          }`}
          aria-label="Devices and missions"
        >
          <DevicePalette />
          <div className="h-px bg-line" />
          <ChallengeList />
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="relative min-h-0 flex-1">
            <ReactFlowProvider>
              <Canvas />
              <PlaybackControls />
            </ReactFlowProvider>
          </div>
          <BottomDock />
        </main>

        <aside
          className={`absolute inset-y-0 right-0 z-30 w-[320px] shrink-0 flex-col border-l border-line bg-surface lg:relative ${
            inspectorOpen ? 'flex' : 'hidden'
          }`}
          aria-label="Device configuration and mission briefing"
        >
          <Tabs tabs={rightTabs} active={rightTab} onChange={setRightTab} />
          <div className="min-h-0 flex-1">
            {rightTab === 'config' ? <ConfigPanel /> : <ChallengeBriefing />}
          </div>
        </aside>
      </div>

      <MissionComplete />
      <Toaster />
    </div>
  )
}
