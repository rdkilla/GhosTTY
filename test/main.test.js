import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";

test("--version prints package version", () => {
  const result = spawnSync("node", ["src/main.js", "--version"], { encoding: "utf-8" });

  assert.equal(result.status, 0);
  assert.match(result.stdout, /^ghostty 0\.1\.0\n$/);
});
