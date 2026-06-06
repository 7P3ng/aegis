'use client'

import { useState, useRef } from 'react'
import type { HeatmapCell } from '@/types/aegis'

interface Props {
  adaptiveHeatmap: HeatmapCell[]
  singleHeatmap: HeatmapCell[]
}

const SCENARIO_LABELS: Record<string, string> = {
  canary_vault_key: 'Vault Key',
  canary_research_embargo: 'Research Embargo',
  canary_support_pii: 'Support PII',
  inject_email_assistant: 'Email Inject',
  inject_translate: 'Translate Inject',
  inject_doc_summary: 'Doc Summary Inject',
}

const TECHNIQUE_LABELS: Record<string, string> = {
  direct_ask: 'Direct Ask',
  roleplay: 'Roleplay',
  fiction: 'Fiction Frame',
  encoding_base64: 'Base64 Encoding',
  leetspeak: 'Leetspeak',
  translation: 'Translation',
  many_shot: 'Many-Shot',
  context_overflow: 'Context Overflow',
  payload_splitting: 'Payload Splitting',
  instruction_override: 'Instruction Override',
  authority_urgency: 'Authority / Urgency',
  refusal_suppression: 'Refusal Suppression',
}

interface TooltipState {
  cell: HeatmapCell
  x: number
  y: number
}

export function TechniqueHeatmap({ adaptiveHeatmap, singleHeatmap }: Props) {
  const [mode, setMode] = useState<'adaptive' | 'single'>('adaptive')
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const cells = mode === 'adaptive' ? adaptiveHeatmap : singleHeatmap

  // Build lookup map
  const cellMap = new Map<string, HeatmapCell>()
  for (const c of cells) {
    cellMap.set(`${c.technique}|${c.scenario}`, c)
  }

  // Get unique sorted axes
  const techniques = Object.keys(TECHNIQUE_LABELS)
  const scenarios = Object.keys(SCENARIO_LABELS)

  // Count attack vs hold per column (technique)
  const techniqueStats = techniques.map(t => {
    const tcells = scenarios.map(s => cellMap.get(`${t}|${s}`)).filter(Boolean) as HeatmapCell[]
    const successes = tcells.filter(c => c.success).length
    return { technique: t, successes, total: tcells.length }
  })

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <h2
          className="text-[11px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          Technique × Scenario Heatmap
        </h2>
        <div
          className="flex-1 h-px"
          style={{ background: 'var(--color-border)' }}
        />
        {/* Mode toggle */}
        <div
          className="flex items-center gap-0.5 p-0.5 rounded-md"
          style={{
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border)',
          }}
        >
          {(['adaptive', 'single'] as const).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="px-2.5 py-1 rounded text-[11px] font-medium transition-all duration-150"
              style={{
                background: mode === m ? 'var(--color-surface-3)' : 'transparent',
                color: mode === m ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                border: mode === m ? '1px solid var(--color-border-strong)' : '1px solid transparent',
              }}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'var(--color-surface-1)',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="p-5 overflow-x-auto" ref={containerRef}>
          <table style={{ borderCollapse: 'separate', borderSpacing: '3px', minWidth: '560px' }}>
            <thead>
              <tr>
                {/* empty corner */}
                <th style={{ width: '140px' }} />
                {scenarios.map(s => (
                  <th
                    key={s}
                    className="text-[10px] font-medium pb-2 px-1"
                    style={{
                      color: 'var(--color-text-tertiary)',
                      textAlign: 'center',
                      whiteSpace: 'nowrap',
                      writingMode: 'vertical-rl',
                      transform: 'rotate(180deg)',
                      height: '80px',
                      verticalAlign: 'bottom',
                      maxWidth: '24px',
                    }}
                  >
                    {SCENARIO_LABELS[s] ?? s}
                  </th>
                ))}
                <th
                  className="text-[10px] font-medium pb-2 pl-3"
                  style={{ color: 'var(--color-text-tertiary)', textAlign: 'right', whiteSpace: 'nowrap' }}
                >
                  ASR
                </th>
              </tr>
            </thead>
            <tbody>
              {techniques.map((tech, ti) => {
                const stat = techniqueStats[ti]
                const asr = stat.total > 0 ? stat.successes / stat.total : 0
                return (
                  <tr key={tech}>
                    <td
                      className="pr-3 py-0.5 text-[11px] font-mono"
                      style={{
                        color: 'var(--color-text-secondary)',
                        whiteSpace: 'nowrap',
                        textAlign: 'right',
                      }}
                    >
                      {TECHNIQUE_LABELS[tech] ?? tech}
                    </td>
                    {scenarios.map(scen => {
                      const cell = cellMap.get(`${tech}|${scen}`)
                      if (!cell) {
                        return (
                          <td
                            key={scen}
                            style={{
                              width: '24px',
                              height: '24px',
                              background: 'var(--color-surface-2)',
                              borderRadius: '3px',
                            }}
                          />
                        )
                      }
                      return (
                        <td
                          key={scen}
                          style={{
                            width: '24px',
                            height: '24px',
                            background: cell.success
                              ? 'rgba(248,113,113,0.70)'
                              : 'rgba(74,222,128,0.20)',
                            borderRadius: '3px',
                            cursor: 'pointer',
                            border: cell.success
                              ? '1px solid rgba(248,113,113,0.40)'
                              : '1px solid rgba(74,222,128,0.15)',
                            transition: 'opacity 0.15s',
                          }}
                          title={`${TECHNIQUE_LABELS[tech] ?? tech} × ${SCENARIO_LABELS[scen] ?? scen}\n${cell.success ? '✗ Attack landed' : '✓ Target held'}\nTurns: ${cell.turns_used}${cell.blocked_by ? `\nBlocked by: ${cell.blocked_by}` : ''}`}
                          onMouseEnter={e => {
                            const rect = (e.target as HTMLElement).getBoundingClientRect()
                            const containerRect = containerRef.current?.getBoundingClientRect()
                            setTooltip({
                              cell,
                              x: rect.left - (containerRect?.left ?? 0) + rect.width / 2,
                              y: rect.top - (containerRect?.top ?? 0),
                            })
                          }}
                          onMouseLeave={() => setTooltip(null)}
                        />
                      )
                    })}
                    {/* ASR mini-bar */}
                    <td className="pl-3 py-0.5">
                      <div className="flex items-center gap-1.5">
                        <div
                          style={{
                            width: '48px',
                            height: '4px',
                            background: 'var(--color-surface-3)',
                            borderRadius: '2px',
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            style={{
                              width: `${asr * 100}%`,
                              height: '100%',
                              background: asr > 0.5
                                ? 'var(--color-attack)'
                                : asr > 0.2
                                ? 'var(--color-warn)'
                                : 'var(--color-hold)',
                              borderRadius: '2px',
                            }}
                          />
                        </div>
                        <span
                          className="text-[10px] font-mono"
                          style={{ color: 'var(--color-text-tertiary)' }}
                        >
                          {(asr * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {/* Tooltip */}
          {tooltip && (
            <div
              style={{
                position: 'absolute',
                left: tooltip.x,
                top: tooltip.y - 8,
                transform: 'translate(-50%, -100%)',
                background: 'var(--color-surface-3)',
                border: '1px solid var(--color-border-strong)',
                borderRadius: '6px',
                padding: '8px 10px',
                fontSize: '11px',
                fontFamily: 'var(--font-geist-mono, monospace)',
                color: 'var(--color-text-primary)',
                pointerEvents: 'none',
                zIndex: 30,
                whiteSpace: 'nowrap',
                boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
              }}
            >
              <div className="font-semibold mb-1">{TECHNIQUE_LABELS[tooltip.cell.technique] ?? tooltip.cell.technique}</div>
              <div style={{ color: 'var(--color-text-secondary)' }}>{SCENARIO_LABELS[tooltip.cell.scenario] ?? tooltip.cell.scenario}</div>
              <div
                className="mt-1.5"
                style={{ color: tooltip.cell.success ? 'var(--color-attack)' : 'var(--color-hold)' }}
              >
                {tooltip.cell.success ? '✗ Attack landed' : '✓ Target held'}
              </div>
              <div style={{ color: 'var(--color-text-tertiary)' }}>
                Turns: {tooltip.cell.turns_used}
                {tooltip.cell.blocked_by && ` · Blocked by: ${tooltip.cell.blocked_by}`}
              </div>
            </div>
          )}
        </div>

        {/* Legend */}
        <div
          className="px-5 py-3 flex items-center gap-5"
          style={{ borderTop: '1px solid var(--color-border)' }}
        >
          <span
            className="text-[10px] uppercase tracking-wider"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            Legend
          </span>
          <div className="flex items-center gap-1.5">
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '2px',
                background: 'rgba(248,113,113,0.70)',
                border: '1px solid rgba(248,113,113,0.40)',
              }}
            />
            <span className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>Attack landed</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '2px',
                background: 'rgba(74,222,128,0.20)',
                border: '1px solid rgba(74,222,128,0.15)',
              }}
            />
            <span className="text-[10px]" style={{ color: 'var(--color-text-secondary)' }}>Target held</span>
          </div>
          <span
            className="text-[10px] ml-auto"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            Hover cells for details · Toggle adaptive / single above
          </span>
        </div>
      </div>
    </section>
  )
}
