import {
  Activity,
  ChevronDown,
  ChevronUp,
  Package,
  Radar,
  TerminalIcon,
} from 'lucide-react'

import { IconButton } from '@/components/ui/Button'
import { Tabs, type TabDefinition } from '@/components/ui/Tabs'
import { ConnectionTester } from '@/features/packets/ConnectionTester'
import { EventLog } from '@/features/packets/EventLog'
import { PacketInspector } from '@/features/packets/PacketInspector'
import { Terminal } from '@/features/terminal/Terminal'
import { useSimulationStore } from '@/stores/simulationStore'
import { useUiStore, type BottomTab } from '@/stores/uiStore'

export function BottomDock() {
  const tab = useUiStore((state) => state.bottomTab)
  const setTab = useUiStore((state) => state.setBottomTab)
  const open = useUiStore((state) => state.bottomOpen)
  const toggle = useUiStore((state) => state.toggleBottom)

  const eventCount = useSimulationStore((state) => state.events.length)
  const packetCount = useSimulationStore((state) => state.packets.length)

  const tabs: TabDefinition<BottomTab>[] = [
    { id: 'terminal', label: 'Terminal', icon: <TerminalIcon size={12} /> },
    { id: 'connect', label: 'Connection Test', icon: <Radar size={12} /> },
    { id: 'events', label: 'Events', icon: <Activity size={12} />, badge: eventCount },
    { id: 'packets', label: 'Packets', icon: <Package size={12} />, badge: packetCount },
  ]

  return (
    <section
      className={`flex shrink-0 flex-col border-t border-line bg-surface transition-[height] duration-150 ${
        open ? 'h-[270px]' : 'h-9'
      }`}
      aria-label="Terminal, events and packets"
    >
      <Tabs
        tabs={tabs}
        active={tab}
        onChange={setTab}
        right={
          <IconButton label={open ? 'Collapse panel' : 'Expand panel'} onClick={toggle}>
            {open ? <ChevronDown size={13} /> : <ChevronUp size={13} />}
          </IconButton>
        }
      />
      {open ? (
        <div className="min-h-0 flex-1">
          {tab === 'terminal' ? <Terminal /> : null}
          {tab === 'connect' ? <ConnectionTester /> : null}
          {tab === 'events' ? <EventLog /> : null}
          {tab === 'packets' ? <PacketInspector /> : null}
        </div>
      ) : null}
    </section>
  )
}
