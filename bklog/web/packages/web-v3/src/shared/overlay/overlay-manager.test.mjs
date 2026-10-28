import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { OverlayManager } from './overlay-manager.ts';

describe('OverlayManager', () => {
  it('stacks overlays with increasing z-index', () => {
    const manager = new OverlayManager();
    const dialog = manager.open({ id: 'dialog-a', kind: 'dialog' });
    const drawer = manager.open({ id: 'drawer-a', kind: 'drawer' });
    assert.ok(drawer.zIndex > dialog.zIndex);
    assert.equal(manager.getTop().id, 'drawer-a');
  });

  it('replaces overlays in the same group', () => {
    const manager = new OverlayManager();
    manager.open({ id: 'popup-a', kind: 'popup', group: 'search-suggest' });
    manager.open({ id: 'popup-b', kind: 'popup', group: 'search-suggest' });
    assert.equal(manager.getStack().length, 1);
    assert.equal(manager.getTop().id, 'popup-b');
  });

  it('Escape closes the top dismissible overlay only', () => {
    const manager = new OverlayManager();
    manager.open({ id: 'locked', kind: 'dialog', dismissible: false });
    manager.open({ id: 'tip', kind: 'popup' });
    const closed = manager.handleEscape();
    assert.equal(closed.id, 'tip');
    assert.equal(manager.getTop().id, 'locked');
    assert.equal(manager.handleEscape(), null);
  });
});
