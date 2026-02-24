#!/usr/bin/env node

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const packageJsonPath = new URL("../package.json", import.meta.url);
const { version, name } = JSON.parse(readFileSync(fileURLToPath(packageJsonPath), "utf-8"));

const args = new Set(process.argv.slice(2));

if (args.has("--version") || args.has("-v")) {
  console.log(`${name} ${version}`);
  process.exit(0);
}

if (args.has("--help") || args.has("-h") || args.size === 0) {
  console.log(`Usage: node src/main.js [options]\n\nOptions:\n  -h, --help     Show this help message\n  -v, --version  Print CLI version`);
  process.exit(0);
}

console.error(`Unknown option(s): ${Array.from(args).join(", ")}`);
process.exit(1);
