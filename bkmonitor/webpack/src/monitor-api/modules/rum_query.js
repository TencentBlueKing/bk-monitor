import { request } from '../base';

export const rumRecords = request('POST', 'rum/search/list_records/');
export const rumViewConfig = request('GET', 'rum/search/view_config/');
export const rumFieldsOptionValues = request('POST', 'rum/search/get_fields_option_values/');
export const rumGenerateQueryString = request('POST', 'rum/search/generate_query_string/');

export default {
  rumRecords,
  rumViewConfig,
  rumFieldsOptionValues,
  rumGenerateQueryString,
};
