import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { GrepController, resolveGrepMountAction } from './grep-controller.ts';

const records = [
  { id: '1', dtEventTimeStamp: 1, log: 'error timeout from api' },
  { id: '2', dtEventTimeStamp: 2, log: 'info user login' },
  { id: '3', dtEventTimeStamp: 3, log: 'error disk full' },
];

describe('GrepController', () => {
  it('AC-001 waits while the main search is loading', () => {
    assert.equal(resolveGrepMountAction(true, 'log'), 'wait');
    const controller = new GrepController();
    const state = controller.search(records, true);
    assert.equal(state.uiState, 'waiting');
    assert.equal(state.matches.length, 0);
  });

  it('AC-002 stays idle without a field', () => {
    const controller = new GrepController();
    controller.setField('   ');
    const state = controller.search(records, false);
    assert.equal(state.field, '');
    assert.equal(state.uiState, 'idle');
    assert.equal(resolveGrepMountAction(false, ''), 'idle');
  });

  it('AC-003 filters current records by regex pattern', () => {
    const controller = new GrepController();
    controller.setPattern('error|login');
    const state = controller.search(records, false);
    assert.equal(state.uiState, 'success');
    assert.equal(state.matches.length, 3);
  });

  it('AC-004 rejects invalid regex instead of throwing through', () => {
    const controller = new GrepController();
    controller.setPattern('(');
    const state = controller.search(records, false);
    assert.equal(state.uiState, 'error');
    assert.equal(state.error, 'invalid grep pattern');
  });
});
