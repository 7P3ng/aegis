'use client'

import { useEffect, useState } from 'react'
import type { AegisData } from '@/types/aegis'
import { AsrHero } from '@/components/AsrHero'
import { TechniqueHeatmap } from '@/components/TechniqueHeatmap'
import { DefenseAblation } from '@/components/DefenseAblation'
import { AttackLog } from '@/components/AttackLog'

export default function HomePage() {
  const [data, setData] = useState<AegisData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_BASE_PATH ?? ''}/data.json`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((d: AegisData) => setData(d))
      .catch(e => setError(String(e)))
  }, [])

  return (
    <div style={{ background: 'var(--color-bg)', minHeight: '100vh' }}>
      {/* Header */}
      <header
        className="sticky top-0 z-20"
        style={{
          background: 'rgba(10,10,11,0.90)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="max-w-screen-xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Shield logo mark */}
            <div
              className="w-6 h-6 rounded"
              style={{
                background: 'var(--color-accent-dim)',
                border: '1px solid var(--color-accent-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path
                  d="M6 1L10 3V6.5C10 8.5 8.5 10.2 6 11C3.5 10.2 2 8.5 2 6.5V3L6 1Z"
                  stroke="var(--color-accent)"
                  strokeWidth="1"
                  fill="none"
                />
                <path
                  d="M4.5 6L5.5 7L7.5 5"
                  stroke="var(--color-accent)"
                  strokeWidth="1"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <span
              className="font-semibold text-sm tracking-tight"
              style={{ color: 'var(--color-text-primary)' }}
            >
              Aegis
            </span>
            <span
              className="text-xs hidden sm:block"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              Automated Red-Team Gauntlet
            </span>
          </div>

          <div className="flex items-center gap-4">
            {data && (
              <div
                className="font-mono text-[11px] hidden md:block"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                {data.meta.n_trials} trials · {data.meta.n_scenarios} scenarios · {data.meta.n_techniques} techniques
              </div>
            )}
            {data && (
              <div
                className="px-2 py-0.5 rounded text-[10px] font-mono font-medium"
                style={{
                  background: data.meta.live ? 'var(--color-attack-bg)' : 'var(--color-surface-2)',
                  color: data.meta.live ? 'var(--color-attack)' : 'var(--color-text-tertiary)',
                  border: `1px solid ${data.meta.live ? 'var(--color-attack-border)' : 'var(--color-border)'}`,
                }}
              >
                {data.meta.live ? 'LIVE' : 'SAMPLE'}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Responsible disclaimer */}
      <div
        style={{
          background: 'var(--color-surface-1)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="max-w-screen-xl mx-auto px-6 py-2 flex items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink: 0 }}>
            <circle cx="6" cy="6" r="5" stroke="var(--color-text-tertiary)" strokeWidth="1" fill="none" />
            <path d="M6 5V8" stroke="var(--color-text-tertiary)" strokeWidth="1" strokeLinecap="round" />
            <circle cx="6" cy="3.5" r="0.5" fill="var(--color-text-tertiary)" />
          </svg>
          <span
            className="text-[11px]"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            Responsible red-teaming: harmless proxies only (canary string + injection sentinel); success scored by exact string match — no LLM judge.
          </span>
        </div>
      </div>

      {/* Loading / Error states */}
      {error && (
        <div className="max-w-screen-xl mx-auto px-6 py-12 text-center">
          <div
            className="inline-block px-4 py-3 rounded-lg text-sm font-mono"
            style={{
              background: 'var(--color-error-bg)',
              color: 'var(--color-error)',
              border: '1px solid rgba(248,113,113,0.25)',
            }}
          >
            Failed to load data.json: {error}
          </div>
        </div>
      )}

      {!data && !error && (
        <div className="max-w-screen-xl mx-auto px-6 py-12 text-center">
          <div
            className="text-sm"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            Loading…
          </div>
        </div>
      )}

      {data && (
        <main className="max-w-screen-xl mx-auto px-6 py-8 space-y-10">
          {/* Section 1: ASR Hero */}
          <AsrHero adaptationLift={data.adaptation_lift} defenseCurve={data.defense_curve} />

          {/* Section 2: Heatmap */}
          <TechniqueHeatmap
            adaptiveHeatmap={data.heatmap_adaptive_none}
            singleHeatmap={data.heatmap_single_none}
          />

          {/* Section 3: Defense Ablation */}
          <DefenseAblation defenseCurve={data.defense_curve} />

          {/* Section 4: Attack Log */}
          <AttackLog trials={data.trials} />
        </main>
      )}

      {/* Footer */}
      <footer
        className="mt-16"
        style={{ borderTop: '1px solid var(--color-border)' }}
      >
        <div
          className="max-w-screen-xl mx-auto px-6 py-6 flex items-center justify-between"
        >
          <span
            className="text-[11px] font-mono"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            Aegis — Automated Red-Team Gauntlet
          </span>
          <span
            className="text-[11px]"
            style={{ color: 'var(--color-text-tertiary)' }}
          >
            Built on the{' '}
            <span style={{ color: 'var(--color-accent)' }}>Quorum</span>
            {' '}kernel · same studio
          </span>
        </div>
      </footer>
    </div>
  )
}
