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

import { SceneType } from './types';
import type { SceneConfig } from './types';

/** 6个场景的完整配置 */
export const sceneConfigs: SceneConfig[] = [
  {
    type: SceneType.Container,
    label: '容器',
    icon: 'bklog-container-2',
    fields: [
      {
        label: '集群',
        fieldName: '__ext.bk_bcs_cluster_id',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
        multiple: true,
      },
      {
        label: '输出流',
        fieldName: 'stream',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'static',
        staticOptions: [
          { id: 'stdout', name: 'stdout' },
          { id: 'file', name: 'file' },
        ],
      },
      {
        label: '命名空间',
        fieldName: '__ext.io_kubernetes_pod_namespace',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
        multiple: true,
      },
      {
        label: '工作负载类型',
        fieldName: '__ext.io_kubernetes_workload_type',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'static',
        staticOptions: [
          { id: 'ReplicaSet', name: 'ReplicaSet' },
          { id: 'Deployment', name: 'Deployment' },
          { id: 'StatefulSet', name: 'StatefulSet' },
          { id: 'DaemonSet', name: 'DaemonSet' },
        ],
      },
      {
        label: '工作负载名称',
        fieldName: '__ext.io_kubernetes_workload_name',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
        multiple: true,
      },
      {
        label: 'Pod名称',
        fieldName: '__ext.io_kubernetes_pod',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '容器名称',
        fieldName: '__ext.container_name',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
        multiple: true,
      },
      {
        label: '节点IP',
        fieldName: 'serverIp',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '日志路径',
        fieldName: 'path',
        fieldType: 'string',
        inputType: 'input',
      },
    ],
  },
  {
    type: SceneType.Host,
    label: '主机',
    icon: 'bklog-host',
    fields: [
      {
        label: 'IP地址',
        fieldName: 'ip',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '云区域',
        fieldName: 'cloudId',
        fieldType: 'integer',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: '主机ID',
        fieldName: 'bk_host_id',
        fieldType: 'integer',
        inputType: 'input',
      },
      {
        label: '日志路径',
        fieldName: 'path',
        fieldType: 'string',
        inputType: 'input',
      },
    ],
  },
  {
    type: SceneType.PaaS,
    label: 'Paas',
    skipI18n: true,
    icon: 'bklog-paas',
    fields: [
      {
        label: '应用代码',
        fieldName: 'app_code',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
        multiple: true,
      },
      {
        label: '模块名',
        fieldName: 'module_name',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
        multiple: true,
      },
      {
        label: '输出流',
        fieldName: 'stream',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'static',
        staticOptions: [
          { id: 'json', name: 'json' },
          { id: 'stdout', name: 'stdout' },
        ],
      },
      {
        label: '环境',
        fieldName: '__ext.labels.env',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: '进程类型',
        fieldName: '__ext.labels.process_id',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: '日志级别',
        fieldName: 'levelname',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'static',
        staticOptions: [
          { id: 'ERROR', name: 'ERROR' },
          { id: 'WARN', name: 'WARN' },
          { id: 'INFO', name: 'INFO' },
          { id: 'DEBUG', name: 'DEBUG' },
        ],
      },
      {
        label: '函数名',
        fieldName: 'funcName',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '服务名称',
        fieldName: 'otelServiceName',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: 'TraceID',
        skipI18n: true,
        fieldName: 'otelTraceID',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: 'SpanID',
        skipI18n: true,
        fieldName: 'otelSpanID',
        fieldType: 'string',
        inputType: 'input',
      },
    ],
  },
  {
    type: SceneType.Service,
    label: '服务',
    icon: 'bklog-service',
    fields: [
      {
        label: '应用名称',
        fieldName: 'app_name',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
        multiple: true,
      },
      {
        label: '服务名称',
        fieldName: 'resource.service.name',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: 'Trace ID',
        skipI18n: true,
        fieldName: 'trace_id',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: 'Span ID',
        skipI18n: true,
        fieldName: 'span_id',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: 'Span名称',
        fieldName: 'span_name',
        fieldType: 'string',
        inputType: 'input',
      },
    ],
  },
  {
    type: SceneType.Client,
    label: '客户端',
    icon: 'bklog-kehuduan',
    fields: [
      {
        label: '任务ID',
        fieldName: 'task_id',
        fieldType: 'integer',
        inputType: 'input',
      },
      {
        label: '任务名称',
        fieldName: 'task_name',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '用户标识',
        fieldName: 'openid',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '设备厂商',
        fieldName: 'manufacturer',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: '设备型号',
        fieldName: 'model',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '操作系统',
        fieldName: 'os_type',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'static',
        staticOptions: [
          { id: 'android', name: 'android' },
          { id: 'ios', name: 'ios' },
        ],
      },
      {
        label: '系统版本',
        fieldName: 'os_version',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: 'SDK版本',
        fieldName: 'sdk_version',
        fieldType: 'string',
        inputType: 'input',
      },
    ],
  },
  {
    type: SceneType.TRPC,
    label: 'TRPC',
    skipI18n: true,
    icon: 'bklog-trpc',
    fields: [
      {
        label: '服务名',
        fieldName: 'resource.server',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: '目标服务',
        fieldName: 'resource.target',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: '命名空间',
        fieldName: 'resource.namespace',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: '环境',
        fieldName: 'resource.env',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'api',
        searchable: true,
      },
      {
        label: 'Trace ID',
        skipI18n: true,
        fieldName: 'trace_id',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '日志级别',
        fieldName: 'severity_text',
        fieldType: 'string',
        inputType: 'select',
        sourceType: 'static',
        staticOptions: [
          { id: 'info', name: 'info' },
          { id: 'warn', name: 'warn' },
          { id: 'error', name: 'error' },
        ],
      },
      {
        label: '容器名称',
        fieldName: 'resource.containerName',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '实例IP',
        fieldName: 'resource.instance',
        fieldType: 'string',
        inputType: 'input',
      },
      {
        label: '代码位置',
        fieldName: 'attributes.line',
        fieldType: 'string',
        inputType: 'input',
      },
    ],
  },
];

/** 根据场景类型获取配置 */
export const getSceneConfig = (type: SceneType): SceneConfig | undefined => {
  return sceneConfigs.find(scene => scene.type === type);
};

/** 获取指定场景的所有 fieldName */
export const getSceneFieldNames = (sceneType: string): string[] => {
  const config = sceneConfigs.find(s => s.type === sceneType);
  return config ? config.fields.map(f => f.fieldName) : [];
};

/** 获取所有场景的全部 fieldName（去重） */
export const getAllSceneFieldNames = (): string[] => {
  const names = new Set<string>();
  sceneConfigs.forEach(s => s.fields.forEach(f => names.add(f.fieldName)));
  return Array.from(names);
};
