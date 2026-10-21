export type CompoundId = 'soft' | 'medium' | 'hard' | 'inter' | 'wet'

export interface Compound {
  id: CompoundId
  label: string
  /** Tailwind classes are spelled out in full so Tailwind can detect them. */
  swatch: string
  /** Readable text colour on top of the swatch. */
  onSwatch: string
}

export const COMPOUNDS: readonly Compound[] = [
  { id: 'soft', label: 'Soft', swatch: 'bg-tyre-soft', onSwatch: 'text-white' },
  { id: 'medium', label: 'Medium', swatch: 'bg-tyre-medium', onSwatch: 'text-black/75' },
  { id: 'hard', label: 'Hard', swatch: 'bg-tyre-hard', onSwatch: 'text-black/75' },
  { id: 'inter', label: 'Inter', swatch: 'bg-tyre-inter', onSwatch: 'text-black/75' },
  { id: 'wet', label: 'Wet', swatch: 'bg-tyre-wet', onSwatch: 'text-white' },
]

export const COMPOUND_BY_ID: Readonly<Record<CompoundId, Compound>> = Object.fromEntries(
  COMPOUNDS.map((compound) => [compound.id, compound]),
) as Record<CompoundId, Compound>
