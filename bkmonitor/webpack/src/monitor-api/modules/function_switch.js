import { request } from '../base';

export const listFunction = request('GET', 'rest/v2/function_switch/');
export const switchFunction = request('POST', 'rest/v2/function_switch/switch/');

export default {
  listFunction,
  switchFunction
};
