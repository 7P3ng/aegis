import type { NextConfig } from 'next'

// Empty for local builds / `npx serve out`; set to "/aegis" by the Pages workflow so the
// project site (7p3ng.github.io/aegis/) resolves assets and /data.json correctly.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || ''

const nextConfig: NextConfig = {
  output: 'export',
  trailingSlash: true,
  ...(basePath ? { basePath, assetPrefix: basePath } : {}),
}

export default nextConfig
