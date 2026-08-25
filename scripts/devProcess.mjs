export function normalizeSpawnCommand(command, args, options = {}) {
  const platform = options.platform ?? process.platform;
  if (platform !== "win32" || !/\.(?:cmd|bat)$/i.test(command)) {
    return { command, args };
  }

  return {
    command: "cmd.exe",
    args: ["/d", "/s", "/c", command, ...args],
  };
}

export function resolveDevPorts(env = process.env) {
  return {
    backendPort: env.BACKEND_PORT || "8000",
    frontendPort: env.FRONTEND_PORT || "5174",
  };
}
