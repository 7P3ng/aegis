'use client'

import { useState, useMemo } from 'react'
import type { Trial } from '@/types/aegis'

interface Props {
  trials: Trial[]
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

function OutcomeBadge({ trial }: { trial: Trial }) {
  if (trial.success) {
    return (
      <span
        className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium"
        style={{
          background: 'var(--color-attack-bg)',
          color: 'var(--color-attack)',
          border: '1px solid var(--color-attack-border)',
        }}
      >
        attack landed
      </span>
    )
  }
  if (trial.blocked_by) {
    return (
      <span
        className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium"
        style={{
          background: 'var(--color-surface-2)',
          color: 'var(--color-text-secondary)',
          border: '1px solid var(--color-border)',
        }}
      >
        blocked by {trial.blocked_by}
      </span>
    )
  }
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-mono font-medium"
      style={{
        background: 'var(--color-hold-bg)',
        color: 'var(--color-hold)',
        border: '1px solid var(--color-hold-border)',
      }}
    >
      refused
    </span>
  )
}

function TranscriptView({ trial }: { trial: Trial }) {
  return (
    <div
      className="mt-2 rounded-lg overflow-hidden"
      style={{
        background: 'var(--color-surface-2)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div
        className="px-3 py-2 flex items-center justify-between"
        style={{ borderBottom: '1px solid var(--color-border)' }}
      >
        <span
          className="text-[10px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          Transcript · {trial.transcript.length} turn{trial.transcript.length !== 1 ? 's' : ''}
        </span>
        <span
          className="text-[10px] font-mono"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          {trial.mode} · {trial.condition}
        </span>
      </div>
      <div className="divide-y" style={{ borderColor: 'var(--color-border)' }}>
        {trial.transcript.map((turn, i) => (
          <div key={i} className="px-3 py-3 space-y-2">
            {/* Attacker */}
            <div className="flex gap-2">
              <div
                className="flex-shrink-0 text-[10px] font-mono font-semibold pt-0.5 w-16 text-right"
                style={{ color: 'var(--color-accent)' }}
              >
                attacker
              </div>
              <div
                className="text-[11px] font-mono flex-1 whitespace-pre-wrap break-words leading-relaxed"
                style={{
                  color: 'var(--color-text-primary)',
                  background: 'rgba(255,107,53,0.05)',
                  borderRadius: '4px',
                  padding: '6px 8px',
                  border: '1px solid rgba(255,107,53,0.10)',
                }}
              >
                {turn.attacker}
              </div>
            </div>
            {/* Target */}
            <div className="flex gap-2">
              <div
                className="flex-shrink-0 text-[10px] font-mono font-semibold pt-0.5 w-16 text-right"
                style={{ color: 'var(--color-text-tertiary)' }}
              >
                target
              </div>
              <div
                className="text-[11px] font-mono flex-1 whitespace-pre-wrap break-words leading-relaxed"
                style={{
                  color: turn.success ? 'var(--color-attack)' : 'var(--color-text-secondary)',
                  background: turn.success ? 'rgba(248,113,113,0.05)' : 'var(--color-surface-3)',
                  borderRadius: '4px',
                  padding: '6px 8px',
                  border: `1px solid ${turn.success ? 'rgba(248,113,113,0.15)' : 'var(--color-border)'}`,
                }}
              >
                {turn.target}
              </div>
            </div>
            {/* Turn outcome */}
            <div className="flex justify-end">
              {turn.success ? (
                <span className="text-[10px] font-mono" style={{ color: 'var(--color-attack)' }}>
                  ✗ leaked
                </span>
              ) : turn.blocked_by ? (
                <span className="text-[10px] font-mono" style={{ color: 'var(--color-text-tertiary)' }}>
                  blocked by {turn.blocked_by}
                </span>
              ) : (
                <span className="text-[10px] font-mono" style={{ color: 'var(--color-hold)' }}>
                  ✓ held
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const PAGE_SIZE = 50

export function AttackLog({ trials }: Props) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  const [filterOutcome, setFilterOutcome] = useState<'all' | 'success' | 'blocked' | 'refused'>('all')
  const [filterScenario, setFilterScenario] = useState<string>('all')
  const [filterMode, setFilterMode] = useState<string>('all')
  const [page, setPage] = useState(0)

  const scenarios = useMemo(() => ['all', ...Array.from(new Set(trials.map(t => t.scenario)))], [trials])
  const modes = useMemo(() => ['all', ...Array.from(new Set(trials.map(t => t.mode)))], [trials])

  const filtered = useMemo(() => {
    return trials.filter(t => {
      if (filterOutcome === 'success' && !t.success) return false
      if (filterOutcome === 'blocked' && (t.success || !t.blocked_by)) return false
      if (filterOutcome === 'refused' && (t.success || t.blocked_by)) return false
      if (filterScenario !== 'all' && t.scenario !== filterScenario) return false
      if (filterMode !== 'all' && t.mode !== filterMode) return false
      return true
    })
  }, [trials, filterOutcome, filterScenario, filterMode])

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE)
  const paginated = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  function handleFilterChange() {
    setPage(0)
    setExpandedIdx(null)
  }

  const attackCount = filtered.filter(t => t.success).length
  const blockedCount = filtered.filter(t => !t.success && t.blocked_by).length
  const refusedCount = filtered.filter(t => !t.success && !t.blocked_by).length

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <h2
          className="text-[11px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          Attack Log
        </h2>
        <div
          className="flex-1 h-px"
          style={{ background: 'var(--color-border)' }}
        />
        <span
          className="text-[11px] font-mono"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          {filtered.length} / {trials.length}
        </span>
      </div>

      {/* Filters */}
      <div
        className="rounded-xl p-4 mb-4 flex flex-wrap gap-3 items-center"
        style={{
          background: 'var(--color-surface-1)',
          border: '1px solid var(--color-border)',
        }}
      >
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: 'var(--color-text-tertiary)' }}
        >
          Filter
        </span>

        {/* Outcome filter */}
        <div
          className="flex items-center gap-0.5 p-0.5 rounded-md"
          style={{
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border)',
          }}
        >
          {(['all', 'success', 'blocked', 'refused'] as const).map(o => (
            <button
              key={o}
              onClick={() => { setFilterOutcome(o); handleFilterChange() }}
              className="px-2 py-1 rounded text-[11px] font-medium transition-all duration-100"
              style={{
                background: filterOutcome === o ? 'var(--color-surface-3)' : 'transparent',
                color: filterOutcome === o ? 'var(--color-text-primary)' : 'var(--color-text-tertiary)',
                border: filterOutcome === o ? '1px solid var(--color-border-strong)' : '1px solid transparent',
              }}
            >
              {o}
            </button>
          ))}
        </div>

        {/* Scenario filter */}
        <select
          value={filterScenario}
          onChange={e => { setFilterScenario(e.target.value); handleFilterChange() }}
          className="text-[11px] font-mono rounded-md px-2 py-1.5 outline-none"
          style={{
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {scenarios.map(s => (
            <option key={s} value={s}>
              {s === 'all' ? 'All scenarios' : (SCENARIO_LABELS[s] ?? s)}
            </option>
          ))}
        </select>

        {/* Mode filter */}
        <select
          value={filterMode}
          onChange={e => { setFilterMode(e.target.value); handleFilterChange() }}
          className="text-[11px] font-mono rounded-md px-2 py-1.5 outline-none"
          style={{
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
          }}
        >
          {modes.map(m => (
            <option key={m} value={m}>
              {m === 'all' ? 'All modes' : m}
            </option>
          ))}
        </select>

        {/* Stats */}
        <div className="ml-auto flex items-center gap-3 flex-wrap">
          <span className="text-[11px] font-mono" style={{ color: 'var(--color-attack)' }}>
            {attackCount} attacks
          </span>
          <span className="text-[11px] font-mono" style={{ color: 'var(--color-text-tertiary)' }}>
            {blockedCount} blocked
          </span>
          <span className="text-[11px] font-mono" style={{ color: 'var(--color-hold)' }}>
            {refusedCount} refused
          </span>
        </div>
      </div>

      {/* Table */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          background: 'var(--color-surface-1)',
          border: '1px solid var(--color-border)',
        }}
      >
        {/* Table header */}
        <div
          className="grid gap-2 px-4 py-2 text-[10px] font-semibold uppercase tracking-widest"
          style={{
            gridTemplateColumns: '1fr 1fr 80px 120px 140px 48px',
            borderBottom: '1px solid var(--color-border)',
            color: 'var(--color-text-tertiary)',
            background: 'var(--color-surface-2)',
          }}
        >
          <div>Scenario</div>
          <div>Technique</div>
          <div>Mode</div>
          <div>Condition</div>
          <div>Outcome</div>
          <div className="text-right">Turns</div>
        </div>

        {/* Rows */}
        <div>
          {paginated.length === 0 ? (
            <div
              className="px-4 py-8 text-center text-sm"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              No trials match current filters
            </div>
          ) : (
            paginated.map((trial, i) => {
              const globalIdx = page * PAGE_SIZE + i
              const isExpanded = expandedIdx === globalIdx
              return (
                <div
                  key={globalIdx}
                  style={{
                    borderBottom: '1px solid var(--color-border)',
                    background: isExpanded ? 'var(--color-surface-2)' : 'transparent',
                  }}
                >
                  <button
                    className="w-full text-left"
                    onClick={() => setExpandedIdx(isExpanded ? null : globalIdx)}
                  >
                    <div
                      className="grid gap-2 px-4 py-2.5 items-center text-[12px] transition-colors duration-100 hover:bg-white/[0.02]"
                      style={{ gridTemplateColumns: '1fr 1fr 80px 120px 140px 48px' }}
                    >
                      <div
                        className="font-medium truncate"
                        style={{ color: 'var(--color-text-primary)' }}
                      >
                        {SCENARIO_LABELS[trial.scenario] ?? trial.scenario}
                      </div>
                      <div
                        className="font-mono text-[11px] truncate"
                        style={{ color: 'var(--color-text-secondary)' }}
                      >
                        {TECHNIQUE_LABELS[trial.technique] ?? trial.technique}
                      </div>
                      <div
                        className="font-mono text-[11px]"
                        style={{ color: 'var(--color-text-tertiary)' }}
                      >
                        {trial.mode}
                      </div>
                      <div
                        className="font-mono text-[11px] truncate"
                        style={{ color: 'var(--color-text-tertiary)' }}
                      >
                        {trial.condition === 'prompt+classifier+scan'
                          ? 'full stack'
                          : trial.condition}
                      </div>
                      <div>
                        <OutcomeBadge trial={trial} />
                      </div>
                      <div className="flex items-center justify-end gap-1.5">
                        <span
                          className="font-mono text-[11px]"
                          style={{ color: 'var(--color-text-tertiary)' }}
                        >
                          {trial.turns_used}
                        </span>
                        <svg
                          width="10"
                          height="10"
                          viewBox="0 0 10 10"
                          fill="none"
                          style={{
                            color: 'var(--color-text-tertiary)',
                            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.15s',
                          }}
                        >
                          <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      </div>
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="px-4 pb-4">
                      <TranscriptView trial={trial} />
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>

        {/* Pagination */}
        {pageCount > 1 && (
          <div
            className="px-4 py-3 flex items-center justify-between"
            style={{ borderTop: '1px solid var(--color-border)', background: 'var(--color-surface-2)' }}
          >
            <button
              disabled={page === 0}
              onClick={() => { setPage(p => p - 1); setExpandedIdx(null) }}
              className="px-3 py-1.5 rounded text-[11px] font-medium transition-all"
              style={{
                background: page === 0 ? 'transparent' : 'var(--color-surface-3)',
                color: page === 0 ? 'var(--color-text-tertiary)' : 'var(--color-text-secondary)',
                border: `1px solid ${page === 0 ? 'transparent' : 'var(--color-border)'}`,
                cursor: page === 0 ? 'default' : 'pointer',
              }}
            >
              ← Previous
            </button>
            <span
              className="text-[11px] font-mono"
              style={{ color: 'var(--color-text-tertiary)' }}
            >
              Page {page + 1} of {pageCount} · {filtered.length} trials
            </span>
            <button
              disabled={page >= pageCount - 1}
              onClick={() => { setPage(p => p + 1); setExpandedIdx(null) }}
              className="px-3 py-1.5 rounded text-[11px] font-medium transition-all"
              style={{
                background: page >= pageCount - 1 ? 'transparent' : 'var(--color-surface-3)',
                color: page >= pageCount - 1 ? 'var(--color-text-tertiary)' : 'var(--color-text-secondary)',
                border: `1px solid ${page >= pageCount - 1 ? 'transparent' : 'var(--color-border)'}`,
                cursor: page >= pageCount - 1 ? 'default' : 'pointer',
              }}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </section>
  )
}
