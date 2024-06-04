import { request } from '../base';

export const getReceiver = request('GET', 'rest/v2/notice_group/get_receiver/');
export const getNoticeWay = request('GET', 'rest/v2/notice_group/get_notice_way/');
export const noticeGroupConfig = request('POST', 'rest/v2/notice_group/notice_group_config/');
export const deleteNoticeGroup = request('POST', 'rest/v2/notice_group/delete_notice_group/');
export const noticeGroupList = request('GET', 'rest/v2/notice_group/notice_group_list/');
export const noticeGroupDetail = request('GET', 'rest/v2/notice_group/notice_group_detail/');

export default {
  getReceiver,
  getNoticeWay,
  noticeGroupConfig,
  deleteNoticeGroup,
  noticeGroupList,
  noticeGroupDetail,
};
