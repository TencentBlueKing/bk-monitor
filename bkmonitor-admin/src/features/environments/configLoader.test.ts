import { describe, expect, it } from 'vitest';

import { defaultAdminConfig } from './defaults';
import { resolveDefaultEnvironmentId } from './configLoader';

describe('resolveDefaultEnvironmentId', () => {
  it('falls back to first configured environment when default id is invalid', () => {
    expect(
      resolveDefaultEnvironmentId({
        ...defaultAdminConfig,
        defaultEnvironmentId: 'missing'
      })
    ).toBe('local');
  });

  it('returns empty default id when no environment exists', () => {
    expect(resolveDefaultEnvironmentId({ environments: [] })).toBe('');
  });
});
