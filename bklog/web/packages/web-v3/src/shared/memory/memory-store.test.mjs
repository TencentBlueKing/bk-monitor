import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { MemoryStore } from './memory-store.ts';

describe('MemoryStore', () => {
  it('loads only active memories matching the current task', () => {
    const store = new MemoryStore([
      { id: 'memory.vue3-not-copy', type: 'decision', status: 'active', summary: 'do not copy vue2', hitCount: 0 },
      { id: 'memory.old-rule', type: 'rule', status: 'stale', summary: 'vue2 dialog hack', hitCount: 9 },
    ]);
    const hits = store.query('vue2');
    assert.equal(hits.length, 1);
    assert.equal(hits[0].id, 'memory.vue3-not-copy');
  });

  it('increments hit count without treating frequency as truth', () => {
    const store = new MemoryStore([
      { id: 'memory.tdesign-token-only', type: 'rule', status: 'active', summary: 'css variables', hitCount: 0 },
    ]);
    store.hit('memory.tdesign-token-only', '2026-10-26T00:00:00.000Z');
    assert.equal(store.list()[0].hitCount, 1);
    store.markStale('memory.tdesign-token-only');
    assert.equal(store.query('css').length, 0);
  });
});
