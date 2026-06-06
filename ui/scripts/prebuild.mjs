import { copyFileSync, mkdirSync, existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')

const src = resolve(root, '../evals/results/export.json')
const destDir = resolve(root, 'public')
const dest = resolve(destDir, 'data.json')

mkdirSync(destDir, { recursive: true })

if (existsSync(src)) {
  copyFileSync(src, dest)
  console.log('✓ Copied export.json → public/data.json')
} else {
  console.warn('⚠ evals/results/export.json not found — using existing public/data.json if present')
  if (!existsSync(dest)) {
    throw new Error('No data.json found. Cannot build.')
  }
}
