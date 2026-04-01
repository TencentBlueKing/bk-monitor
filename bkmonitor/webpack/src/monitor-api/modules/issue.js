import { request } from '../base';

export const assignIssue = request('POST', 'fta/issue/issue/assign/');
export const resolveIssue = request('POST', 'fta/issue/issue/resolve/');
export const archiveIssue = request('POST', 'fta/issue/issue/archive/');
export const updateIssuePriority = request('POST', 'fta/issue/issue/update_priority/');
export const addIssueFollowUp = request('POST', 'fta/issue/issue/add_follow_up/');
export const listIssueActivities = request('GET', 'fta/issue/issue/activities/');
export const listIssueHistory = request('GET', 'fta/issue/issue/history/');


export default {
  assignIssue,
  resolveIssue,
  archiveIssue,
  updateIssuePriority,
  addIssueFollowUp,
  listIssueActivities,
  listIssueHistory,
};
