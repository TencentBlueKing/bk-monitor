import { request } from '../base';

export const profileQuery = request('GET', 'apm/profile_api/profiles/');

export default {
  profileQuery
};
