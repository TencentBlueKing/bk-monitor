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
import { releaseCollectorPlugin } from 'monitor-api/modules/model';
import { saveMetric } from 'monitor-api/modules/plugin';
import { deepClone, random } from 'monitor-common/utils';

import { matchRuleFn } from '../../../custom-escalation/metric-manage/utils';

import {
  ALL_LABEL,
  FRONT_END_FIELD_KEYS,
  GROUP_DEFAULT_NAME,
  type IBatchField,
  type IFlatField,
  type IPluginField,
  type IPluginGroup,
  type IPluginMeta,
  type MonitorType,
} from './types';

/** 生成字段唯一键 */
export function fieldUid(tableName: string, monitorType: string, name: string) {
  return `${tableName}::${monitorType}::${name}`;
}

/** 创建默认分组 */
export function createDefaultGroup(desc = '默认分组'): IPluginGroup {
  return {
    table_name: GROUP_DEFAULT_NAME,
    table_desc: desc,
    rule_list: [],
    fields: [],
  };
}

/** 保证存在默认分组 */
export function ensureDefaultGroup(data: IPluginGroup[] = [], desc = '默认分组'): IPluginGroup[] {
  const list = Array.isArray(data) ? deepClone(data) : [];
  if (!list.some(item => item.table_name === GROUP_DEFAULT_NAME)) {
    list.unshift(createDefaultGroup(desc));
  }
  return list.map(group => ({
    ...group,
    rule_list: group.rule_list || [],
    fields: (group.fields || []).map(item => normalizeField(item)),
  }));
}

/** 规范化单条字段（diff 指标展示、补齐前端态） */
export function normalizeField(item: IPluginField): IPluginField {
  const field = {
    ...item,
    selection: false,
    id: item.id || random(10),
    uid: item.uid || fieldUid('', item.monitor_type, item.name),
  };
  if (field.monitor_type === 'metric' && field.type === 'double' && field.is_diff_metric) {
    field.type = 'diff';
  }
  return field;
}

/** 扁平化所有字段，附带所属分组 */
export function flattenFields(groups: IPluginGroup[]): IFlatField[] {
  return groups.flatMap(group =>
    (group.fields || [])
      .filter(item => item.name)
      .map(item => ({
        ...item,
        table_name: group.table_name,
        table_desc: group.table_desc,
        uid: fieldUid(group.table_name, item.monitor_type, item.name),
      }))
  );
}

/** 按分组与类型过滤字段 */
export function filterFieldsByGroup(
  fields: IFlatField[],
  groupName: string,
  monitorType: MonitorType
): IFlatField[] {
  return fields.filter(item => {
    if (item.monitor_type !== monitorType) {
      return false;
    }
    if (groupName === ALL_LABEL) {
      return true;
    }
    return item.table_name === groupName;
  });
}

/** 模糊匹配 */
export function fuzzyMatch(str: string, pattern: string) {
  return String(str || '')
    .toLowerCase()
    .includes(String(pattern || '').toLowerCase());
}

/** 统计分组指标数 */
export function getMetricCount(group: IPluginGroup) {
  return (group.fields || []).filter(item => item.monitor_type === 'metric' && item.name).length;
}

/** 检查维度是否被超过 num 个指标关联 */
export function checkDimensionRelevance(dimension: IPluginField, fields: IPluginField[], num = 1) {
  return fields.filter(metric => metric.tag_list?.some(d => d.field_name === dimension.name)).length > num;
}

/**
 * 将勾选的指标（及关联维度）移动到目标分组
 * 逻辑对齐设置指标&维度页 handleMoveGroup
 */
export function moveCheckedFields(groups: IPluginGroup[], targetName: string): IPluginGroup[] {
  const tableData = deepClone(groups) as IPluginGroup[];
  let targetGroup: IPluginField[] = [];
  const result: IPluginField[] = [];

  for (const group of tableData) {
    if (group.table_name !== targetName) {
      const delList = new Set<string>();
      for (const metric of group.fields) {
        if (metric.selection && metric.monitor_type === 'metric') {
          delList.add(metric.id || metric.name);
          metric.selection = false;
          result.push(deepClone(metric));
          for (const dimension of metric.tag_list || []) {
            const item = group.fields.find(field => field.name === dimension.field_name);
            if (!item) continue;
            item.selection = false;
            result.push(deepClone(item));
            if (!checkDimensionRelevance(item, group.fields, 0)) {
              delList.add(item.id || item.name);
            }
          }
        }
      }
      group.fields = group.fields.filter(item => !delList.has(item.id || item.name));
    } else {
      targetGroup = group.fields;
      for (const item of targetGroup) {
        item.selection = false;
      }
    }
  }

  for (const item of result) {
    const index = targetGroup.findIndex(row => row.name === item.name && row.monitor_type === item.monitor_type);
    if (index > -1) {
      targetGroup.splice(index, 1, item);
    } else {
      targetGroup.push(item);
    }
  }
  return tableData;
}

/** 把单条字段移动到目标分组 */
export function moveFieldToGroup(groups: IPluginGroup[], field: IFlatField, targetName: string): IPluginGroup[] {
  const tableData = deepClone(groups) as IPluginGroup[];
  for (const group of tableData) {
    for (const item of group.fields) {
      item.selection =
        item.name === field.name && item.monitor_type === field.monitor_type && group.table_name === field.table_name;
    }
  }
  return moveCheckedFields(tableData, targetName);
}

/**
 * 分组规则变化后，按规则把默认分组/当前分组的指标互移
 * @param evictUnmatched 为 false 时只吸入匹配指标，不把当前分类已有指标挪走（编辑分类时使用）
 */
export function applyGroupRules(groups: IPluginGroup[], groupName: string, evictUnmatched = true): IPluginGroup[] {
  const tableData = deepClone(groups) as IPluginGroup[];
  const target = tableData.find(item => item.table_name === groupName);
  const defaultGroup = tableData.find(item => item.table_name === GROUP_DEFAULT_NAME);
  if (!target || !defaultGroup) {
    return tableData;
  }

  for (const field of defaultGroup.fields) {
    if (field.monitor_type === 'metric' && target.rule_list.some(rule => matchRuleFn(field.name, rule))) {
      field.selection = true;
    }
  }
  const afterMoveIn = moveCheckedFields(tableData, groupName);
  if (!evictUnmatched) {
    return afterMoveIn;
  }
  const nextTarget = afterMoveIn.find(item => item.table_name === groupName);
  for (const field of nextTarget?.fields || []) {
    if (field.monitor_type === 'metric' && !nextTarget.rule_list.some(rule => matchRuleFn(field.name, rule))) {
      field.selection = true;
    }
  }
  return moveCheckedFields(afterMoveIn, GROUP_DEFAULT_NAME);
}

/** 删除分组，字段并入默认分组 */
export function deleteGroup(groups: IPluginGroup[], groupName: string): IPluginGroup[] {
  const tableData = deepClone(groups) as IPluginGroup[];
  const target = tableData.find(item => item.table_name === groupName);
  const defaultGroup = tableData.find(item => item.table_name === GROUP_DEFAULT_NAME);
  if (!target || !defaultGroup || groupName === GROUP_DEFAULT_NAME) {
    return tableData.filter(item => item.table_name !== groupName);
  }
  for (const field of target.fields) {
    const index = defaultGroup.fields.findIndex(
      row => row.name === field.name && row.monitor_type === field.monitor_type
    );
    if (index > -1) {
      defaultGroup.fields.splice(index, 1, field);
    } else {
      defaultGroup.fields.push(field);
    }
  }
  return tableData.filter(item => item.table_name !== groupName);
}

/** 创建批量编辑空行 */
export function createEmptyField(mode: MonitorType, tableName: string, tableDesc: string): IBatchField {
  const field = normalizeField({
    monitor_type: mode,
    name: '',
    description: '',
    source_name: '',
    is_active: true,
    is_diff_metric: false,
    type: mode === 'metric' ? 'double' : 'string',
    unit: 'none',
    dimensions: mode === 'metric' ? [] : undefined,
    tag_list: mode === 'metric' ? [] : undefined,
    value: { linux: null, windows: null, aix: null },
  });
  return {
    ...field,
    table_name: tableName,
    table_desc: tableDesc,
    uid: fieldUid(tableName, mode, ''),
    isNew: true,
    error: '',
    selection: false,
  };
}

function findFieldByUid(groups: IPluginGroup[], uid: string) {
  for (const group of groups) {
    const field = (group.fields || []).find(
      item => fieldUid(group.table_name, item.monitor_type, item.name) === uid
    );
    if (field) {
      return { field, group };
    }
  }
  return null;
}

function stripBatchMeta(field: IBatchField): IPluginField {
  const next = { ...field } as IPluginField & Partial<IBatchField>;
  for (const key of ['table_name', 'table_desc', 'originUid', 'isNew', 'error', ...FRONT_END_FIELD_KEYS]) {
    delete next[key];
  }
  return next;
}

function moveDimensionToGroup(groups: IPluginGroup[], field: IPluginField, fromName: string, targetName: string) {
  const source = groups.find(item => item.table_name === fromName);
  const target = groups.find(item => item.table_name === targetName);
  if (!source || !target) return;
  source.fields = source.fields.filter(item => item !== field);
  const index = target.fields.findIndex(item => item.name === field.name && item.monitor_type === field.monitor_type);
  if (index > -1) {
    target.fields.splice(index, 1, field);
  } else {
    target.fields.push(field);
  }
}

/** 把批量编辑结果写回分组 */
export function applyBatchFieldChanges(
  groups: IPluginGroup[],
  rows: IBatchField[],
  deletedUids: string[],
  mode: MonitorType
): IPluginGroup[] {
  let next = deepClone(groups) as IPluginGroup[];

  for (const uid of deletedUids) {
    const found = findFieldByUid(next, uid);
    if (!found) continue;
    const { field, group } = found;
    group.fields = group.fields.filter(item => item !== field);
    if (mode === 'dimension') {
      for (const item of next) {
        for (const metric of item.fields) {
          if (metric.monitor_type === 'metric' && metric.tag_list?.length) {
            metric.tag_list = metric.tag_list.filter(dimension => dimension.field_name !== field.name);
          }
        }
      }
    }
  }

  const metricMoves: Record<string, string[]> = {};
  for (const row of rows) {
    if (row.isNew || !row.originUid) {
      if (!row.name?.trim()) continue;
      const target = next.find(item => item.table_name === row.table_name) || next[0];
      if (!target) continue;
      target.fields.push(
        normalizeField({
          ...stripBatchMeta(row),
          name: row.name.trim(),
          description: row.description || '',
          monitor_type: mode,
          is_active: row.is_active !== false,
          type: row.type,
          unit: row.unit || 'none',
        })
      );
      continue;
    }

    const originUid = row.originUid || row.uid;
    const found = findFieldByUid(next, originUid);
    if (!found) continue;
    const { field, group } = found;
    field.description = row.description || '';
    field.is_active = row.is_active !== false;
    if (mode === 'metric') {
      field.type = row.type;
      field.unit = row.unit || 'none';
      field.is_diff_metric = row.type === 'diff';
    }
    if (row.table_name && row.table_name !== group.table_name) {
      if (mode === 'metric') {
        if (!metricMoves[row.table_name]) {
          metricMoves[row.table_name] = [];
        }
        metricMoves[row.table_name].push(originUid);
      } else {
        moveDimensionToGroup(next, field, group.table_name, row.table_name);
      }
    }
  }

  for (const [targetName, uids] of Object.entries(metricMoves)) {
    for (const group of next) {
      for (const field of group.fields) {
        const uid = fieldUid(group.table_name, field.monitor_type, field.name);
        field.selection = uids.includes(uid) && field.monitor_type === 'metric';
      }
    }
    next = moveCheckedFields(next, targetName);
  }

  return next;
}

/** 构建 saveMetric 入参，对齐设置指标&维度页 */
export function buildSaveMetricParams(pluginMeta: IPluginMeta, groups: IPluginGroup[]) {
  const cacheData = deepClone(groups) as IPluginGroup[];
  for (const group of cacheData) {
    group.fields = group.fields.filter(item => item.name);
  }
  // 保留全部分类（含新建空分组），与已有指标一并提交，避免新增分类被过滤后丢失
  const tableData = cacheData.filter(group => group.table_name);

  return {
    plugin_id: pluginMeta.plugin_id,
    plugin_type: pluginMeta.plugin_type,
    config_version: pluginMeta.config_version,
    info_version: pluginMeta.info_version,
    enable_field_blacklist: !!pluginMeta.enable_field_blacklist,
    need_upgrade: true,
    metric_json: tableData.map(item => ({
      table_name: item.table_name,
      table_desc: item.table_name === GROUP_DEFAULT_NAME ? '默认分组' : item.table_desc || item.table_name,
      rule_list: item.rule_list || [],
      fields: item.fields.map(set => {
        const tmpSet = { ...set };
        if (set.monitor_type === 'metric' && set.type === 'diff') {
          tmpSet.type = 'double';
          tmpSet.is_diff_metric = true;
        }
        for (const key of FRONT_END_FIELD_KEYS) {
          delete tmpSet[key];
        }
        tmpSet.is_manual =
          !item.rule_list.some(rule => matchRuleFn(set.name, rule)) && item.table_name !== GROUP_DEFAULT_NAME;
        return tmpSet;
      }),
    })),
  };
}

/** 调用 saveMetric，必要时 release */
export async function savePluginMetricJson(pluginMeta: IPluginMeta, groups: IPluginGroup[]) {
  const params = buildSaveMetricParams(pluginMeta, groups);
  const data = await saveMetric(params, { needMessage: false });
  if (data?.token) {
    await releaseCollectorPlugin(pluginMeta.plugin_id, data);
  }
  return data;
}

/** 插件类型对应的指标类型选项 */
export function getMetricTypeList(pluginType: string) {
  const list = [
    { id: 'double', name: 'double' },
    { id: 'int', name: 'int' },
  ];
  if (['Script', 'JMX', 'Exporter', 'Pushgateway'].includes(pluginType)) {
    list.push({ id: 'diff', name: 'diff' });
  }
  return list;
}

/** 导出用的精简 metric_json */
export function getExportMetricJson(groups: IPluginGroup[]) {
  return groups
    .filter(item => item.table_name)
    .map(item => ({
      table_name: item.table_name,
      table_desc: item.table_desc,
      rule_list: item.rule_list || [],
      fields: (item.fields || [])
        .filter(field => field.name)
        .map(({ description, monitor_type, is_diff_metric, name, type, unit, is_active, dimensions = [], tag_list = [] }) => {
          if (monitor_type === 'metric') {
            return {
              description,
              is_active,
              is_diff_metric,
              monitor_type,
              name,
              type,
              unit,
              dimensions,
              tag_list,
            };
          }
          return {
            description,
            monitor_type,
            name,
            type,
            unit,
            is_active,
          };
        }),
    }));
}
