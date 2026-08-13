import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import { useEffect } from 'react'

import { useUiStore, type Toast } from '@/stores/uiStore'

const TONE: Record<Toast['tone'], { className: string; icon: typeof Info }> = {
  info: { className: 'border-line bg-panel text-ink-dim', icon: Info },
  success: { className: 'border-ok/30 bg-ok/10 text-ok', icon: CircleCheck },
  error: { className: 'border-bad/30 bg-bad/10 text-bad', icon: CircleAlert },
}

const DISMISS_AFTER_MS = 4500

export function Toaster() {
  const toast = useUiStore((state) => state.toast)
  const dismiss = useUiStore((state) => state.dismissToast)

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(dismiss, DISMISS_AFTER_MS)
    return () => window.clearTimeout(timer)
  }, [toast, dismiss])

  if (!toast) return null
  const { className, icon: Icon } = TONE[toast.tone]

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-4 right-4 z-40 flex max-w-sm items-start gap-2 rounded-lg border px-3 py-2 text-xs leading-relaxed shadow-xl ${className}`}
    >
      <Icon size={14} className="mt-px shrink-0" />
      <span className="min-w-0">{toast.text}</span>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss"
        className="-mr-1 shrink-0 opacity-60 transition-opacity hover:opacity-100"
      >
        <X size={13} />
      </button>
    </div>
  )
}
