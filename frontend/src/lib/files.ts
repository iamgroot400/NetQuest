/** Saving and loading topologies as plain JSON files. */

import type { TopologyDocument } from '@/types'
import { TOPOLOGY_VERSION } from '@/types'

export function downloadTopology(document_: TopologyDocument) {
  const safeName =
    document_.name.trim().replace(/[^\w\-. ]+/g, '').replace(/\s+/g, '-') || 'network'
  const blob = new Blob([JSON.stringify(document_, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${safeName}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}

export class TopologyFileError extends Error {}

/** Parse and sanity-check a file the user picked. */
export async function readTopologyFile(file: File): Promise<TopologyDocument> {
  let parsed: unknown
  try {
    parsed = JSON.parse(await file.text())
  } catch {
    throw new TopologyFileError('That file is not valid JSON.')
  }

  if (typeof parsed !== 'object' || parsed === null) {
    throw new TopologyFileError('That file does not contain a network.')
  }

  const candidate = parsed as Partial<TopologyDocument>
  if (!Array.isArray(candidate.devices) || !Array.isArray(candidate.links)) {
    throw new TopologyFileError(
      'That file has no "devices" and "links" — it is not a NetQuest network.',
    )
  }
  if (candidate.version !== undefined && candidate.version > TOPOLOGY_VERSION) {
    throw new TopologyFileError(
      `This file was saved by a newer version of NetQuest (v${candidate.version}).`,
    )
  }

  return {
    version: TOPOLOGY_VERSION,
    name: typeof candidate.name === 'string' ? candidate.name : 'Imported network',
    devices: candidate.devices,
    links: candidate.links,
  }
}
