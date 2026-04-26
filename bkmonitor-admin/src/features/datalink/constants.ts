import { Database, Network, Table, HardDrive, ArrowLeftRight, GitFork, Server } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface KindTab {
  kind: string;
  label: string;
  icon: LucideIcon;
  isClusterConfig?: boolean;
  isDataLink?: boolean;
}

export const DATA_LINK_KIND_TABS: KindTab[] = [
  { kind: 'DataLink', label: '链路', icon: Network, isDataLink: true },
  { kind: 'DataId', label: '数据源配置', icon: Database },
  { kind: 'ResultTable', label: '结果表', icon: Table },
  { kind: 'VmStorageBinding', label: 'VM 绑定', icon: HardDrive },
  { kind: 'ElasticSearchBinding', label: 'ES 绑定', icon: HardDrive },
  { kind: 'DorisBinding', label: 'Doris 绑定', icon: HardDrive },
  { kind: 'Databus', label: '数据总线', icon: ArrowLeftRight },
  { kind: 'ConditionalSink', label: '条件路由', icon: GitFork },
  { kind: 'ClusterConfig', label: '集群配置', icon: Server, isClusterConfig: true }
] as const;

export const CLUSTER_CONFIG_KIND_OPTIONS = [
  { label: 'KafkaChannel', value: 'KafkaChannel' },
  { label: 'VmStorage', value: 'VmStorage' },
  { label: 'ElasticSearch', value: 'ElasticSearch' },
  { label: 'Doris', value: 'Doris' }
] as const;

export const DATA_LINK_STRATEGY_OPTIONS = [
  { label: 'bk_standard_v2_event', value: 'bk_standard_v2_event' },
  { label: 'bk_standard_v2_time_series', value: 'bk_standard_v2_time_series' },
  { label: 'bk_exporter_time_series', value: 'bk_exporter_time_series' },
  { label: 'bk_standard_time_series', value: 'bk_standard_time_series' },
  { label: 'bcs_federal_proxy_time_series', value: 'bcs_federal_proxy_time_series' },
  { label: 'bcs_federal_subset_time_series', value: 'bcs_federal_subset_time_series' },
  { label: 'basereport_time_series_v1', value: 'basereport_time_series_v1' },
  { label: 'system_proc_perf', value: 'system_proc_perf' },
  { label: 'system_proc_port', value: 'system_proc_port' },
  { label: 'base_event_v1', value: 'base_event_v1' },
  { label: 'bk_log', value: 'bk_log' }
] as const;

export const NAMESPACE_OPTIONS = [
  { label: 'bkmonitor', value: 'bkmonitor' },
  { label: 'bklog', value: 'bklog' }
] as const;
