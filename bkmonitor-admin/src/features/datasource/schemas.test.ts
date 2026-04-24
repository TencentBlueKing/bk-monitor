import { describe, expect, it } from 'vitest';

import { datasourceListQuerySchema } from './schemas';

describe('datasourceListQuerySchema', () => {
  it('coerces filter and pagination params', () => {
    expect(
      datasourceListQuerySchema.parse({
        bkTenantId: 'system',
        bkDataId: '50010',
        page: '2',
        pageSize: '50'
      })
    ).toMatchObject({
      bkTenantId: 'system',
      bkDataId: 50010,
      page: 2,
      pageSize: 50
    });
  });
});
