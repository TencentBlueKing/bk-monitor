import { request } from '../base';

export const getSubscriptionList = request('POST', 'rest/v2/email_subscription/get_subscription_list/');
export const getSubscription = request('GET', 'rest/v2/email_subscription/get_subscription/');
export const cloneSubscription = request('POST', 'rest/v2/email_subscription/clone_subscription/');
export const createOrUpdateSubscription = request('POST', 'rest/v2/email_subscription/create_or_update_subscription/');
export const deleteSubscription = request('POST', 'rest/v2/email_subscription/delete_subscription/');
export const sendSubscription = request('POST', 'rest/v2/email_subscription/send_subscription/');
export const cancelSubscription = request('POST', 'rest/v2/email_subscription/cancel_subscription/');
export const getSendRecords = request('GET', 'rest/v2/email_subscription/get_send_records/');
export const getApplyRecords = request('GET', 'rest/v2/email_subscription/get_apply_records/');
export const getVariables = request('GET', 'rest/v2/email_subscription/get_variables/');
export const getExistSubscriptions = request('GET', 'rest/v2/email_subscription/get_exist_subscriptions/');

export default {
  getSubscriptionList,
  getSubscription,
  cloneSubscription,
  createOrUpdateSubscription,
  deleteSubscription,
  sendSubscription,
  cancelSubscription,
  getSendRecords,
  getApplyRecords,
  getVariables,
  getExistSubscriptions
};
