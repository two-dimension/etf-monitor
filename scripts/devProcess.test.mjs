import assert from "node:assert/strict";
import test from "node:test";

import { normalizeSpawnCommand, resolveDevPorts } from "./devProcess.mjs";

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

test("uses project dev ports that avoid common occupied service ports", () => {
  assert.deepEqual(resolveDevPorts(), {
    backendPort: "8000",
    frontendPort: "5174",
  });
});

test("allows dev ports to be overridden from the environment", () => {
  assert.deepEqual(
    resolveDevPorts({ BACKEND_PORT: "8010", FRONTEND_PORT: "5180" }),
    {
      backendPort: "8010",
      frontendPort: "5180",
    },
  );
});
