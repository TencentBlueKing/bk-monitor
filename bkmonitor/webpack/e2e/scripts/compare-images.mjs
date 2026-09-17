#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';

function help() {
  console.log(`Usage:
  node e2e/scripts/compare-images.mjs --expected <png> --actual <png> --output <dir> [--threshold <0..1>]

Writes diff.png, overlay.png and metrics.json. The command exits with code 2 when image dimensions differ.`);
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--') {
      continue;
    }
    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }
    if (!token.startsWith('--')) {
      throw new Error(`Unexpected argument: ${token}`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) {
      throw new Error(`Missing value for ${token}`);
    }
    args[token.slice(2)] = value;
    index += 1;
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  help();
  process.exit(0);
}
for (const name of ['expected', 'actual', 'output']) {
  if (!args[name]) {
    throw new Error(`--${name} is required.`);
  }
}

const threshold = args.threshold === undefined ? 0.2 : Number(args.threshold);
if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) {
  throw new Error('--threshold must be a number between 0 and 1.');
}

const expectedPath = path.resolve(args.expected);
const actualPath = path.resolve(args.actual);
const outputDir = path.resolve(args.output);
fs.mkdirSync(outputDir, { recursive: true });

const expected = PNG.sync.read(fs.readFileSync(expectedPath));
const actual = PNG.sync.read(fs.readFileSync(actualPath));
const metricsPath = path.join(outputDir, 'metrics.json');

if (expected.width !== actual.width || expected.height !== actual.height) {
  const metrics = {
    status: 'dimension-mismatch',
    expected: { width: expected.width, height: expected.height },
    actual: { width: actual.width, height: actual.height },
    threshold,
    diffPixels: null,
    diffRatio: null,
    similarity: null,
  };
  fs.writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(metrics, null, 2));
  process.exit(2);
}

const diff = new PNG({ width: expected.width, height: expected.height });
const overlay = new PNG({ width: expected.width, height: expected.height });
const diffPixels = pixelmatch(expected.data, actual.data, diff.data, expected.width, expected.height, {
  threshold,
  includeAA: false,
  alpha: 0.5,
});

for (let index = 0; index < overlay.data.length; index += 4) {
  overlay.data[index] = Math.round((expected.data[index] + actual.data[index]) / 2);
  overlay.data[index + 1] = Math.round((expected.data[index + 1] + actual.data[index + 1]) / 2);
  overlay.data[index + 2] = Math.round((expected.data[index + 2] + actual.data[index + 2]) / 2);
  overlay.data[index + 3] = 255;
}

const totalPixels = expected.width * expected.height;
const diffRatio = totalPixels === 0 ? 0 : diffPixels / totalPixels;
const metrics = {
  status: 'compared',
  expected: { width: expected.width, height: expected.height },
  actual: { width: actual.width, height: actual.height },
  threshold,
  diffPixels,
  totalPixels,
  diffRatio,
  similarity: 1 - diffRatio,
};

fs.writeFileSync(path.join(outputDir, 'diff.png'), PNG.sync.write(diff));
fs.writeFileSync(path.join(outputDir, 'overlay.png'), PNG.sync.write(overlay));
fs.writeFileSync(metricsPath, `${JSON.stringify(metrics, null, 2)}\n`, 'utf8');
console.log(JSON.stringify(metrics, null, 2));
