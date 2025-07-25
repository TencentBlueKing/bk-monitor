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
export enum RelationEventType {
  K8s = 'k8s_event',
  pipeline = 'cicd_event',
  System = 'system_event',
}
export interface IApdexRelation {
  apdex_value: number;
}

export interface IAppInfoItem {
  application_id: number;
  id: string;
  name: string;
}

export interface IAppInfoList {
  editBkID: number | string;
  id?: number;
  relate_app_name?: string;
  relate_bk_biz_id?: number;
  relate_bk_biz_name?: string;
  submitType: string;
}

export interface IApplicationItem {
  id: string;
  name: string;
}

export interface IAppRelation {
  application_id: string;
  relate_app_name: string;
  relate_bk_biz_id: number;
  relate_bk_biz_name: string;
}

export interface IBaseInfoList {
  icon: null | string;
  label: TranslateResult;
  value: string;
}

export interface IBaseParams {
  app_name: string;
  bk_biz_id: number;
  service_name: string;
}

export interface IBaseServiceInfo {
  labels: string[];
}

export interface ICmdbInfoItem {
  id: number;
  name: string;
}

export interface ICMDBInfoList {
  id: number;
  submitType: string;
  template_id: number;
}

export interface ICmdbRelation {
  first_category?: ICmdbRelationCategory;
  id?: number;
  second_category?: ICmdbRelationCategory;
  template_id?: number | string;
  template_name?: string;
}

export interface ICmdbRelationCategory {
  icon: string;
  name: string;
}

export interface ICMDBSelectOption {
  firstIcon: string;
  firstValue: string;
  id: number | string;
  name: string;
  secondIcon: string;
  secondValue: string;
}

export interface IExtraData {
  category_icon: string;
  category_name: string;
  predicate_value: string;
  predicate_value_icon: string;
  service_language: string;
}

export interface IIndexSetItem {
  id: string;
  name: string;
}

export interface ILocationRelation {
  apdex: number;
  appId: string;
  bizId: number | string;
  cmdb: number | string;
  logType: string;
  logValue: string;
  relatedBizId: number | string;
}

export interface ILogInfoItem {
  id: string;
  name: string;
}

export interface ILogRelation {
  log_type: string;
  log_type_alias: string;
  related_bk_biz_id?: number;
  related_bk_biz_name?: string;
  value: string;
  value_alias?: string;
}

export interface ILogsInfoList {
  editValue: string;
  id?: number;
  isSubmiting: boolean;
  log_type?: string;
  log_type_name?: string;
  submitType: string;
  value?: string;
}

export type IReqType = 'del' | 'get' | 'set';

export interface ISelectEditValue {
  activeItem: IAppInfoList | ICMDBInfoList | ILogsInfoList;
  selectValue: string;
  type: string;
}

export interface ISelectOption {
  id: number | string;
  name: string;
}

export interface IServiceInfo {
  extra_data: IExtraData;
  instance_count: number;
  labels: string[];
  relation: IServiceRelation;
  topo_key: string;
}

export interface IServiceRelation {
  apdex_relation?: IApdexRelation;
  app_relation?: IAppRelation;
  cmdb_relation?: ICmdbRelation;
  log_relation?: ILogRelation;
  uri_relation?: IUriRelation[];
  event_relation?: {
    options: {
      is_auto: boolean;
    };
    relations: {
      bcs_cluster_id?: string;
      kind?: string;
      name?: string;
      namespace?: string;
    }[];
    table: RelationEventType;
  }[];
}

export interface IUriRelation {
  id: number;
  rank: number;
  uri: string;
}
