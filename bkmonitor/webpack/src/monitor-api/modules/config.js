import { request } from '../base';

export const listGlobalConfig = request('GET', 'rest/v2/global_config/');
export const setGlobalConfig = request('POST', 'rest/v2/global_config/');

export default {
  listGlobalConfig,
  setGlobalConfig,
};
