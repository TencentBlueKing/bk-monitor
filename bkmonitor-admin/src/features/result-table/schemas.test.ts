import { describe, expect, it } from 'vitest';

import { resultTableFieldListQuerySchema } from './schemas';

describe('resultTableFieldListQuerySchema', () => {
  it('keeps table id required and paginates field list', () => {
    const query = resultTableFieldListQuerySchema.parse({
      tableId: '2_bkmonitor_time_series.__default__',
      fieldName: 'metric',
      page: '3',
      pageSize: '20'
    });

    expect(query).toMatchObject({
      tableId: '2_bkmonitor_time_series.__default__',
      fieldName: 'metric',
      page: 3,
      pageSize: 20
    });
  });
});
