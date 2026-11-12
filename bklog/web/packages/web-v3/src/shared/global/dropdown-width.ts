import type { Props } from 'tippy.js';

type DropdownModifier = NonNullable<NonNullable<Props['popperOptions']>['modifiers']>[number];

/** Match a custom dropdown to its reference border box on every Popper layout pass. */
export const dropdownWidthModifier: DropdownModifier = {
  name: 'bklogDropdownWidth',
  enabled: true,
  phase: 'beforeWrite' as const,
  requires: ['computeStyles'],
  fn({ state }) {
    state.styles.popper.width = `${state.rects.reference.width}px`;
  },
};
