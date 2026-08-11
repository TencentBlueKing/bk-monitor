import { request } from '../base';

export const listSourceAnalysisBkciProjects = request('GET', 'fta/issue/source_analysis_options/bkci_projects/');
export const listSourceAnalysisBkciRepositories = request('GET', 'fta/issue/source_analysis_options/bkci_repositories/');
export const listSourceAnalysisAgents = request('GET', 'fta/issue/source_analysis_options/agents/');
export const listSourceAnalysisSkills = request('GET', 'fta/issue/source_analysis_options/skills/');
export const listSourceAnalysisKnowledgeBases = request('GET', 'fta/issue/source_analysis_options/knowledge_bases/');
export const getSourceAnalysisConfig = request('GET', 'fta/issue/source_analysis_config/');
export const saveSourceAnalysisConfig = request('PUT', 'fta/issue/source_analysis_config/save/');
export const listSourceAnalysisRules = request('GET', 'fta/issue/source_analysis_rules/');
export const createSourceAnalysisRule = request('POST', 'fta/issue/source_analysis_rules/');
export const getSourceAnalysisRule = request('GET', 'fta/issue/source_analysis_rules/{pk}/');
export const updateSourceAnalysisRule = request('PATCH', 'fta/issue/source_analysis_rules/{pk}/');
export const deleteSourceAnalysisRule = request('DELETE', 'fta/issue/source_analysis_rules/{pk}/');
export const searchIssue = request('POST', 'fta/issue/issue/search/');
export const issueTrend = request('POST', 'fta/issue/issue/trend/');
export const issueTopN = request('POST', 'fta/issue/issue/top_n/');
export const issueDetail = request('GET', 'fta/issue/issue/detail/');
export const aiAnalysisOverview = request('GET', 'fta/issue/issue/ai_analysis_overview/');
export const sourceAnalysis = request('GET', 'fta/issue/issue/source_analysis/');
export const startSourceAnalysis = request('POST', 'fta/issue/issue/start_source_analysis/');
export const retrySourceAnalysis = request('POST', 'fta/issue/issue/retry_source_analysis/');
export const reanalyzeSourceAnalysis = request('POST', 'fta/issue/issue/reanalyze_source_analysis/');
export const sourceAnalysisRaw = request('GET', 'fta/issue/issue/source_analysis_raw/');
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
export const exportIssue = request('POST', 'fta/issue/issue/export/');
export const listRecentAssignees = request('POST', 'fta/issue/issue/recent_assignees/');
export const mergeIssue = request('POST', 'fta/issue/issue/merge/');
export const splitIssue = request('POST', 'fta/issue/issue/split/');
export const listMergeSources = request('GET', 'fta/issue/issue/merge_sources/');
export const alertIssueEnrich = request('POST', 'fta/issue/issue/alert_enrich/');
export const issueLogContent = request('POST', 'fta/issue/issue/log_content/');
export const listTapdWorkspace = request('POST', 'fta/issue/tapd/workspace/');
export const listUserTapdWorkspace = request('POST', 'fta/issue/tapd/user_workspace/');
export const unbindTapdWorkspace = request('POST', 'fta/issue/tapd/unbind_workspace/');
export const rebindTapdWorkspace = request('POST', 'fta/issue/tapd/rebind_workspace/');
export const revokeTapdUserAuth = request('POST', 'fta/issue/tapd/revoke_auth/');
export const getTapdFields = request('POST', 'fta/issue/issue/get_tapd_fields/');
export const searchTapdItems = request('POST', 'fta/issue/issue/search_tapd_items/');
export const createTapd = request('POST', 'fta/issue/issue/create_tapd/');
export const linkIssueToTapd = request('POST', 'fta/issue/issue/link_tapd/');
export const listIssueTapdRelations = request('POST', 'fta/issue/issue/tapd_relations/');

export default {
  listSourceAnalysisBkciProjects,
  listSourceAnalysisBkciRepositories,
  listSourceAnalysisAgents,
  listSourceAnalysisSkills,
  listSourceAnalysisKnowledgeBases,
  getSourceAnalysisConfig,
  saveSourceAnalysisConfig,
  listSourceAnalysisRules,
  createSourceAnalysisRule,
  getSourceAnalysisRule,
  updateSourceAnalysisRule,
  deleteSourceAnalysisRule,
  searchIssue,
  issueTrend,
  issueTopN,
  issueDetail,
  aiAnalysisOverview,
  sourceAnalysis,
  startSourceAnalysis,
  retrySourceAnalysis,
  reanalyzeSourceAnalysis,
  sourceAnalysisRaw,
  assignIssue,
  resolveIssue,
  reopenIssue,
  archiveIssue,
  restoreIssue,
  updateIssuePriority,
  renameIssue,
  addIssueFollowUp,
  editIssueFollowUp,
  listIssueActivities,
  listIssueHistory,
  exportIssue,
  listRecentAssignees,
  mergeIssue,
  splitIssue,
  listMergeSources,
  alertIssueEnrich,
  issueLogContent,
  listTapdWorkspace,
  listUserTapdWorkspace,
  unbindTapdWorkspace,
  rebindTapdWorkspace,
  revokeTapdUserAuth,
  getTapdFields,
  searchTapdItems,
  createTapd,
  linkIssueToTapd,
  listIssueTapdRelations,
};
