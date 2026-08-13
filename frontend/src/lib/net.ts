/** Address helpers used by the config forms. Validation itself lives on the backend. */

export function isValidIpv4(value: string | null | undefined): boolean {
  if (!value) return false
  const parts = value.trim().split('.')
  if (parts.length !== 4) return false
  return parts.every((part) => {
    if (!/^\d{1,3}$/.test(part)) return false
    if (part.length > 1 && part.startsWith('0')) return false
    return Number(part) <= 255
  })
}

const VALID_MASKS = new Set(
  Array.from({ length: 33 }, (_, prefix) => {
    const value = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0
    return [24, 16, 8, 0].map((shift) => (value >>> shift) & 0xff).join('.')
  }),
)

export function isValidNetmask(value: string | null | undefined): boolean {
  return !!value && VALID_MASKS.has(value.trim())
}

export function netmaskToPrefix(mask: string): number | null {
  if (!isValidNetmask(mask)) return null
  return mask
    .split('.')
    .reduce((count, octet) => count + (Number(octet).toString(2).match(/1/g)?.length ?? 0), 0)
}

/** Common masks offered as quick picks in the config panel. */
export const COMMON_MASKS = [
  '255.255.255.0',
  '255.255.0.0',
  '255.0.0.0',
  '255.255.255.128',
  '255.255.255.192',
  '255.255.255.252',
]
