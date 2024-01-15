import { request } from '../base';
export const query = request('POST', 'apm/profile_api/query/samples/');
export const queryLabels = request('GET', 'apm/profile_api/query/labels/');
export const queryLabelValues = request('GET', 'apm/profile_api/query/label_values/');
export const queryServicesDetail = request('GET', 'apm/profile_api/query/services_detail/');
export const listApplicationServices = request('GET', 'apm/profile_api/query/services/');
export const upload = request('POST', 'apm/profile_api/upload/upload/');
export const listProfileUploadRecord = request('GET', 'apm/profile_api/query/records/');

export default {
  upload,
  query,
  queryLabels,
  queryLabelValues,
  queryServicesDetail,
  listApplicationServices,
  listProfileUploadRecord
};
