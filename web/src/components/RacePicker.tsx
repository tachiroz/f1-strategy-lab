import type { RaceSummary } from '../api/types'
import { Segmented, Select } from './Select'

interface RacePickerProps {
  races: readonly RaceSummary[]
  value: number
  onChange: (raceId: number) => void
  /** Races the simulator cannot run are listed but cannot be picked. */
  simulatableOnly?: boolean
}

export function RacePicker({ races, value, onChange, simulatableOnly = false }: RacePickerProps) {
  const seasons = [...new Set(races.map((race) => race.season))]
  const current = races.find((race) => race.race_id === value)
  const season = current?.season ?? seasons.at(-1)
  const inSeason = races.filter((race) => race.season === season)

  function pickSeason(next: number) {
    const candidates = races.filter((race) => race.season === next)
    const first = candidates.find((race) => race.simulatable) ?? candidates[0]
    if (first) onChange(first.race_id)
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <Segmented
        label="Сезон"
        value={season ?? 0}
        options={seasons.map((item) => ({ value: item, label: item }))}
        onChange={pickSeason}
      />
      <Select
        label="Гонка"
        value={String(value)}
        onChange={(raceId) => onChange(Number(raceId))}
        className="w-full sm:w-80"
        options={inSeason.map((race) => ({
          value: String(race.race_id),
          label: `${String(race.round).padStart(2, '0')} · ${race.race_name}${
            race.simulatable ? '' : ' (нет симуляции)'
          }`,
          disabled: simulatableOnly && !race.simulatable,
        }))}
      />
    </div>
  )
}
