import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { normalizeSpawnCommand, resolveDevPorts } from "./devProcess.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const npmCommand = isWindows ? "npm.cmd" : "npm";
const pythonCommand = isWindows ? "python" : "python3";
const sharedEnv = {
  ...process.env,
  PYTHONPATH: path.join(root, "backend"),
  npm_config_cache: path.join(root, ".npm-cache"),
  FORCE_COLOR: "1",
};
const { backendPort, frontendPort } = resolveDevPorts(sharedEnv);
sharedEnv.BACKEND_PORT = backendPort;
sharedEnv.FRONTEND_PORT = frontendPort;

const children = [
  run("backend", pythonCommand, [
    "-m",
    "uvicorn",
    "app.main:app",
    "--app-dir",
    "backend",
    "--reload",
    "--host",
    "127.0.0.1",
    "--port",
    backendPort,
  ]),
  run("frontend", npmCommand, ["run", "dev", "--prefix", "frontend"]),
];

console.log("ETF monitor is starting in one terminal.");
console.log(`Frontend: http://127.0.0.1:${frontendPort}`);
console.log(`Backend:  http://127.0.0.1:${backendPort}/docs`);
console.log("Press Ctrl+C to stop both services.");

let shuttingDown = false;

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

for (const child of children) {
  child.on("exit", (code) => {
    if (!shuttingDown && code !== 0) {
      console.error(`Process exited: ${child.name} (${code ?? "unknown"})`);
      shutdown(code ?? 1);
    }
  });
}

function run(name, command, args) {
  const normalized = normalizeSpawnCommand(command, args);
  const child = spawn(normalized.command, normalized.args, {
    cwd: root,
    env: sharedEnv,
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.name = name;
  child.stdout.on("data", (chunk) => writePrefixed(name, chunk));
  child.stderr.on("data", (chunk) => writePrefixed(name, chunk));
  return child;
}

function writePrefixed(name, chunk) {
  const lines = chunk.toString().replace(/\r/g, "").split("\n");
  for (const line of lines) {
    if (line.trim().length > 0) {
      console.log(`[${name}] ${line}`);
    }
  }
}

function shutdown(exitCode) {
  if (shuttingDown) return;
  shuttingDown = true;
  Promise.all(children.map((child) => killProcessTree(child))).finally(() => {
    process.exit(exitCode);
  });
}

function killProcessTree(child) {
  if (!child.pid || child.killed) return Promise.resolve();
  if (!isWindows) {
    child.kill("SIGTERM");
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const killer = spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], {
      stdio: "ignore",
    });
    killer.on("exit", resolve);
    killer.on("error", resolve);
  });
}
