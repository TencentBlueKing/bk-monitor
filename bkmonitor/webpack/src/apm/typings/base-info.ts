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
import type { TranslateResult } from 'vue-i18n';

export interface IBaseParams {
  bk_biz_id: number;
  app_name: string;
  service_name: string;
}

export interface IBaseServiceInfo {
  labels: string[];
}

export interface IBaseInfoList {
  label: TranslateResult;
  icon: null | string;
  value: string;
}

export interface ICMDBInfoList {
  id: number;
  template_id: number;
  submitType: string;
}

export interface ICMDBSelectOption {
  id: number | string;
  name: string;
  firstValue: string;
  firstIcon: string;
  secondValue: string;
  secondIcon: string;
}

export interface ILogsInfoList {
  id?: number;
  log_type?: string;
  log_type_name?: string;
  value?: string;
  editValue: string;
  submitType: string;
  isSubmiting: boolean;
}

export interface ISelectOption {
  id: number | string;
  name: string;
}

export interface IAppInfoList {
  id?: number;
  relate_app_name?: string;
  relate_bk_biz_id?: number;
  relate_bk_biz_name?: string;
  editBkID: number | string;
  submitType: string;
}

export interface ISelectEditValue {
  activeItem: IAppInfoList | ICMDBInfoList | ILogsInfoList;
  selectValue: string;
  type: string;
}

export type IReqType = 'del' | 'get' | 'set';

export interface IExtraData {
  category_name: string;
  category_icon: string;
  predicate_value: string;
  predicate_value_icon: string;
  service_language: string;
}

export interface ICmdbRelationCategory {
  name: string;
  icon: string;
}

export interface ICmdbRelation {
  template_id?: number | string;
  id?: number;
  template_name?: string;
  first_category?: ICmdbRelationCategory;
  second_category?: ICmdbRelationCategory;
}

export interface ILogRelation {
  log_type: string;
  log_type_alias: string;
  value: string;
  value_alias?: string;
  related_bk_biz_id?: number;
  related_bk_biz_name?: string;
}

export interface IAppRelation {
  application_id: string;
  relate_app_name: string;
  relate_bk_biz_id: number;
  relate_bk_biz_name: string;
}

export interface IApdexRelation {
  apdex_value: number;
}

export interface IUriRelation {
  id: number;
  rank: number;
  uri: string;
}

export interface IServiceRelation {
  cmdb_relation?: ICmdbRelation;
  log_relation?: ILogRelation;
  app_relation?: IAppRelation;
  apdex_relation?: IApdexRelation;
  uri_relation?: IUriRelation[];
}

export interface IServiceInfo {
  topo_key: string;
  instance_count: number;
  extra_data: IExtraData;
  relation: IServiceRelation;
  labels: string[];
}

export interface ILocationRelation {
  cmdb: number | string;
  logType: string;
  logValue: string;
  bizId: number | string;
  appId: string;
  apdex: number;
  relatedBizId: number | string;
}

export interface ICmdbInfoItem {
  id: number;
  name: string;
}

export interface ILogInfoItem {
  id: string;
  name: string;
}

export interface IAppInfoItem {
  application_id: number;
  id: string;
  name: string;
}

export interface IIndexSetItem {
  id: string;
  name: string;
}

export interface IApplicationItem {
  id: string;
  name: string;
}
