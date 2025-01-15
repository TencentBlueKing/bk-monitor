import { request } from '../base';

export const listDbStatistics = request('POST', 'apm/service_db/db/list_db_statistics/');
export const listDbSpan = request('POST', 'apm/service_db/db/list_db_span/');
export const listDbSystem = request('POST', 'apm/service_db/db/list_db_system/');

export default {
  listDbStatistics,
  listDbSpan,
  listDbSystem,
};
