import { request } from '../base';

export const rumRecords = request('POST', 'rum/search/list_records/');
export const rumViewConfig = request('GET', 'rum/search/view_config/');
export const rumFieldsOptionValues = request('POST', 'rum/search/get_fields_option_values/');
export const rumGenerateQueryString = request('POST', 'rum/search/generate_query_string/');
export const rumFieldsTopK = request('POST', 'rum/search/fields_topk/');
export const rumFieldStatisticsInfo = request('POST', 'rum/search/field_statistics_info/');
export const rumFieldStatisticsGraph = request('POST', 'rum/search/field_statistics_graph/');
export const rumDownloadTopk = request('POST', '/rum/search/download_topk/');

export default {
  rumRecords,
  rumViewConfig,
  rumFieldsOptionValues,
  rumGenerateQueryString,
  rumFieldsTopK,
  rumFieldStatisticsInfo,
  rumFieldStatisticsGraph,
  rumDownloadTopk,
};
