import assert from "node:assert/strict";
import test from "node:test";

import { normalizeSpawnCommand } from "./devProcess.mjs";

test("wraps Windows cmd shims with cmd.exe", () => {
  assert.deepEqual(
    normalizeSpawnCommand("npm.cmd", ["run", "dev"], { platform: "win32" }),
    {
      command: "cmd.exe",
      args: ["/d", "/s", "/c", "npm.cmd", "run", "dev"],
    },
  );
});

test("keeps non-Windows commands unchanged", () => {
  assert.deepEqual(
    normalizeSpawnCommand("npm", ["run", "dev"], { platform: "linux" }),
    {
      command: "npm",
      args: ["run", "dev"],
    },
  );
});
