export interface AegisData {
  meta: {
    target: string
    k: number
    live: boolean
    n_trials: number
    n_scenarios: number
    n_techniques: number
    conditions: string[]
  }
  adaptation_lift: {
    single_asr: number
    single_ci: [number, number]
    single_n: number
    adaptive_asr: number
    adaptive_ci: [number, number]
    adaptive_n: number
    lift_abs: number
    significance?: {
      b_single_fail_adaptive_success: number
      c_single_success_adaptive_fail: number
      discordant: number
      p_value: number
      significant_at_05: boolean
    }
  }
  defense_curve: {
    by_condition: Record<string, { asr: number; ci: [number, number]; n: number }>
    per_layer_marginal: Record<string, number>
    reduction_abs: number
    from_condition: string
    to_condition: string
  }
  heatmap_adaptive_none: HeatmapCell[]
  heatmap_single_none: HeatmapCell[]
  trials: Trial[]
}

export interface HeatmapCell {
  scenario: string
  technique: string
  success: boolean
  turns_used: number
  blocked_by: string | null
}

export interface TranscriptTurn {
  attacker: string
  target: string
  success: boolean
  blocked_by: string | null
}

export interface Trial {
  scenario: string
  technique: string
  mode: string
  condition: string
  success: boolean
  turns_used: number
  blocked_by: string | null
  transcript: TranscriptTurn[]
}
