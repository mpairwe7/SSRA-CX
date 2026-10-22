import { defineConfig, devices } from "@playwright/test";

const publicBaseUrl = "http://127.0.0.1:3100";
const consoleBaseUrl = "http://127.0.0.1:3102";

export default defineConfig({
  testDir: "./tests/browser",
  outputDir: "test-results/playwright-artifacts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never", outputFolder: "playwright-report" }]]
    : "list",
  timeout: 30_000,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: publicBaseUrl,
    colorScheme: "light",
    locale: "en-SS",
    reducedMotion: "reduce",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
    timezoneId: "Africa/Juba",
  },
  webServer: [
    {
      command: "node tests/browser/mock-runtime.mjs",
      url: "http://127.0.0.1:3101/healthz",
      reuseExistingServer: false,
    },
    {
      command: "node apps/web/server.js",
      url: `${publicBaseUrl}/healthz`,
      env: {
        HOSTNAME: "127.0.0.1",
        INTERNAL_API_URL: "http://127.0.0.1:3103",
        INTERNAL_RUNTIME_URL: "http://127.0.0.1:3101",
        PORT: "3100",
      },
      reuseExistingServer: false,
    },
    {
      command: "node apps/console/server.js",
      url: `${consoleBaseUrl}/healthz`,
      env: {
        HOSTNAME: "127.0.0.1",
        PORT: "3102",
      },
      reuseExistingServer: false,
    },
  ],
});
