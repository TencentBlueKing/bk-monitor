/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { alertIncidentDetail, incidentDiagnosis, incidentResults, panelDetail } from 'monitor-api/modules/incident';

import type { RequestOptions } from '../../../../services/base';
import type {
  AlertIncidentDetailDto,
  DiagnosticPanelKey,
  IncidentDiagnosisDto,
  IncidentResultsDto,
  PanelDetailDto,
  PanelDetailParamsDto,
} from '../typing';

type IncidentApi = {
  alertIncidentDetail: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<unknown>;
  incidentDiagnosis: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<unknown>;
  incidentResults: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<unknown>;
  panelDetail: (params: Record<string, unknown>, config?: Record<string, unknown>) => Promise<unknown>;
};

const incidentApi: IncidentApi = {
  alertIncidentDetail,
  incidentDiagnosis,
  incidentResults,
  panelDetail,
};

const requestConfig = (options?: RequestOptions) => ({
  needMessage: false,
  ...(options?.signal ? { signal: options.signal } : {}),
});

export interface DiagnosticDataService {
  getAlertIncidentDetail(alertId: string, options?: RequestOptions): Promise<AlertIncidentDetailDto>;
  getIncidentDiagnosis(
    incidentDocumentId: string,
    bizId: number,
    subPanel: DiagnosticPanelKey,
    options?: RequestOptions
  ): Promise<IncidentDiagnosisDto>;
  getIncidentResults(incidentDocumentId: string, bizId: number, options?: RequestOptions): Promise<IncidentResultsDto>;
  getPanelDetail(params: PanelDetailParamsDto, options?: RequestOptions): Promise<PanelDetailDto>;
}

export const createDiagnosticDataService = (api: IncidentApi = incidentApi): DiagnosticDataService => ({
  getAlertIncidentDetail: (alertId, options) =>
    api.alertIncidentDetail(
      {
        alert_id: alertId,
        filter_one_hop: true,
      },
      requestConfig(options)
    ) as Promise<AlertIncidentDetailDto>,
  getIncidentDiagnosis: (incidentDocumentId, bizId, subPanel, options) =>
    api.incidentDiagnosis(
      {
        id: incidentDocumentId,
        bk_biz_ids: [bizId],
        sub_panel: subPanel,
      },
      requestConfig(options)
    ) as Promise<IncidentDiagnosisDto>,
  getIncidentResults: (incidentDocumentId, bizId, options) =>
    api.incidentResults(
      {
        id: incidentDocumentId,
        bk_biz_id: bizId,
      },
      requestConfig(options)
    ) as Promise<IncidentResultsDto>,
  getPanelDetail: (params, options) =>
    api.panelDetail(params as unknown as Record<string, unknown>, requestConfig(options)) as Promise<PanelDetailDto>,
});

export const diagnosticDataService = createDiagnosticDataService();
