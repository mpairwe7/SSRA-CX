#!/usr/bin/env node

import { readFileSync } from "node:fs";

const packageUrl = new URL("../package.json", import.meta.url);
const rootPackage = JSON.parse(readFileSync(packageUrl, "utf8"));
const engineRange = rootPackage.engines?.node;
const boundedRangeMatch =
  typeof engineRange === "string" ? /^>=(\d+)\.0\.0 <(\d+)\.0\.0$/.exec(engineRange) : null;

if (!boundedRangeMatch) {
  console.error(
    "package.json engines.node must use a bounded Node-major range such as '>=24.0.0 <25.0.0'.",
  );
  process.exit(1);
}

const currentMajor = Number.parseInt(process.versions.node.split(".")[0], 10);
const minimumMajor = Number.parseInt(boundedRangeMatch[1], 10);
const exclusiveMaximumMajor = Number.parseInt(boundedRangeMatch[2], 10);

if (currentMajor < minimumMajor || currentMajor >= exclusiveMaximumMajor) {
  console.error(
    `Node.js ${process.versions.node} does not satisfy package.json engines.node (${engineRange}).`,
  );
  process.exit(1);
}

console.log(`Node.js ${process.versions.node} satisfies package.json engines.node (${engineRange}).`);
