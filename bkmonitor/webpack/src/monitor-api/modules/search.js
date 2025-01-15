import { request } from '../base';

export const globalSearch = request('GET', 'rest/v2/search/');

export default {
  globalSearch,
};
