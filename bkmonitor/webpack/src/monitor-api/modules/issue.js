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
export const listRecentAssignees = request('POST', 'fta/issue/issue/recent_assignees/');
export const mergeIssue = request('POST', 'fta/issue/issue/merge/');
export const splitIssue = request('POST', 'fta/issue/issue/split/');
export const listMergeSources = request('GET', 'fta/issue/issue/merge_sources/');
export const alertIssueEnrich = request('POST', 'fta/issue/issue/alert_enrich/');
export const listTapdWorkspace = request('POST', 'fta/issue/tapd/workspace/');
export const getTapdFields = request('POST', 'fta/issue/issue/get_tapd_fields/');
export const searchTAPDItems = request('POST', 'fta/issue/issue/search_tapd_items/');
export const createTapd = request('POST', 'fta/issue/issue/create_tapd/');
export const listIssueTapdRelations = request('POST', 'fta/issue/issue/tapd_relations/');
export const linkIssueToTapd = request('POST', 'fta/issue/issue/link_tapd/');


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
  listRecentAssignees,
  mergeIssue,
  splitIssue,
  listMergeSources,
  alertIssueEnrich,
  listTapdWorkspace,
  getTapdFields,
  searchTAPDItems,
  createTapd,
  listIssueTapdRelations,
  linkIssueToTapd,
};
