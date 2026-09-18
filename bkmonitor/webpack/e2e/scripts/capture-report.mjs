#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium } from '@playwright/test';

export async function captureReport(runDirectory) {
  const runDir = fs.realpathSync(runDirectory);
  const reportPath = path.join(runDir, 'report/index.html');
  const factsPath = path.join(runDir, 'report/delivery-facts.json');
  const facts = JSON.parse(fs.readFileSync(factsPath, 'utf8'));
  const reportHash = createHash('sha256').update(fs.readFileSync(reportPath)).digest('hex');
  const isInsideRun = file => {
    const relative = path.relative(runDir, fs.realpathSync(file));
    return relative !== '..' && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
  };
  if (!isInsideRun(reportPath) || !isInsideRun(factsPath)) {
    throw new Error('Report and facts must be inside the run directory.');
  }
  const browser = await chromium.launch({ headless: true });
  const artifacts = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1800 }, deviceScaleFactor: 1 });
    // Reports are local artifacts; opening one must not contact the target environment.
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.protocol === 'file:') {
        try {
          if (isInsideRun(fileURLToPath(url))) return route.continue();
        } catch {}
      }
      return route.abort();
    });
    await page.goto(pathToFileURL(reportPath).href, { waitUntil: 'load' });
    await page.evaluate(async () => {
      document.querySelectorAll('details').forEach(item => { item.open = true; });
      await document.fonts.ready;
      await Promise.all([...document.images].map(image => image.decode()));
    });
    await page.addStyleTag({ content: '.error-box pre { max-height: none; overflow: visible; }' });
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const fullPath = 'report/report-full.png';
    await page.screenshot({ path: path.join(runDir, fullPath), fullPage: true, animations: 'disabled' });
    const addArtifact = (runPath, label) => artifacts.push({
      role: 'report', mediaType: 'image', label, runPath, reportHash,
    });
    if (height <= 1800) {
      addArtifact(fullPath, '完整测试报告');
    } else {
      // Overlap preserves context when a table or paragraph spans two images.
      for (let y = 0, index = 1; y < height; y += 1720, index += 1) {
        const runPath = `report/report-page-${String(index).padStart(2, '0')}.png`;
        await page.screenshot({
          path: path.join(runDir, runPath), fullPage: true, animations: 'disabled',
          clip: { x: 0, y, width: 1440, height: Math.min(1800, height - y) },
        });
        addArtifact(runPath, `完整测试报告（第 ${index} 张）`);
        if (y + 1800 >= height) break;
      }
    }
  } finally {
    await browser.close();
  }
  facts.internal.artifacts = [
    ...(facts.internal.artifacts || []).filter(item => item.role !== 'report'),
    ...artifacts,
  ];
  fs.writeFileSync(factsPath, `${JSON.stringify(facts, null, 2)}\n`);
  return artifacts;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  if (args.length !== 2 || args[0] !== '--run-dir') {
    throw new Error('Usage: node e2e/scripts/capture-report.mjs --run-dir <runDir>');
  }
  console.log(JSON.stringify(await captureReport(path.resolve(args[1])), null, 2));
}
