import { request } from '../base';

export const getAuthorityMeta = request('GET', 'rest/v2/iam/get_authority_meta/');
export const checkAllowedByActionIds = request('POST', 'rest/v2/iam/check_allowed_by_action_ids/');
export const getAuthorityDetail = request('POST', 'rest/v2/iam/get_authority_detail/');
export const checkAllowed = request('POST', 'rest/v2/iam/check_allowed/');
export const checkAllowedByApmApplication = request('POST', 'rest/v2/iam/check_allowed_by_apm_application/');
export const getAuthorityApplyInfo = request('POST', 'rest/v2/iam/get_authority_apply_info/');
export const test = request('GET', 'rest/v2/iam/test/');
export const getExternalPermissionList = request('GET', 'rest/v2/external/get_external_permission_list/');
export const getByAction = request('GET', 'rest/v2/external/get_resource_by_action/');
export const createOrUpdateExternalPermission = request('POST', 'rest/v2/external/create_or_update_external_permission/');
export const deleteExternalPermission = request('POST', 'rest/v2/external/delete_external_permission/');
export const createOrUpdateAuthorizer = request('POST', 'rest/v2/external/create_or_update_authorizer/');
export const getAuthorizerByBiz = request('GET', 'rest/v2/external/get_authorizer_by_biz/');
export const getAuthorizerList = request('GET', 'rest/v2/external/get_authorizer_list/');
export const getApplyRecordList = request('GET', 'rest/v2/external/get_apply_record_list/');
export const callback = request('GET', 'rest/v2/external/callback/');

export default {
  getAuthorityMeta,
  checkAllowedByActionIds,
  getAuthorityDetail,
  checkAllowed,
  checkAllowedByApmApplication,
  getAuthorityApplyInfo,
  test,
  getExternalPermissionList,
  getByAction,
  createOrUpdateExternalPermission,
  deleteExternalPermission,
  createOrUpdateAuthorizer,
  getAuthorizerByBiz,
  getAuthorizerList,
  getApplyRecordList,
  callback,
};
