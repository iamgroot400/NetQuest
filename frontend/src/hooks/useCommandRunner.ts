import { useCallback } from 'react'

import { ApiError, api } from '@/lib/api'
import { useSimulationStore } from '@/stores/simulationStore'
import { useTerminalStore } from '@/stores/terminalStore'
import { toDocument, useTopologyStore } from '@/stores/topologyStore'
import { useUiStore } from '@/stores/uiStore'

/**
 * Runs one terminal command end to end: post the topology, print the output,
 * write the learned tables back, and hand the event trace to the animator.
 */
export function useCommandRunner() {
  const notify = useUiStore((state) => state.notify)

  return useCallback(
    async (deviceId: string, command: string) => {
      const trimmed = command.trim()
      if (!trimmed) return

      const device = useTopologyStore.getState().devices.find((d) => d.id === deviceId)
      const terminal = useTerminalStore.getState()

      terminal.append(deviceId, [{ text: `${device?.name ?? 'device'}> ${trimmed}`, kind: 'prompt' }])
      terminal.remember(deviceId, trimmed)

      // Handled locally: there is nothing for the engine to simulate.
      if (trimmed === 'clear' || trimmed === 'cls') {
        terminal.clear(deviceId)
        return
      }

      const simulation = useSimulationStore.getState()
      simulation.setRunning(true)
      simulation.setError(null)

      try {
        const response = await api.runCommand(toDocument(), deviceId, trimmed)
        useTopologyStore.getState().applyDeviceState(response.device_state)
        useSimulationStore.getState().load(response.events, response.packets)
        useTerminalStore.getState().append(
          deviceId,
          response.output.map((text) => ({
            text,
            kind: response.success ? ('output' as const) : ('error' as const),
          })),
        )
        return response
      } catch (error) {
        const message =
          error instanceof ApiError ? error.message : 'The command could not be run.'
        useTerminalStore.getState().append(deviceId, [{ text: message, kind: 'error' }])
        useSimulationStore.getState().setError(message)
        notify(message, 'error')
        return undefined
      } finally {
        useSimulationStore.getState().setRunning(false)
      }
    },
    [notify],
  )
}
