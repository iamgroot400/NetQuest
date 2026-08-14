import { ArrowDown } from 'lucide-react'
import type { ReactNode } from 'react'

import { Empty } from '@/components/ui/Field'
import { TONE_CLASS, packetLabel, packetTone } from '@/lib/packets'
import { useSimulationStore } from '@/stores/simulationStore'
import type { PacketSnapshot } from '@/types'

export function PacketInspector() {
  const packets = useSimulationStore((state) => state.packets)
  const cursor = useSimulationStore((state) => state.cursor)
  const events = useSimulationStore((state) => state.events)
  const selectedFrameUid = useSimulationStore((state) => state.selectedFrameUid)
  const selectFrame = useSimulationStore((state) => state.selectFrame)

  // Only show packets that have already been sent at the current playback point.
  const seen = new Set(
    events
      .slice(0, cursor)
      .map((event) => event.frame_uid)
      .filter((uid): uid is string => !!uid),
  )
  const visible = packets.filter((packet) => seen.has(packet.frame_uid))
  const selected =
    visible.find((packet) => packet.frame_uid === selectedFrameUid) ?? visible[0] ?? null

  if (!packets.length) {
    return (
      <Empty>
        Nothing has been captured yet. Every frame that crosses a cable is recorded
        here with its real headers.
      </Empty>
    )
  }

  return (
    <div className="flex h-full min-h-0">
      <ul className="w-[290px] shrink-0 overflow-y-auto border-r border-line-soft py-1">
        {visible.length === 0 ? (
          <li className="px-3 py-3 text-[11px] text-ink-faint">
            Play the trace to capture frames.
          </li>
        ) : null}
        {visible.map((packet) => {
          const tone = packetTone(packet)
          const isSelected = packet.frame_uid === selected?.frame_uid
          return (
            <li key={packet.frame_uid}>
              <button
                type="button"
                onClick={() => selectFrame(packet.frame_uid)}
                className={`flex w-full flex-col gap-0.5 border-l-2 px-2.5 py-1.5 text-left transition-colors hover:bg-raised ${
                  isSelected ? 'border-accent bg-raised' : 'border-transparent'
                }`}
              >
                <span className={`text-[11px] font-medium ${TONE_CLASS[tone]}`}>
                  {packetLabel(packet)}
                </span>
                <span className="truncate font-mono text-[10.5px] text-ink-faint">
                  {packet.path.join(' → ')}
                </span>
              </button>
            </li>
          )
        })}
      </ul>

      <div className="min-w-0 flex-1 overflow-y-auto p-3">
        {selected ? <PacketDetail packet={selected} /> : null}
      </div>
    </div>
  )
}

function PacketDetail({ packet }: { packet: PacketSnapshot }) {
  const tone = packetTone(packet)

  return (
    <div className="space-y-3">
      <div>
        <span className={`text-[13px] font-semibold ${TONE_CLASS[tone]}`}>
          {packetLabel(packet)}
        </span>
        <p className="font-mono text-[11px] text-ink-faint">{packet.summary}</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Group title="Ethernet">
          <Row label="Source MAC" value={packet.src_mac} />
          <Row label="Destination MAC" value={packet.dst_mac} />
          <Row label="EtherType" value={packet.ethertype} />
        </Group>

        {packet.ethertype === 'ARP' ? (
          <Group title="ARP">
            <Row label="Operation" value={packet.arp_operation} />
            <Row label="Sender IP" value={packet.arp_sender_ip} />
            <Row label="Sender MAC" value={packet.arp_sender_mac} />
            <Row label="Target IP" value={packet.arp_target_ip} />
            <Row label="Target MAC" value={packet.arp_target_mac} />
          </Group>
        ) : (
          <Group title="IPv4">
            <Row label="Source IP" value={packet.src_ip} />
            <Row label="Destination IP" value={packet.dst_ip} />
            <Row label="Protocol" value={packet.protocol} />
            <Row label="TTL" value={packet.ttl} />
            <Row label="Length" value={packet.length ? `${packet.length} bytes` : null} />
          </Group>
        )}

        {packet.transport_protocol ? (
          <Group title={packet.transport_protocol}>
            <Row label="Source port" value={packet.src_port} />
            <Row label="Destination port" value={packet.dst_port} />
            <Row label="Flag" value={packet.tcp_flag} />
          </Group>
        ) : null}

        {packet.icmp_type ? (
          <Group title="ICMP">
            <Row label="Type" value={packet.icmp_type} />
            <Row label="Code" value={packet.icmp_code} />
            <Row label="Identifier" value={packet.icmp_identifier} />
            <Row label="Sequence" value={packet.icmp_sequence} />
          </Group>
        ) : null}

        {packet.dns_query_name ? (
          <Group title="DNS">
            <Row label="Question" value={packet.dns_query_name} />
            <Row label="Type" value={packet.dns_query_type} />
            <Row label="Status" value={packet.dns_status} />
            {packet.dns_answers.length > 0 ? (
              <div className="mt-1 border-t border-line-soft pt-1">
                {packet.dns_answers.map((answer) => (
                  <p key={answer} className="font-mono text-[10.5px] text-ink-dim">
                    {answer}
                  </p>
                ))}
              </div>
            ) : null}
          </Group>
        ) : null}

        {packet.dhcp_type ? (
          <Group title="DHCP">
            <Row label="Message" value={packet.dhcp_type} />
            <Row label="Offered address" value={packet.dhcp_offered_ip} />
          </Group>
        ) : null}

        {packet.encapsulated ? (
          <Group title="Inside the tunnel">
            <p className="font-mono text-[11px] leading-relaxed text-ink-dim">
              {packet.inner_summary}
            </p>
            <p className="mt-1 text-[10.5px] leading-relaxed text-ink-faint">
              Anything inspecting this packet in transit sees only the outer UDP
              header above — not this.
            </p>
          </Group>
        ) : null}

        <Group title="Path">
          <ol className="space-y-0.5">
            {packet.path.map((hop, index) => (
              <li key={`${hop}-${index}`} className="font-mono text-[11px] text-ink-dim">
                {index > 0 ? (
                  <ArrowDown size={10} className="mb-0.5 inline text-ink-faint" />
                ) : null}{' '}
                {hop}
              </li>
            ))}
          </ol>
        </Group>
      </div>
    </div>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-md border border-line bg-panel p-2.5">
      <h4 className="mb-1.5 text-[10px] font-semibold tracking-widest text-ink-faint uppercase">
        {title}
      </h4>
      <dl className="space-y-0.5">{children}</dl>
    </section>
  )
}

function Row({ label, value }: { label: string; value: string | number | null }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="flex justify-between gap-3 text-[11px]">
      <dt className="shrink-0 text-ink-faint">{label}</dt>
      <dd className="truncate font-mono text-ink-dim">{value}</dd>
    </div>
  )
}
