import { request } from '../base';

export const createShareToken = request('POST', 'rest/v2/share/create_share_token/');
export const updateShareToken = request('POST', 'rest/v2/share/update_share_token/');
export const deleteShareToken = request('POST', 'rest/v2/share/delete_share_token/');
export const getShareTokenList = request('POST', 'rest/v2/share/get_share_token_list/');
export const getShareParams = request('GET', 'rest/v2/get_token/get_share_params/');

export default {
  createShareToken,
  updateShareToken,
  deleteShareToken,
  getShareTokenList,
  getShareParams,
};
