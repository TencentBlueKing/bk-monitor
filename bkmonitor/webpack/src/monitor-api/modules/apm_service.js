import { request } from '../base';

export const serviceConfig = request('POST', 'apm/service/service/service_config/');
export const serviceInfo = request('POST', 'apm/service/service/service_info/');
export const listCodeRedefinedRule = request('POST', 'apm/service/service/list_code_redefined_rule/');
export const setCodeRedefinedRule = request('POST', 'apm/service/service/set_code_redefined_rule/');
export const deleteCodeRedefinedRule = request('POST', 'apm/service/service/delete_code_redefined_rule/');
export const cmdbServiceTemplate = request('POST', 'apm/service/service/cmdb_service_template/');
export const logServiceChoiceList = request('POST', 'apm/service/service/log_service_relation_choices/');
export const appQueryByIndexSet = request('POST', 'apm/service/service/app_query_by_index_set/');
export const uriregularVerify = request('POST', 'apm/service/service/uri_regular/');
export const serviceUrlList = request('POST', 'apm/service/service/service_url_list/');
export const pipelineOverview = request('POST', 'apm/service/service/pipeline_overview/');
export const listPipeline = request('POST', 'apm/service/service/list_pipeline/');
export const applicationList = request('POST', 'apm/service/application/application_list/');
export const logServiceRelationBkLogIndexSet = request('POST', 'apm/service/application/log_service_relation_bk_log_index_set/');

export default {
  serviceConfig,
  serviceInfo,
  listCodeRedefinedRule,
  setCodeRedefinedRule,
  deleteCodeRedefinedRule,
  cmdbServiceTemplate,
  logServiceChoiceList,
  appQueryByIndexSet,
  uriregularVerify,
  serviceUrlList,
  pipelineOverview,
  listPipeline,
  applicationList,
  logServiceRelationBkLogIndexSet,
};
