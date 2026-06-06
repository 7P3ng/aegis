'use client'

import type { AegisData } from '@/types/aegis'

interface Props {
  defenseCurve: AegisData['defense_curve']
}

const CONDITION_LABELS: Record<string, string> = {
  none: 'No defense',
  prompt: 'Prompt hardening',
  'prompt+classifier': '+ Classifier',
  'prompt+classifier+scan': '+ Scan (full stack)',
}

const CONDITION_ORDER = ['none', 'prompt', 'prompt+classifier', 'prompt+classifier+scan']

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`
}

function ci(lo: number, hi: number) {
  return `[${(lo * 100).toFixed(1)}, ${(hi * 100).toFixed(1)}]`
}

function asrColor(asr: number) {
  if (asr > 0.5) return 'var(--color-attack)'
  if (asr > 0.25) return 'var(--color-warn)'
  return 'var(--color-hold)'
}

export function DefenseAblation({ defenseCurve }: Props) {
  const maxAsr = Math.max(
    ...CONDITION_ORDER.map(c => defenseCurve.by_condition[c]?.asr ?? 0)
  )

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <h2
          className="text-[11px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          Per-Layer Defense Ablation
        </h2>
        <div
          className="flex-1 h-px"
          style={{ background: 'var(--color-border)' }}
        />
        <div
          className="px-2 py-0.5 rounded text-[10px] font-mono"
          style={{
            background: 'var(--color-hold-bg)',
            color: 'var(--color-hold)',
            border: '1px solid var(--color-hold-border)',
          }}
        >
          −{pct(defenseCurve.reduction_abs)} total
        </div>
      </div>

      <div
        className="rounded-xl p-6"
        style={{
          background: 'var(--color-surface-1)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="space-y-5">
          {CONDITION_ORDER.map((cond, i) => {
            const val = defenseCurve.by_condition[cond]
            if (!val) return null
            const marginal = defenseCurve.per_layer_marginal[cond]
            const isFirst = i === 0
            const barWidth = maxAsr > 0 ? (val.asr / maxAsr) * 100 : 0

            return (
              <div key={cond}>
                {/* Row header */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-5 h-5 rounded flex items-center justify-center text-[9px] font-mono font-bold flex-shrink-0"
                      style={{
                        background: 'var(--color-surface-3)',
                        color: 'var(--color-text-tertiary)',
                        border: '1px solid var(--color-border)',
                      }}
                    >
                      {i + 1}
                    </div>
                    <span
                      className="text-sm font-medium"
                      style={{ color: 'var(--color-text-primary)' }}
                    >
                      {CONDITION_LABELS[cond] ?? cond}
                    </span>
                    {!isFirst && marginal !== undefined && marginal > 0 && (
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] font-mono"
                        style={{
                          background: 'var(--color-hold-bg)',
                          color: 'var(--color-hold)',
                          border: '1px solid var(--color-hold-border)',
                        }}
                      >
                        −{pct(marginal)} layer
                      </span>
                    )}
                    {!isFirst && marginal !== undefined && marginal === 0 && (
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] font-mono"
                        style={{
                          background: 'var(--color-surface-2)',
                          color: 'var(--color-text-tertiary)',
                          border: '1px solid var(--color-border)',
                        }}
                      >
                        no change
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span
                      className="text-[11px] font-mono"
                      style={{ color: 'var(--color-text-tertiary)' }}
                    >
                      95% CI {ci(val.ci[0], val.ci[1])}
                    </span>
                    <span
                      className="text-lg font-bold font-mono"
                      style={{ color: asrColor(val.asr), minWidth: '52px', textAlign: 'right' }}
                    >
                      {pct(val.asr)}
                    </span>
                  </div>
                </div>

                {/* Bar */}
                <div
                  className="h-7 rounded overflow-hidden relative"
                  style={{ background: 'var(--color-surface-2)' }}
                >
                  <div
                    className="h-full rounded"
                    style={{
                      width: `${barWidth}%`,
                      background: asrColor(val.asr),
                      opacity: 0.3,
                      transition: 'width 0.5s ease',
                    }}
                  />
                  {/* Solid inner bar */}
                  <div
                    className="absolute top-0 left-0 h-full rounded"
                    style={{
                      width: `${barWidth}%`,
                      background: 'transparent',
                      borderRight: `2px solid ${asrColor(val.asr)}`,
                    }}
                  />
                  {/* CI range indicator */}
                  <div
                    className="absolute top-0 h-full"
                    style={{
                      left: maxAsr > 0 ? `${(val.ci[0] / maxAsr) * 100}%` : '0%',
                      width: maxAsr > 0 ? `${((val.ci[1] - val.ci[0]) / maxAsr) * 100}%` : '0%',
                      background: `${asrColor(val.asr)}`,
                      opacity: 0.15,
                    }}
                  />
                  <div
                    className="absolute top-1.5 left-3 text-[10px] font-mono font-semibold"
                    style={{ color: asrColor(val.asr) }}
                  >
                    {CONDITION_LABELS[cond] ?? cond}
                  </div>
                </div>

                {/* Connector line to next */}
                {i < CONDITION_ORDER.length - 1 && (
                  <div className="flex items-center pl-2.5 mt-2 mb-0 gap-2">
                    <div
                      style={{
                        width: '1px',
                        height: '12px',
                        background: 'var(--color-border)',
                        marginLeft: '8px',
                      }}
                    />
                    {defenseCurve.per_layer_marginal[CONDITION_ORDER[i + 1]] !== undefined &&
                      defenseCurve.per_layer_marginal[CONDITION_ORDER[i + 1]] > 0 && (
                        <span
                          className="text-[10px] font-mono"
                          style={{ color: 'var(--color-text-tertiary)' }}
                        >
                          adds −{pct(defenseCurve.per_layer_marginal[CONDITION_ORDER[i + 1]])} defense
                        </span>
                      )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div
          className="mt-6 pt-4 flex items-center justify-between text-[11px]"
          style={{
            borderTop: '1px solid var(--color-border)',
            color: 'var(--color-text-tertiary)',
          }}
        >
          <span>adaptive mode · n=72 per condition · Wilson 95% CI</span>
          <span>Total reduction: −{pct(defenseCurve.reduction_abs)}</span>
        </div>
      </div>
    </section>
  )
}
