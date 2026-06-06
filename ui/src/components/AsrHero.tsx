'use client'

import type { AegisData } from '@/types/aegis'

interface Props {
  adaptationLift: AegisData['adaptation_lift']
  defenseCurve: AegisData['defense_curve']
}

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`
}

function ci(lo: number, hi: number) {
  return `[${pct(lo)}, ${pct(hi)}]`
}

export function AsrHero({ adaptationLift, defenseCurve }: Props) {
  const liftPositive = adaptationLift.lift_abs >= 0
  const defReduction = defenseCurve.reduction_abs
  const fromAsr = defenseCurve.by_condition[defenseCurve.from_condition]
  const toAsr = defenseCurve.by_condition[defenseCurve.to_condition]

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <h2
          className="text-[11px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          Attack Success Rate
        </h2>
        <div
          className="flex-1 h-px"
          style={{ background: 'var(--color-border)' }}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Card A: Adaptation Lift */}
        <div
          className="rounded-xl p-6"
          style={{
            background: 'var(--color-surface-1)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div className="flex items-start justify-between mb-6">
            <div>
              <div
                className="text-xs font-semibold uppercase tracking-widest mb-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Adaptation Lift
              </div>
              <div
                className="text-xs"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Single-shot → multi-turn adaptive
              </div>
            </div>
            <div
              className="px-2 py-0.5 rounded text-[10px] font-mono"
              style={{
                background: liftPositive ? 'var(--color-attack-bg)' : 'var(--color-hold-bg)',
                color: liftPositive ? 'var(--color-attack)' : 'var(--color-hold)',
                border: `1px solid ${liftPositive ? 'var(--color-attack-border)' : 'var(--color-hold-border)'}`,
              }}
            >
              {liftPositive ? '+' : ''}{pct(adaptationLift.lift_abs)} lift
            </div>
          </div>

          {/* Big numbers */}
          <div className="flex items-center gap-4 mb-5">
            <div className="flex-1">
              <div
                className="text-[10px] uppercase tracking-wider mb-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Single-shot
              </div>
              <div
                className="text-4xl font-bold font-mono tracking-tight"
                style={{ color: 'var(--color-text-primary)' }}
              >
                {pct(adaptationLift.single_asr)}
              </div>
              <div
                className="text-[10px] font-mono mt-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                95% CI {ci(adaptationLift.single_ci[0], adaptationLift.single_ci[1])}
              </div>
            </div>

            {/* Arrow */}
            <div className="flex flex-col items-center gap-1">
              <svg width="24" height="16" viewBox="0 0 24 16" fill="none">
                <path d="M2 8H20M14 2L20 8L14 14" stroke="var(--color-accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>

            <div className="flex-1">
              <div
                className="text-[10px] uppercase tracking-wider mb-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Adaptive
              </div>
              <div
                className="text-4xl font-bold font-mono tracking-tight"
                style={{ color: liftPositive ? 'var(--color-attack)' : 'var(--color-hold)' }}
              >
                {pct(adaptationLift.adaptive_asr)}
              </div>
              <div
                className="text-[10px] font-mono mt-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                95% CI {ci(adaptationLift.adaptive_ci[0], adaptationLift.adaptive_ci[1])}
              </div>
            </div>
          </div>

          {/* Progress bar: single vs adaptive */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <div
                className="w-16 text-[10px] text-right font-mono"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                single
              </div>
              <div
                className="flex-1 h-1.5 rounded-full overflow-hidden"
                style={{ background: 'var(--color-surface-3)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: pct(adaptationLift.single_asr),
                    background: 'var(--color-text-secondary)',
                  }}
                />
              </div>
              <div
                className="w-10 text-[10px] font-mono text-right"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {pct(adaptationLift.single_asr)}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div
                className="w-16 text-[10px] text-right font-mono"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                adaptive
              </div>
              <div
                className="flex-1 h-1.5 rounded-full overflow-hidden"
                style={{ background: 'var(--color-surface-3)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: pct(adaptationLift.adaptive_asr),
                    background: 'var(--color-attack)',
                  }}
                />
              </div>
              <div
                className="w-10 text-[10px] font-mono text-right"
                style={{ color: 'var(--color-attack)' }}
              >
                {pct(adaptationLift.adaptive_asr)}
              </div>
            </div>
          </div>

          <div
            className="mt-4 pt-4 text-[11px]"
            style={{
              borderTop: '1px solid var(--color-border)',
              color: 'var(--color-text-tertiary)',
            }}
          >
            n={adaptationLift.adaptive_n} adaptive · n={adaptationLift.single_n} single · condition: none
          </div>
        </div>

        {/* Card B: Defense Reduction */}
        <div
          className="rounded-xl p-6"
          style={{
            background: 'var(--color-surface-1)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div className="flex items-start justify-between mb-6">
            <div>
              <div
                className="text-xs font-semibold uppercase tracking-widest mb-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Defense Reduction
              </div>
              <div
                className="text-xs"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                {defenseCurve.from_condition} → {defenseCurve.to_condition}
              </div>
            </div>
            <div
              className="px-2 py-0.5 rounded text-[10px] font-mono"
              style={{
                background: 'var(--color-hold-bg)',
                color: 'var(--color-hold)',
                border: '1px solid var(--color-hold-border)',
              }}
            >
              −{pct(defReduction)} ASR
            </div>
          </div>

          {/* Big numbers */}
          <div className="flex items-center gap-4 mb-5">
            <div className="flex-1">
              <div
                className="text-[10px] uppercase tracking-wider mb-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Undefended
              </div>
              <div
                className="text-4xl font-bold font-mono tracking-tight"
                style={{ color: 'var(--color-attack)' }}
              >
                {fromAsr ? pct(fromAsr.asr) : '—'}
              </div>
              {fromAsr && (
                <div
                  className="text-[10px] font-mono mt-1"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  95% CI {ci(fromAsr.ci[0], fromAsr.ci[1])}
                </div>
              )}
            </div>

            {/* Down arrow */}
            <div className="flex flex-col items-center gap-1">
              <svg width="16" height="24" viewBox="0 0 16 24" fill="none">
                <path d="M8 2V20M2 14L8 20L14 14" stroke="var(--color-hold)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>

            <div className="flex-1">
              <div
                className="text-[10px] uppercase tracking-wider mb-1"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                Full stack
              </div>
              <div
                className="text-4xl font-bold font-mono tracking-tight"
                style={{ color: 'var(--color-hold)' }}
              >
                {toAsr ? pct(toAsr.asr) : '—'}
              </div>
              {toAsr && (
                <div
                  className="text-[10px] font-mono mt-1"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  95% CI {ci(toAsr.ci[0], toAsr.ci[1])}
                </div>
              )}
            </div>
          </div>

          {/* Progress bars for each condition */}
          <div className="space-y-1.5">
            {defenseCurve.by_condition && Object.entries(defenseCurve.by_condition).map(([cond, val]) => (
              <div key={cond} className="flex items-center gap-2">
                <div
                  className="w-28 text-[10px] text-right font-mono truncate"
                  style={{ color: 'var(--color-text-tertiary)' }}
                >
                  {cond === 'none' ? 'none' : cond.replace('prompt+classifier+scan', 'full stack')}
                </div>
                <div
                  className="flex-1 h-1.5 rounded-full overflow-hidden"
                  style={{ background: 'var(--color-surface-3)' }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: pct(val.asr),
                      background: val.asr > 0.5
                        ? 'var(--color-attack)'
                        : val.asr > 0.25
                        ? 'var(--color-warn)'
                        : 'var(--color-hold)',
                    }}
                  />
                </div>
                <div
                  className="w-10 text-[10px] font-mono text-right"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {pct(val.asr)}
                </div>
              </div>
            ))}
          </div>

          <div
            className="mt-4 pt-4 text-[11px]"
            style={{
              borderTop: '1px solid var(--color-border)',
              color: 'var(--color-text-tertiary)',
            }}
          >
            adaptive mode · n=72 per condition
          </div>
        </div>
      </div>
    </section>
  )
}
