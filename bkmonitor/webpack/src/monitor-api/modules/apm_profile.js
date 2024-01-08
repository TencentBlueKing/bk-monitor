import { request } from '../base';

export const query = request('POST', 'apm/profile_api/profiling/query/');
export const upload = request('POST', 'apm/profile_api/profiling/upload/');
export const listProfileUploadRecord = request('GET', 'apm/profile_api/profiling/list_profile_upload_records/');

export default {
  query,
  upload,
  listProfileUploadRecord
};
