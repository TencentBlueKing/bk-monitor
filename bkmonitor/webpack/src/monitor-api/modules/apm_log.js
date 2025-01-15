import { request } from '../base';

export const serviceLogInfo = request('POST', 'apm/service_log/log/log_relation/');
export const serviceRelationList = request('POST', 'apm/service_log/log/log_relation_list/');

export default {
  serviceLogInfo,
  serviceRelationList,
};
