#!/usr/bin/env node

import { execSync } from 'node:child_process'

const baseRefCandidates = [
  process.env.TRACKING_GUARD_BASE,
  'origin/master',
  'origin/main',
  'master',
  'main',
].filter(Boolean)

function getChangedFiles() {
  for (const baseRef of baseRefCandidates) {
    try {
      const output = execSync(`git diff --name-only ${baseRef}...HEAD`, {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
      })
      return output.split('\n').map((line) => line.trim()).filter(Boolean)
    } catch {
      // try next candidate
    }
  }

  try {
    const output = execSync('git diff --name-only HEAD~1...HEAD', {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    })
    return output.split('\n').map((line) => line.trim()).filter(Boolean)
  } catch {
    return []
  }
}

const changedFiles = getChangedFiles()

const protectedPathPatterns = [
  /^dashboard\/src\/lib\/publishing\//,
  /^dashboard\/src\/lib\/tracking\//,
  /^dashboard\/src\/app\/api\/tracking\//,
  /^src\/.*analyzify/i,
  /^dashboard\/.*analyzify/i,
  /^.*gtm.*$/i,
]

const violations = changedFiles.filter((file) =>
  protectedPathPatterns.some((pattern) => pattern.test(file))
)

if (violations.length > 0) {
  console.error('Tracking regression guard failed. Protected paths were modified:')
  for (const file of violations) {
    console.error(` - ${file}`)
  }
  process.exit(1)
}

console.log('Tracking regression guard passed: no protected tracking paths changed.')
