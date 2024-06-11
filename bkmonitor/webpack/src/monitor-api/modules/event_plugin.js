import { request } from '../base';

export const listEventPlugin = request('GET', 'fta/plugin/event/');
export const getEventPlugin = request('GET', 'fta/plugin/event/{pk}/');
export const deployEventPlugin = request('POST', 'fta/plugin/event/');
export const createEventPlugin = request('POST', 'fta/plugin/event/');
export const importEventPlugin = request('POST', 'fta/plugin/event/import/');
export const updateEventPlugin = request('PUT', 'fta/plugin/event/{pk}/');
export const deleteEventPlugin = request('DELETE', 'fta/plugin/event/{pk}/');
export const getEventPluginInstance = request('GET', 'fta/plugin/event/{pk}/instances/');
export const tailEventPluginData = request('GET', 'fta/plugin/event/{pk}/tail/');
export const createEventPluginInstance = request('POST', 'fta/plugin/event/{pk}/instance/install/');
export const updateEventPluginInstance = request('PUT', 'fta/plugin/event/{pk}/instance/');
export const getEventPluginToken = request('GET', 'fta/plugin/event/{pk}/instance/token/');
export const disablePluginCollect = request('POST', 'fta/plugin/event/instance/disable_collect/');

export default {
  listEventPlugin,
  getEventPlugin,
  deployEventPlugin,
  createEventPlugin,
  importEventPlugin,
  updateEventPlugin,
  deleteEventPlugin,
  getEventPluginInstance,
  tailEventPluginData,
  createEventPluginInstance,
  updateEventPluginInstance,
  getEventPluginToken,
  disablePluginCollect,
};
