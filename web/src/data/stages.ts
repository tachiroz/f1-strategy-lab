import {
  Boxes,
  Database,
  Dices,
  FileText,
  Gauge,
  LayoutDashboard,
  type LucideIcon,
} from 'lucide-react'

export type StageStatus = 'done' | 'active' | 'planned'

export interface Stage {
  id: number
  title: string
  description: string
  icon: LucideIcon
}

/** Stage in progress right now; bump it after each stage is merged into main. */
export const CURRENT_STAGE = 1

/** Project roadmap, mirrors the stages in CLAUDE.md. */
export const STAGES: readonly Stage[] = [
  {
    id: 1,
    title: 'Каркас',
    description: 'Структура репозитория, линтеры, тесты и CI для Python и веба.',
    icon: Boxes,
  },
  {
    id: 2,
    title: 'Загрузка данных',
    description: 'FastF1 и Jolpica-F1 → SQLite: круги, стинты, пит-стопы, погода и результаты.',
    icon: Database,
  },
  {
    id: 3,
    title: 'Модель шин',
    description: 'Деградация по составам с поправкой на топливо и трассу, без кругов под SC.',
    icon: Gauge,
  },
  {
    id: 4,
    title: 'Симулятор',
    description: 'Монте-Карло от 5000 прогонов: пит-стопы, Safety Car, надёжность.',
    icon: Dices,
  },
  {
    id: 5,
    title: 'Дашборд',
    description: 'Сравнение стратегий, распределение финишных позиций, чувствительность к SC.',
    icon: LayoutDashboard,
  },
  {
    id: 6,
    title: 'Разбор гонки',
    description: 'Текстовый отчёт по шаблону строго на основе данных, экспорт в Markdown.',
    icon: FileText,
  },
]

/** Status of a stage relative to the stage currently in progress. */
export function stageStatus(stageId: number, current: number = CURRENT_STAGE): StageStatus {
  if (stageId < current) return 'done'
  if (stageId === current) return 'active'
  return 'planned'
}
