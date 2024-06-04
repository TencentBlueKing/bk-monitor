import { request } from '../base';

export const saveCalendar = request('POST', 'calendars/save_calendar/');
export const editCalendar = request('POST', 'calendars/edit_calendar/');
export const getCalendar = request('GET', 'calendars/get_calendar/');
export const listCalendar = request('GET', 'calendars/list_calendar/');
export const deleteCalendar = request('POST', 'calendars/delete_calendar/');
export const saveItem = request('POST', 'calendars/save_item/');
export const deleteItem = request('POST', 'calendars/delete_item/');
export const editItem = request('POST', 'calendars/edit_item/');
export const itemDetail = request('POST', 'calendars/item_detail/');
export const itemList = request('POST', 'calendars/item_list/');
export const getTimeZone = request('GET', 'calendars/get_time_zone/');
export const getParentItemList = request('GET', 'calendars/get_parent_item_list/');

export default {
  saveCalendar,
  editCalendar,
  getCalendar,
  listCalendar,
  deleteCalendar,
  saveItem,
  deleteItem,
  editItem,
  itemDetail,
  itemList,
  getTimeZone,
  getParentItemList,
};
