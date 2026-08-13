import {
  FilePlus2,
  FolderOpen,
  PanelLeft,
  PanelRight,
  Save,
  TriangleAlert,
} from 'lucide-react'
import { useRef, useState, useEffect } from 'react'

import { Button, IconButton } from '@/components/ui/Button'
import { TopologyFileError, downloadTopology, readTopologyFile } from '@/lib/files'
import { LEVELS, levelForXp, nextLevel, useProgressStore } from '@/stores/progressStore'
import { toExportDocument, useTopologyStore } from '@/stores/topologyStore'
import { useUiStore } from '@/stores/uiStore'
import { useValidationStore } from '@/stores/validationStore'

export function TopBar() {
  const name = useTopologyStore((state) => state.name)
  const rename = useTopologyStore((state) => state.rename)
  const reset = useTopologyStore((state) => state.reset)
  const loadDocument = useTopologyStore((state) => state.loadDocument)
  const deviceCount = useTopologyStore((state) => state.devices.length)

  const xp = useProgressStore((state) => state.xp)
  const notify = useUiStore((state) => state.notify)
  const toggleSidebar = useUiStore((state) => state.toggleSidebar)
  const toggleInspector = useUiStore((state) => state.toggleInspector)

  const errorCount = useValidationStore(
    (state) => state.issues.filter((i) => i.severity === 'error').length,
  )

  const fileRef = useRef<HTMLInputElement>(null)
  const [draftName, setDraftName] = useState(name)
  useEffect(() => setDraftName(name), [name])

  const level = levelForXp(xp)
  const upcoming = nextLevel(xp)
  const progress = upcoming
    ? ((xp - level.xp) / (upcoming.xp - level.xp)) * 100
    : 100

  const onPickFile = async (file: File | undefined) => {
    if (!file) return
    try {
      loadDocument(await readTopologyFile(file))
      notify(`Loaded ${file.name}.`, 'success')
    } catch (error) {
      notify(
        error instanceof TopologyFileError ? error.message : 'Could not read that file.',
        'error',
      )
    }
  }

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-surface px-3">
      <IconButton label="Toggle the left panel" onClick={toggleSidebar}>
        <PanelLeft size={14} />
      </IconButton>

      <span className="flex items-center gap-2">
        <span
          aria-hidden
          className="flex h-6 w-6 items-center justify-center rounded bg-ok/15 text-ok"
        >
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 4v5M12 15v5M6 12h12" strokeLinecap="round" />
            <circle cx="12" cy="12" r="2" fill="currentColor" stroke="none" />
          </svg>
        </span>
        <span className="text-[13px] font-bold tracking-widest text-ink">NETQUEST</span>
      </span>

      <div className="mx-1 hidden h-5 w-px bg-line sm:block" />

      <input
        value={draftName}
        aria-label="Network name"
        onChange={(event) => setDraftName(event.target.value)}
        onBlur={() => rename(draftName.trim() || 'Untitled network')}
        onKeyDown={(event) => event.key === 'Enter' && event.currentTarget.blur()}
        className="hidden h-7 w-40 rounded border border-transparent bg-transparent px-2 text-[12px] text-ink-dim transition-colors hover:border-line focus:border-accent focus:outline-none sm:block"
      />

      <div className="ml-auto flex items-center gap-2">
        {errorCount > 0 ? (
          <span
            className="hidden items-center gap-1 rounded border border-bad/30 bg-bad/10 px-2 py-1 text-[11px] text-bad md:flex"
            title="Open a device to see the details"
          >
            <TriangleAlert size={12} />
            {errorCount} config error{errorCount > 1 ? 's' : ''}
          </span>
        ) : null}

        <div className="hidden w-40 lg:block">
          <div className="mb-0.5 flex items-baseline justify-between text-[10px]">
            <span className="font-medium text-ink-dim">
              Level {level.level} · {level.name}
            </span>
            <span className="font-mono text-ink-faint tabular-nums">{xp} XP</span>
          </div>
          <div
            className="h-1 overflow-hidden rounded-full bg-raised"
            title={
              upcoming
                ? `${upcoming.xp - xp} XP to level ${upcoming.level} (${upcoming.name})`
                : `Top level of ${LEVELS.length}`
            }
          >
            <div
              className="h-full rounded-full bg-ok transition-[width] duration-500"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
        </div>

        <div className="mx-1 hidden h-5 w-px bg-line lg:block" />

        <Button
          size="sm"
          onClick={() => {
            if (deviceCount > 0 && !window.confirm('Clear the canvas and start over?')) return
            reset()
          }}
        >
          <FilePlus2 size={13} />
          <span className="hidden md:inline">New</span>
        </Button>

        <Button size="sm" onClick={() => fileRef.current?.click()}>
          <FolderOpen size={13} />
          <span className="hidden md:inline">Load</span>
        </Button>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={(event) => {
            void onPickFile(event.target.files?.[0])
            event.target.value = ''
          }}
        />

        <Button
          size="sm"
          variant="primary"
          disabled={deviceCount === 0}
          onClick={() => downloadTopology(toExportDocument())}
        >
          <Save size={13} />
          <span className="hidden md:inline">Save</span>
        </Button>

        <IconButton label="Toggle the right panel" onClick={toggleInspector}>
          <PanelRight size={14} />
        </IconButton>
      </div>
    </header>
  )
}
