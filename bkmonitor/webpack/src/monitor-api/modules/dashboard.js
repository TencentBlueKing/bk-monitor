/*
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
*/
import { request } from '../base';

export const phoneReceiver = request('GET', 'rest/v2/phone_receiver/');
export const memberData = request('GET', 'rest/v2/member_data/');
export const addMenu = request('POST', 'rest/v2/add_menu/');
export const editMenu = request('POST', 'rest/v2/edit_menu/');
export const deleteMenu = request('POST', 'rest/v2/delete_menu/');
export const listMetrics = request('GET', 'rest/v2/list_metrics/');
export const fieldValues = request('GET', 'rest/v2/field_values/');
export const seriesInfo = request('POST', 'rest/v2/series_info/');
export const saveView = request('POST', 'rest/v2/save_view/');
export const deleteLocation = request('POST', 'rest/v2/delete_location/');
export const addLocation = request('GET', 'rest/v2/add_location/');
export const getView = request('GET', 'rest/v2/view/');
export const viewGraph = request('POST', 'rest/v2/view_graph/');

export default {
  phoneReceiver,
  memberData,
  addMenu,
  editMenu,
  deleteMenu,
  listMetrics,
  fieldValues,
  seriesInfo,
  saveView,
  deleteLocation,
  addLocation,
  getView,
  viewGraph
};
