// Writes the release version into custom_components/<domain>/manifest.json.
// Home Assistant and HACS read the version from the manifest, so semantic-release calls this
// in its prepare step (see .releaserc.json) before the release commit and tag are created.
// Usage: node scripts/set-version.mjs 1.2.3
import { readdirSync, readFileSync, writeFileSync } from "node:fs";

const version = process.argv[2];
if (!/^\d+\.\d+\.\d+(?:-[\w.]+)?$/.test(version ?? "")) {
  console.error(`Expected a semver version, got "${version}"`);
  process.exit(1);
}

const domains = readdirSync("custom_components", { withFileTypes: true }).filter((entry) => entry.isDirectory());
if (domains.length !== 1) {
  console.error(`HACS manages exactly one integration per repository, found ${domains.length}`);
  process.exit(1);
}

const file = `custom_components/${domains[0].name}/manifest.json`;
const manifest = readFileSync(file, "utf8");
// A text replace keeps the file formatting (a JSON round-trip would reflow the arrays).
const updated = manifest.replace(/("version"\s*:\s*)"[^"]*"/, `$1"${version}"`);
if (updated === manifest && !manifest.includes(`"${version}"`)) {
  console.error(`No "version" key found in ${file}`);
  process.exit(1);
}
writeFileSync(file, updated);
console.log(`${file} → ${version}`);
