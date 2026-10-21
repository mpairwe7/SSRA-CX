#!/usr/bin/env node

import { readFileSync } from "node:fs";

const packageUrl = new URL("../package.json", import.meta.url);
const rootPackage = JSON.parse(readFileSync(packageUrl, "utf8"));
const engineRange = rootPackage.engines?.node;
const minimumMatch = typeof engineRange === "string" ? /^>=(\d+)\.0\.0$/.exec(engineRange) : null;

if (!minimumMatch) {
  console.error("package.json engines.node must use an explicit >=<major>.0.0 range.");
  process.exit(1);
}

const currentMajor = Number.parseInt(process.versions.node.split(".")[0], 10);
const requiredMajor = Number.parseInt(minimumMatch[1], 10);

if (currentMajor < requiredMajor) {
  console.error(
    `Node.js ${process.versions.node} does not satisfy package.json engines.node (${engineRange}).`,
  );
  process.exit(1);
}

console.log(`Node.js ${process.versions.node} satisfies package.json engines.node (${engineRange}).`);
