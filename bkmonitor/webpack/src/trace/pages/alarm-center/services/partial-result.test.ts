import assert from 'node:assert/strict';
import test from 'node:test';

import { getPartialResultState } from './partial-result.ts';

test('normalizes an incomplete backend response for the alarm table', () => {
  const state = getPartialResultState({
    is_partial: true,
    partial_reasons: [
      {
        code: 'notice_way_candidate_limit',
        scopes: ['alerts', 'total'],
        scanned_candidate_count: 10000,
        candidate_limit: 10000,
      },
    ],
    total_relation: 'gte',
  });

  assert.deepEqual(state, {
    isPartial: true,
    partialReasons: [
      {
        code: 'notice_way_candidate_limit',
        scopes: ['alerts', 'total'],
        scanned_candidate_count: 10000,
        candidate_limit: 10000,
      },
    ],
    totalRelation: 'gte',
  });
});

test('uses complete defaults for older backend responses', () => {
  assert.deepEqual(getPartialResultState({}), {
    isPartial: false,
    partialReasons: [],
    totalRelation: 'eq',
  });
});

test('keeps a lower-bound total separate from partial result state', () => {
  assert.deepEqual(
    getPartialResultState({
      is_partial: false,
      partial_reasons: [],
      total_relation: 'gte',
    }),
    {
      isPartial: false,
      partialReasons: [],
      totalRelation: 'gte',
    }
  );
});
