import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const configDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(configDir, "..");

const nextConfig: NextConfig = {
  // Prevent workspace-root inference warnings in a multi-folder repo.
  outputFileTracingRoot: repoRoot,
  turbopack: {
    // Keep workspace root stable regardless of invocation cwd.
    root: repoRoot,
  },
};

export default nextConfig;
