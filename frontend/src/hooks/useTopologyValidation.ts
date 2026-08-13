import { useEffect } from 'react'

import { api } from '@/lib/api'
import { toDocument, useTopologyStore } from '@/stores/topologyStore'
import { useValidationStore } from '@/stores/validationStore'

/**
 * Re-checks the topology shortly after it stops changing, so misconfigurations
 * surface on the device badges without a request per keystroke.
 */
export function useTopologyValidation() {
  const devices = useTopologyStore((state) => state.devices)
  const links = useTopologyStore((state) => state.links)

  useEffect(() => {
    if (devices.length === 0) {
      useValidationStore.getState().clear()
      return
    }

    let cancelled = false
    const timer = window.setTimeout(async () => {
      try {
        const result = await api.validateTopology(toDocument())
        if (!cancelled) {
          useValidationStore.getState().setResult(result.valid, result.issues)
        }
      } catch {
        // The panel already reports a lost backend; badges just stay as they are.
      }
    }, 400)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [devices, links])
}
