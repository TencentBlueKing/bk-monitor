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
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
import { computed, onBeforeMount, reactive, shallowRef } from 'vue';

import { useI18n } from 'vue-i18n';

import type { TableColumnItem } from '../../alarm-center/typings';
import type { CheckboxGroupValue } from 'tdesign-vue-next';

/** localStorage 存储键 */
const INCIDENT_ALERT_TABLE_STORAGE_KEY = '__INCIDENT_ALERT_TABLE_COLUMNS__';

/** 不可隐藏的列（必须显示） */
const LOCKED_FIELDS = ['row-select', 'alert_name', 'bk_biz_name', 'status'];

export function useIncidentAlertColumns() {
  const { t } = useI18n();

  /** 全部列定义 */
  const allColumns = shallowRef<TableColumnItem[]>(getDefaultColumns(t));

  /** 当前显示的列 colKey 列表 */
  const displayColKeys = shallowRef<CheckboxGroupValue>([]);

  /** 记录各列拖拽后的宽度，key 为 colKey，value 为像素宽度 */
  const columnsWidthMap = reactive<Record<string, number>>({});

  /** 必须显示且不可编辑隐藏的列 */
  const lockedFields = computed(() => LOCKED_FIELDS);

  /** 全部可选列字段（用于列设置面板） */
  const allFields = computed(() => [
    { label: '', field: 'row-select' },
    ...allColumns.value.map(col => ({
      label: col.title?.toString() || '',
      field: col.colKey,
    })),
  ]);

  /** 当前显示列的 colKey 列表（考虑 localStorage 缓存和默认值） */
  const displayFields = computed<string[]>({
    get: () => {
      const stored = displayColKeys.value as string[];
      if (stored?.length) return stored;
      return ['row-select', ...allColumns.value.filter(col => col.is_default !== false).map(col => col.colKey)];
    },
    set: (val: string[]) => {
      displayColKeys.value = val;
    },
  });

  /** 最终用于 CommonTable 的列配置（过滤隐藏列 + 合并拖拽列宽） */
  const tableColumns = computed<TableColumnItem[]>(() => {
    const visibleKeys = new Set(displayFields.value);
    const hasRowSelect = visibleKeys.has('row-select');
    const cols = allColumns.value
      .filter(col => visibleKeys.has(col.colKey))
      .map(col => {
        const resizedWidth = columnsWidthMap[col.colKey];
        if (resizedWidth != null && col.resizable !== false) {
          return { ...col, width: resizedWidth };
        }
        return col;
      });
    if (hasRowSelect) {
      return [
        { colKey: 'row-select', type: 'multiple' as const, width: 50, minWidth: 50, fixed: 'left' as const },
        ...cols,
      ];
    }
    return cols;
  });

  /** 列宽拖拽回调：同步到 columnsWidthMap，使所有 Collapse 内表格列宽保持一致 */
  const handleColumnResizeChange = (context: { columnsWidth: Record<string, number> }) => {
    const widths = context?.columnsWidth;
    if (!widths) return;
    for (const [colKey, width] of Object.entries(widths)) {
      columnsWidthMap[colKey] = width;
    }
  };

  /** 列显隐变化回调 */
  const handleDisplayColumnsChange = (checked: CheckboxGroupValue) => {
    // 确保 row-select 始终在选中列表中
    const checkedSet = new Set(checked as string[]);
    if (!checkedSet.has('row-select')) {
      checkedSet.add('row-select');
    }
    const finalChecked = Array.from(checkedSet);
    displayColKeys.value = finalChecked;
    localStorage.setItem(INCIDENT_ALERT_TABLE_STORAGE_KEY, JSON.stringify(finalChecked));
  };

  /** 从 localStorage 恢复列显隐设置 */
  onBeforeMount(() => {
    const cache = localStorage.getItem(INCIDENT_ALERT_TABLE_STORAGE_KEY);
    if (cache) {
      try {
        displayColKeys.value = JSON.parse(cache) || [];
      } catch (e) {
        console.log(e);
      }
    }
  });

  return {
    allColumns,
    tableColumns,
    allFields,
    displayFields,
    lockedFields,
    columnsWidthMap,
    handleColumnResizeChange,
    handleDisplayColumnsChange,
  };
}

/**
 * 故障告警表格默认列定义
 * colKey 与 AlertService.ALERT_TABLE_COLUMNS 保持一致
 * is_default / is_locked 与告警中心告警模块对齐
 */
function getDefaultColumns(t: (key: string) => string): TableColumnItem[] {
  return [
    {
      colKey: 'alert_name',
      title: t('告警名称'),
      width: 180,
      minWidth: 60,
      fixed: 'left',
      is_default: true,
      is_locked: true,
    },
    {
      colKey: 'tags',
      title: t('维度'),
      width: 350,
      minWidth: 60,
      is_default: true,
      is_locked: false,
    },
    {
      colKey: 'begin_time',
      title: t('开始时间'),
      width: 150,
      minWidth: 60,
      is_default: true,
      is_locked: false,
      sorter: true,
    },
    {
      colKey: 'end_time',
      title: t('结束时间'),
      width: 150,
      minWidth: 60,
      is_default: true,
      is_locked: false,
      sorter: true,
    },
    {
      colKey: 'create_time',
      title: t('创建时间'),
      width: 150,
      minWidth: 60,
      is_default: false,
      is_locked: false,
      sorter: true,
    },
    {
      colKey: 'description',
      title: t('告警内容'),
      width: 300,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'target_key',
      title: t('监控目标'),
      width: 110,
      minWidth: 60,
      is_default: true,
      is_locked: false,
    },
    {
      colKey: 'plugin_display_name',
      title: t('告警来源'),
      width: 110,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'category_display',
      title: t('分类'),
      width: 160,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'metric',
      title: t('告警指标'),
      width: 240,
      minWidth: 60,
      is_default: false,
      is_locked: false,
      // sorter: true,
    },
    {
      colKey: 'event_count',
      title: t('关联事件'),
      width: 140,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'latest_time',
      title: t('最新事件时间'),
      width: 150,
      minWidth: 60,
      is_default: false,
      is_locked: false,
      sorter: true,
    },
    {
      colKey: 'first_anomaly_time',
      title: t('首次异常时间'),
      width: 150,
      minWidth: 60,
      is_default: false,
      is_locked: false,
      sorter: true,
    },
    {
      colKey: 'duration',
      title: t('持续时间'),
      width: 120,
      minWidth: 60,
      is_default: false,
      is_locked: false,
      sorter: true,
    },
    {
      colKey: 'extend_info',
      title: t('关联信息'),
      width: 250,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'appointee',
      title: t('负责人'),
      width: 200,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'assignee',
      title: t('通知人'),
      width: 200,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'follower',
      title: t('关注人'),
      width: 200,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'strategy_name',
      title: t('策略名称'),
      width: 160,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'labels',
      title: t('策略标签'),
      width: 240,
      minWidth: 60,
      is_default: false,
      is_locked: false,
    },
    {
      colKey: 'bk_biz_name',
      title: t('空间名'),
      width: 110,
      minWidth: 60,
      fixed: 'right',
      is_default: true,
      is_locked: true,
    },
    {
      colKey: 'stage_display',
      title: t('处理阶段'),
      width: 80,
      minWidth: 60,
      fixed: 'right',
      is_default: true,
      is_locked: false,
    },
    {
      colKey: 'status',
      title: t('状态'),
      width: 80,
      minWidth: 60,
      fixed: 'right',
      is_default: true,
      is_locked: true,
      sorter: true,
    },
  ];
}
