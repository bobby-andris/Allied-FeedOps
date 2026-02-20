import type { NextConfig } from "next";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(configDir, "..");

function resolvePrimaryCheckoutRoot(root: string): string | null {
  const gitRefPath = path.join(root, ".git");
  if (!fs.existsSync(gitRefPath) || !fs.statSync(gitRefPath).isFile()) {
    return null;
  }
  try {
    const content = fs.readFileSync(gitRefPath, "utf8").trim();
    if (!content.startsWith("gitdir:")) return null;
    const gitdir = content.slice("gitdir:".length).trim();
    const resolvedGitdir = path.resolve(root, gitdir);
    const parts = resolvedGitdir.split(path.sep);
    const worktreesIndex = parts.lastIndexOf("worktrees");
    if (worktreesIndex > 0) {
      return parts.slice(0, worktreesIndex - 1).join(path.sep) || null;
    }
  } catch {
    return null;
  }
  return null;
}

function loadEnvFile(filePath: string, override = false): void {
  if (!fs.existsSync(filePath)) return;

  const lines = fs.readFileSync(filePath, "utf8").split(/\r?\n/);
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const withoutExport = line.startsWith("export ") ? line.slice(7).trim() : line;
    const separatorIndex = withoutExport.indexOf("=");
    if (separatorIndex <= 0) continue;

    const key = withoutExport.slice(0, separatorIndex).trim();
    if (!key) continue;

    if (!override && process.env[key] !== undefined) continue;

    const rawValue = withoutExport.slice(separatorIndex + 1).trim();
    const unquoted = rawValue.replace(/^['"]|['"]$/g, "");
    process.env[key] = unquoted.replace(/\\n/g, "\n");
  }
}

function loadEnvRoots(roots: string[]): void {
  for (const root of roots) {
    loadEnvFile(path.resolve(root, ".env"), false);
    loadEnvFile(path.resolve(root, ".env.local"), true);
    loadEnvFile(path.resolve(root, ".env.vercel"), true);
  }
}

const envRoots = [repoRoot];
const primaryRoot = resolvePrimaryCheckoutRoot(repoRoot);
if (primaryRoot && !envRoots.includes(primaryRoot)) {
  envRoots.push(primaryRoot);
}

// Align local dashboard env loading with production-style Vercel variables.
loadEnvRoots(envRoots);

const nextConfig: NextConfig = {
  // Prevent workspace-root inference warnings in a multi-folder repo.
  outputFileTracingRoot: repoRoot,
  turbopack: {
    // Keep workspace root stable regardless of invocation cwd.
    root: repoRoot,
  },
};

export default nextConfig;
