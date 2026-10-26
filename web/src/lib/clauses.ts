// The 10 clause types. See docs/superpowers/specs/2026-10-26-lensor-ui.md section 3.
export type Family = 'term' | 'exit' | 'money' | 'law'

export type ClauseInfo = { cuad: string; plain: string; family: Family }

export const CLAUSES: ClauseInfo[] = [
  { cuad: 'Expiration Date', plain: 'End date', family: 'term' },
  { cuad: 'Renewal Term', plain: 'Automatic renewal', family: 'term' },
  { cuad: 'Notice Period to Terminate Renewal', plain: 'Notice to stop renewal', family: 'term' },
  { cuad: 'Governing Law', plain: 'Governing law', family: 'law' },
  { cuad: 'Termination for Convenience', plain: 'Ending early', family: 'exit' },
  { cuad: 'Change of Control', plain: 'Company sale', family: 'exit' },
  { cuad: 'Anti-Assignment', plain: 'Passing it on', family: 'exit' },
  { cuad: 'Non-Compete', plain: 'Non-compete', family: 'law' },
  { cuad: 'Cap on Liability', plain: 'Limit on what you owe', family: 'money' },
  { cuad: 'Uncapped Liability', plain: 'No limit', family: 'money' },
]

const BY_CUAD = new Map(CLAUSES.map((c) => [c.cuad, c]))

export function clauseInfo(cuad: string): ClauseInfo {
  return BY_CUAD.get(cuad) ?? { cuad, plain: cuad, family: 'law' }
}

export const FAMILY_COLOR: Record<Family, string> = {
  term: 'var(--fam-term)',
  exit: 'var(--fam-exit)',
  money: 'var(--fam-money)',
  law: 'var(--fam-law)',
}
