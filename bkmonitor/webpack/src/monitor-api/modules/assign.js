import { request } from '../base';

export const batchUpdate = request('POST', 'fta/assign/rule_operate/batch_update/');
export const matchDebug = request('POST', 'fta/assign/rule_operate/match_debug/');
export const getAssignConditionKeys = request('GET', 'fta/assign/rule_operate/get_assign_condition_keys/');
export const searchObjectAttribute = request('GET', 'fta/assign/cmdb/search_object_attribute/');

export default {
  batchUpdate,
  matchDebug,
  getAssignConditionKeys,
  searchObjectAttribute,
};
