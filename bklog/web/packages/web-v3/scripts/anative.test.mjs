import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { analyzeImpact, checkContracts, validateSpecs } from './anative.mjs';

describe('anative CLI', () => {
  it('validates feature and related contracts', () => {
    const result = validateSpecs();
    assert.equal(result.ok, true, result.errors.join('\n'));
    assert.ok(result.counts.feature >= 1);
  });

  it('checks contract references', () => {
    const result = checkContracts();
    assert.equal(result.ok, true, result.errors.join('\n'));
  });

  it('reports retrieve impact files', () => {
    const result = analyzeImpact();
    assert.equal(result.ok, true);
    assert.ok(result.files.includes('src/features/retrieve/retrieve-search-controller.ts'));
  });
});
