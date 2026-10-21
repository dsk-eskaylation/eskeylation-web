export interface CreditMember { name: string; media_id?: number }
export interface CreditGroup { role: string; members: CreditMember[] }

export function creditMember(value: unknown): CreditMember | null {
  if (!value || typeof value !== 'object') return null
  const item = value as Record<string, unknown>
  if (typeof item.name !== 'string') return null
  return {
    name: item.name,
    ...(typeof item.media_id === 'number' && Number.isSafeInteger(item.media_id) && item.media_id > 0
      ? { media_id: item.media_id } : {}),
  }
}

/** Read both the original names-only credits and the editable member records. */
export function creditGroups(value: unknown): CreditGroup[] {
  if (!Array.isArray(value)) return []
  return value.filter((group) => group && typeof group.role === 'string').map((group) => ({
    role: group.role,
    members: Array.isArray(group.members)
      ? group.members.map(creditMember).filter((member: CreditMember | null): member is CreditMember => member !== null)
      : (Array.isArray(group.names) ? group.names : []).filter((name: unknown): name is string => typeof name === 'string').map((name: string) => ({ name })),
  }))
}
