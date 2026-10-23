// Loopback ports for the rendered browser suite. Override the base only to run
// isolated copies side by side, for example from separate git worktrees.
const rawBase = process.env.SSRA_BROWSER_TEST_PORT_BASE ?? "3100";
const portBase = Number.parseInt(rawBase, 10);
if (!/^\d+$/.test(rawBase) || portBase < 1024 || portBase > 65_000) {
  throw new Error("SSRA_BROWSER_TEST_PORT_BASE must be an integer from 1024 to 65000");
}

export const browserTestPorts = {
  api: portBase + 3,
  console: portBase + 2,
  publicWeb: portBase,
  runtime: portBase + 1,
} as const;
