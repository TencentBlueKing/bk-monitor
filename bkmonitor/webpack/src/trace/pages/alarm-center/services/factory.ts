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

import { AlarmType } from '../typings';
import { ActionService } from './action-services';
import { AlertService } from './alert-services';
import { IncidentService } from './incident-services';

export type AlarmServiceType<T = AlarmType> = T extends AlarmType.ACTION
  ? ActionService
  : T extends AlarmType.INCIDENT
    ? IncidentService
    : AlertService;

// export class AlarmContextProxy {
//   protected service: AlarmServiceType;
//   constructor(public type: AlarmType) {
//     this.service = AlarmServiceFactory(type);
//   }
//   get analysisFields() {
//     return this.service.analysisFields;
//   }
//   getAnalysisDimensionFields(params: Partial<CommonFilterParams>) {
//     return this.service.getAnalysisDimensionFields(params);
//   }
//   getAnalysisTopNData(params: Partial<CommonFilterParams>) {
//     return this.service.getAnalysisTopNData(params);
//   }
//   getFilterTableList(params: Partial<CommonFilterParams>) {
//     return this.service.getFilterTableList(params);
//   }
//   getQuickFilterList(params: Partial<CommonFilterParams>) {
//     return this.service.getQuickFilterList(params);
//   }
//   // getTableColumns() {
//   //   if (this.type === AlarmType.ACTION) {
//   //     return this.service.getTableColumns();
//   //   }
//   //   return [];
//   // }
// }

// export function AlarmServiceFactory(type: AlarmType.ALERT): AlertService;
// export function AlarmServiceFactory(type: AlarmType.INCIDENT): IncidentService;
// export function AlarmServiceFactory(type: AlarmType.ACTION): ActionService;
export function AlarmServiceFactory(type: AlarmType) {
  if (type === AlarmType.ACTION) {
    return new ActionService(AlarmType.ACTION);
  }
  if (type === AlarmType.INCIDENT) {
    return new IncidentService(AlarmType.INCIDENT);
  }
  return new AlertService(AlarmType.ALERT);
}
