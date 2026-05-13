import { request } from '../base';

export const assignIssue = request('POST', 'fta/issue/issue/assign/');
export const resolveIssue = request('POST', 'fta/issue/issue/resolve/');
export const reopenIssue = request('POST', 'fta/issue/issue/reopen/');
export const archiveIssue = request('POST', 'fta/issue/issue/archive/');
export const restoreIssue = request('POST', 'fta/issue/issue/restore/');
export const updateIssuePriority = request('POST', 'fta/issue/issue/update_priority/');
export const renameIssue = request('POST', 'fta/issue/issue/rename/');
export const addIssueFollowUp = request('POST', 'fta/issue/issue/add_follow_up/');
export const editIssueFollowUp = request('POST', 'fta/issue/issue/edit_follow_up/');
export const listIssueActivities = request('GET', 'fta/issue/issue/activities/');
export const listIssueHistory = request('GET', 'fta/issue/issue/history/');
export const issueDetail = request('GET', 'fta/issue/issue/detail/');
export const issueSearch = request('POST', 'fta/issue/issue/search/');
export const issueTopN = request('POST', 'fta/issue/issue/top_n/');
export const exportIssue = request('POST', 'fta/issue/issue/export/');


export default {
  assignIssue,
  resolveIssue,
  reopenIssue,
  restoreIssue,
  archiveIssue,
  updateIssuePriority,
  renameIssue,
  addIssueFollowUp,
  editIssueFollowUp,
  listIssueActivities,
  listIssueHistory,
  issueDetail,
  issueSearch,
  issueTopN,
  exportIssue,
};
