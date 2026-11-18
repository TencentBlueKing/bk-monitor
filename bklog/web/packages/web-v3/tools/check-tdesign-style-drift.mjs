/** Advisory gate for new business-level TDesign coupling. Source metadata only. */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const project = fileURLToPath(new URL('../', import.meta.url));
const baselineFile = process.argv[2] || fileURLToPath(new URL('../../../analyze-info/reports/alignment-audit-20261112/tdesign-style-inventory.json', import.meta.url));
const baseline = JSON.parse(readFileSync(baselineFile, 'utf8'));
// The original inventory is historical. Later reviews apply to exact file/class pairs only.
const reviewed = process.argv[2] ? {} : JSON.parse(
  readFileSync(new URL('../ai-native/tdesign-reviewed-selectors.json', import.meta.url), 'utf8'),
);
const current = JSON.parse(execFileSync(process.execPath, ['tools/audit-tdesign-styles.mjs'], { cwd: project, encoding: 'utf8' }));
const previous = new Map(baseline.files.map(file => [file.file, file]));
const warnings = current.files.filter(file => file.file.startsWith('features/')).flatMap(file => {
  const old = previous.get(file.file);
  const added = file.classes.filter(value => !old?.classes.includes(value) && !reviewed[file.file]?.[value]?.trim());
  const importantGrowth = Math.max(0, file.importantInFile - (old?.importantInFile || 0));
  return added.length || importantGrowth ? [{ file: file.file, addedClasses: added, importantGrowth }] : [];
});
console.log(JSON.stringify({ status: warnings.length ? 'REVIEW_REQUIRED' : 'NO_NEW_COUPLING', mode: 'advisory', warnings }, null, 2));
