import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { createLocalSearchFetcher, RetrieveSearchController } from './retrieve-search-controller.ts';

const dataset = [
  { id: '1', dtEventTimeStamp: 1, log: 'error timeout from api' },
  { id: '2', dtEventTimeStamp: 2, log: 'info user login' },
  { id: '3', dtEventTimeStamp: 3, log: 'error disk full' },
];

describe('RetrieveSearchController', () => {
  it('AC-001 / AC-004 trims keyword and returns matching records', async () => {
    const controller = new RetrieveSearchController(createLocalSearchFetcher(dataset));
    const state = await controller.submit({ keyword: '  error  ' });
    assert.equal(state.keyword, 'error');
    assert.equal(state.uiState, 'success');
    assert.equal(state.records.length, 2);
    assert.ok(state.records.every(item => item.log.includes('error')));
  });

  it('AC-002 ignores stale responses', async () => {
    let releaseSlow;
    const slow = new Promise(resolve => {
      releaseSlow = resolve;
    });
    const fetcher = async ({ keyword, signal }) => {
      if (keyword === 'old') {
        await slow;
        if (signal.aborted) {
          throw new DOMException('Aborted', 'AbortError');
        }
        return { list: [{ id: 'old', dtEventTimeStamp: 1, log: 'old' }], total: 1 };
      }
      return { list: [{ id: 'new', dtEventTimeStamp: 2, log: 'new' }], total: 1 };
    };
    const controller = new RetrieveSearchController(fetcher);
    const first = controller.submit({ keyword: 'old' });
    const second = await controller.submit({ keyword: 'new' });
    releaseSlow();
    await first;
    assert.equal(second.uiState, 'success');
    assert.equal(second.keyword, 'new');
    assert.equal(controller.getState().records[0].id, 'new');
  });

  it('AC-003 resets page when keyword changes', async () => {
    const controller = new RetrieveSearchController(createLocalSearchFetcher(dataset));
    await controller.submit({ keyword: 'error', page: 3 });
    const next = await controller.submit({ keyword: 'info', page: 3 });
    assert.equal(next.page, 1);
    assert.equal(next.keyword, 'info');
  });
});
