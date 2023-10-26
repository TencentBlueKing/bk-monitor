import { request } from '../base';

export const getBkchatGroup = request('GET', 'rest/v2/bkchat_group/get_bkchat_group/');

export default {
  getBkchatGroup
};
