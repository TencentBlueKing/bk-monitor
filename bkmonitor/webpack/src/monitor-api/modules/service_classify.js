import { request } from '../base';

export const serviceCategoryList = request('GET', 'rest/v2/service_classify/service_category_list/');

export default {
  serviceCategoryList,
};
