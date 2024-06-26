import { request } from '../base';

export const getBkchatGroup = request('GET', 'rest/v2/bkchat_group/get_bkchat_group/');
export const previewDutyRulePlan = request('POST', 'rest/v2/duty_plan/preview_duty_rule_plan/');
export const previewUserGroupPlan = request('POST', 'rest/v2/duty_plan/preview_user_group_plan/');

export default {
  getBkchatGroup,
  previewDutyRulePlan,
  previewUserGroupPlan,
};
