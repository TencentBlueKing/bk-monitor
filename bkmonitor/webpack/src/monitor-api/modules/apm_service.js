import { request } from '../base';

export const serviceConfig = request('POST', 'apm/service/service/service_config/');
export const serviceInfo = request('POST', 'apm/service/service/service_info/');
export const cmdbServiceTemplate = request('POST', 'apm/service/service/cmdb_service_template/');
export const logServiceChoiceList = request('POST', 'apm/service/service/log_service_relation_choices/');
export const appQueryByIndexSet = request('POST', 'apm/service/service/app_query_by_index_set/');
export const uriregularVerify = request('POST', 'apm/service/service/uri_regular/');
export const serviceUrlList = request('POST', 'apm/service/service/service_url_list/');
export const applicationList = request('POST', 'apm/service/application/application_list/');
export const logServiceRelationBkLogIndexSet = request('POST', 'apm/service/application/log_service_relation_bk_log_index_set/');

export default {
  serviceConfig,
  serviceInfo,
  cmdbServiceTemplate,
  logServiceChoiceList,
  appQueryByIndexSet,
  uriregularVerify,
  serviceUrlList,
  applicationList,
  logServiceRelationBkLogIndexSet,
};
