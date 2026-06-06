import type { AegisData } from '@/types/aegis'

function pct(x: number) {
  return `${(x * 100).toFixed(1)}%`
}

export function CrossModel({ cross }: { cross: NonNullable<AegisData['cross_model']> }) {
  const targets = cross.targets
  if (targets.length < 2) return null
  return (
    <section className="mt-16">
      <div className="text-[11px] tracking-widest mb-4" style={{ color: 'var(--color-text-tertiary)' }}>
        CROSS-MODEL COMPARISON
      </div>
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: '1px solid var(--color-border)', background: 'var(--color-surface)' }}
      >
        <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              <th className="text-left p-3 font-normal" style={{ color: 'var(--color-text-tertiary)' }}>
                Metric (adaptive attacker)
              </th>
              {targets.map(t => (
                <th key={t} className="text-right p-3 font-mono text-[13px]"
                    style={{ color: 'var(--color-text-secondary)' }}>
                  {t}
                </th>
              ))}
              <th className="text-right p-3 font-normal" style={{ color: 'var(--color-text-tertiary)' }}>
                p (2-prop)
              </th>
            </tr>
          </thead>
          <tbody>
            {cross.rows.map(row => {
              const vals = targets.map(t => row.by_target[t].asr)
              const minV = Math.min(...vals)
              const sig = row.significant_at_05
              return (
                <tr key={row.label} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td className="p-3" style={{ color: 'var(--color-text-secondary)' }}>{row.label}</td>
                  {targets.map(t => {
                    const v = row.by_target[t].asr
                    const isLow = v === minV
                    return (
                      <td key={t} className="text-right p-3 font-mono tabular-nums"
                          style={{ color: isLow ? 'var(--color-hold)' : 'var(--color-attack)' }}>
                        {pct(v)}
                        <span className="ml-1 text-[10px]" style={{ color: 'var(--color-text-tertiary)' }}>
                          n={row.by_target[t].n}
                        </span>
                      </td>
                    )
                  })}
                  <td className="text-right p-3 font-mono text-[12px]"
                      style={{ color: sig ? 'var(--color-attack)' : 'var(--color-text-tertiary)' }}>
                    {row.p_value !== undefined ? row.p_value : '—'}{sig ? ' *' : ''}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[11px]" style={{ color: 'var(--color-text-tertiary)' }}>
        Lower ASR = more robust (green). <span style={{ color: 'var(--color-attack)' }}>*</span> significant
        at 0.05 (two-proportion z-test). Scores are for the adaptive attacker; the primary-target
        charts above detail {targets[0]}.
      </p>
    </section>
  )
}
