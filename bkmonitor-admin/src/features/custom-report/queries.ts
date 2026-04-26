import { useQuery } from '@tanstack/react-query';

import type { AdminEnvironment } from '../environments/schemas';
import { getCustomReportDetail, listCustomReportMetrics, listCustomReports } from './api';
import type {
  CustomReportListQuery,
  CustomReportMetricListQuery,
  CustomReportType
} from './schemas';

export function useCustomReportList(environment: AdminEnvironment, query: CustomReportListQuery) {
  return useQuery({
    queryKey: ['custom-report', environment.id, environment, 'list', query],
    queryFn: () => listCustomReports(environment, query)
  });
}

export function useCustomReportDetail(
  environment: AdminEnvironment,
  params: { bkTenantId: string; reportType: CustomReportType; groupId: number },
  enabled = true
) {
  return useQuery({
    queryKey: ['custom-report', environment.id, environment, 'detail', params],
    queryFn: () =>
      getCustomReportDetail(environment, {
        ...params,
        include: ['datasource', 'result_table', 'monitor_web', 'apm']
      }),
    enabled
  });
}

export function useCustomReportMetricList(
  environment: AdminEnvironment,
  query: CustomReportMetricListQuery,
  enabled = true
) {
  return useQuery({
    queryKey: ['custom-report', environment.id, environment, 'metric-list', query],
    queryFn: () => listCustomReportMetrics(environment, query),
    enabled
  });
}
