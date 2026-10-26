// The 10 clause types. See docs/superpowers/specs/2026-10-26-lensor-ui.md section 3.
export type Family = 'term' | 'exit' | 'money' | 'law'

/** `missing` is the text when Lensor found no such clause. It states a finding, not a legal view. */
export type ClauseInfo = { cuad: string; plain: string; family: Family; missing: string }

export const CLAUSES: ClauseInfo[] = [
  {
    cuad: 'Expiration Date',
    plain: 'End date',
    family: 'term',
    missing: 'Lensor found no end date.',
  },
  {
    cuad: 'Renewal Term',
    plain: 'Automatic renewal',
    family: 'term',
    missing: 'Lensor found no automatic renewal.',
  },
  {
    cuad: 'Notice Period to Terminate Renewal',
    plain: 'Notice to stop renewal',
    family: 'term',
    missing: 'Lensor found no notice period to stop a renewal.',
  },
  {
    cuad: 'Governing Law',
    plain: 'Governing law',
    family: 'law',
    missing: 'Lensor found no clause that names the governing law.',
  },
  {
    cuad: 'Termination for Convenience',
    plain: 'Ending early',
    family: 'exit',
    missing: 'Lensor found no right to end the contract without a reason.',
  },
  {
    cuad: 'Change of Control',
    plain: 'Company sale',
    family: 'exit',
    missing: 'Lensor found no rule for the sale of a company.',
  },
  {
    cuad: 'Anti-Assignment',
    plain: 'Passing it on',
    family: 'exit',
    missing: 'Lensor found no limit on passing the contract to another company.',
  },
  {
    cuad: 'Non-Compete',
    plain: 'Non-compete',
    family: 'law',
    missing: 'Lensor found no clause that limits work with competitors.',
  },
  {
    cuad: 'Cap on Liability',
    plain: 'Limit on what you owe',
    family: 'money',
    missing: 'Lensor found no general limit on what a party could owe.',
  },
  {
    cuad: 'Uncapped Liability',
    plain: 'No limit',
    family: 'money',
    missing: 'Lensor found no claim without a limit.',
  },
]

const BY_CUAD = new Map(CLAUSES.map((c) => [c.cuad, c]))

export function clauseInfo(cuad: string): ClauseInfo {
  return BY_CUAD.get(cuad) ?? { cuad, plain: cuad, family: 'law', missing: 'Lensor found no such clause.' }
}

export const FAMILY_COLOR: Record<Family, string> = {
  term: 'var(--fam-term)',
  exit: 'var(--fam-exit)',
  money: 'var(--fam-money)',
  law: 'var(--fam-law)',
}
