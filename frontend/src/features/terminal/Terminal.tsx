import { CornerDownLeft, Loader2 } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

import { Empty } from '@/components/ui/Field'
import { useCommandRunner } from '@/hooks/useCommandRunner'
import { useSimulationStore } from '@/stores/simulationStore'
import { useTerminalStore, type LineKind } from '@/stores/terminalStore'
import { useTopologyStore } from '@/stores/topologyStore'

const LINE_CLASS: Record<LineKind, string> = {
  prompt: 'text-accent',
  output: 'text-ink-dim',
  error: 'text-bad',
  system: 'text-ink-faint italic',
}

const SUGGESTIONS: Record<string, string[]> = {
  pc: ['ipconfig', 'ping ', 'arp', 'netstat', 'help'],
  server: ['ipconfig', 'ping ', 'arp', 'netstat', 'help'],
  switch: ['show mac-address-table', 'show interfaces', 'clear mac-address-table', 'help'],
  router: ['show ip route', 'show interfaces', 'show arp', 'ping ', 'help'],
}

export function Terminal() {
  const devices = useTopologyStore((state) => state.devices)
  const selectedDeviceId = useTopologyStore((state) => state.selectedDeviceId)
  const select = useTopologyStore((state) => state.select)
  const running = useSimulationStore((state) => state.running)
  const runCommand = useCommandRunner()

  const [target, setTarget] = useState<string | null>(selectedDeviceId)
  const [value, setValue] = useState('')
  const [historyIndex, setHistoryIndex] = useState<number | null>(null)

  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Follow the canvas selection, but stay put when the user deselects.
  useEffect(() => {
    if (selectedDeviceId) setTarget(selectedDeviceId)
  }, [selectedDeviceId])

  const device = devices.find((d) => d.id === target) ?? devices[0] ?? null
  const deviceId = device?.id ?? null

  const lines = useTerminalStore((state) => (deviceId ? state.buffers[deviceId] : undefined))
  const history = useTerminalStore((state) => (deviceId ? state.history[deviceId] : undefined))

  useLayoutEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [lines])

  if (!device || !deviceId) {
    return <Empty>Add a device to the canvas to open a terminal on it.</Empty>
  }

  const submit = () => {
    if (!value.trim() || running) return
    void runCommand(deviceId, value)
    setValue('')
    setHistoryIndex(null)
  }

  const recallHistory = (direction: -1 | 1) => {
    const entries = history ?? []
    if (!entries.length) return
    const nextIndex =
      historyIndex === null
        ? direction === -1
          ? entries.length - 1
          : null
        : Math.min(Math.max(historyIndex + direction, 0), entries.length - 1)

    if (nextIndex === null) return
    setHistoryIndex(nextIndex)
    setValue(entries[nextIndex] ?? '')
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-line-soft px-3 py-1.5">
        <label className="text-[11px] text-ink-faint" htmlFor="terminal-device">
          Device
        </label>
        <select
          id="terminal-device"
          value={deviceId}
          onChange={(event) => {
            setTarget(event.target.value)
            select(event.target.value)
          }}
          className="h-6 rounded border border-line bg-surface px-1.5 font-mono text-[11px] text-ink"
        >
          {devices.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <span className="ml-auto flex flex-wrap items-center gap-1">
          {(SUGGESTIONS[device.type] ?? []).map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => {
                setValue(suggestion)
                inputRef.current?.focus()
              }}
              className="rounded border border-line bg-panel px-1.5 py-0.5 font-mono text-[10px] text-ink-faint transition-colors hover:border-ink-faint hover:text-ink-dim"
            >
              {suggestion.trim()}
            </button>
          ))}
        </span>
      </div>

      <div
        ref={scrollRef}
        onClick={() => inputRef.current?.focus()}
        className="min-h-0 flex-1 cursor-text overflow-y-auto px-3 py-2 font-mono text-[12px] leading-[1.55]"
      >
        {!lines?.length ? (
          <p className="text-ink-faint">
            Terminal ready on {device.name}. Type{' '}
            <span className="text-ink-dim">help</span> to see what this device
            understands.
          </p>
        ) : (
          lines.map((line) => (
            <pre
              key={line.id}
              className={`font-mono whitespace-pre-wrap ${LINE_CLASS[line.kind]}`}
            >
              {line.text || ' '}
            </pre>
          ))
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2 border-t border-line-soft px-3 py-2">
        <span className="shrink-0 font-mono text-[12px] text-accent">{device.name}&gt;</span>
        <input
          ref={inputRef}
          value={value}
          spellCheck={false}
          autoComplete="off"
          disabled={running}
          placeholder={running ? 'Running…' : 'Type a command'}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') submit()
            else if (event.key === 'ArrowUp') {
              event.preventDefault()
              recallHistory(-1)
            } else if (event.key === 'ArrowDown') {
              event.preventDefault()
              recallHistory(1)
            }
          }}
          className="min-w-0 flex-1 bg-transparent font-mono text-[12px] text-ink outline-none placeholder:text-ink-faint disabled:opacity-50"
        />
        {running ? (
          <Loader2 size={13} className="shrink-0 animate-spin text-ink-faint" />
        ) : (
          <CornerDownLeft size={13} className="shrink-0 text-ink-faint" />
        )}
      </div>
    </div>
  )
}
