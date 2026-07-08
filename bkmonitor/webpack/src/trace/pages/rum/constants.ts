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

/** 应用配置 tab 枚举 */
export const RUM_APP_CONFIG_TAB_ENUM = {
  BASIC_CONFIG: 'basicConfig',
  STORAGE_STATUS: 'storageStatus',
  DATA_STATUS: 'dataStatus',
} as const;

/** 应用配置 tab 配置 */
export const RUM_APP_CONFIG_TAB_MAP = [
  { id: RUM_APP_CONFIG_TAB_ENUM.BASIC_CONFIG, name: window.i18n.t('基本配置') },
  { id: RUM_APP_CONFIG_TAB_ENUM.STORAGE_STATUS, name: window.i18n.t('存储状态') },
  { id: RUM_APP_CONFIG_TAB_ENUM.DATA_STATUS, name: window.i18n.t('数据状态') },
];

// ===================== 数据状态 — 枚举常量 =====================

/** 告警级别枚举：致命/预警/无告警/无数据 */
export const AlertLevelEnum = {
  /** 致命告警 */
  FATAL: 'fatal',
  /** 预警 */
  WARNING: 'warning',
  /** 无告警 */
  NORMAL: 'normal',
  /** 无数据 */
  NO_DATA: 'no_data',
} as const;

// ===================== 数据状态 — 静态映射 =====================

/** 告警色块颜色映射表 — 默认态 */
export const ALERT_LEVEL_COLOR_MAP: Record<string, string> = {
  [AlertLevelEnum.FATAL]: '#FF5656',
  [AlertLevelEnum.WARNING]: '#FFB848',
  [AlertLevelEnum.NORMAL]: '#2DCB56',
  [AlertLevelEnum.NO_DATA]: '#EAEBF0',
};

/** 告警色块颜色映射表 — 悬停态 */
export const ALERT_LEVEL_HOVER_COLOR_MAP: Record<string, string> = {
  [AlertLevelEnum.FATAL]: '#F8B4B4',
  [AlertLevelEnum.WARNING]: '#FFD695',
  [AlertLevelEnum.NORMAL]: '#81E09A',
  [AlertLevelEnum.NO_DATA]: '#EAEBF0',
};

// ===================== 数据状态 — 尺寸常量 =====================

/** 色块宽度 (px) */
export const ALERT_BAR_WIDTH = 6;
/** 色块间距 (px) */
export const ALERT_BAR_GAP = 2;
/** 色块默认高度 (px) */
export const ALERT_BAR_HEIGHT = 14;
/** 色块激活高度 (px) */
export const ALERT_BAR_ACTIVE_HEIGHT = 20;

// ===================== 数据采样 — 静态列配置 =====================

/** 数据采样表格静态列配置（title / width 等静态属性，cellRenderer 由 useSamplingColumnsRenderer 注入） */
export const SAMPLING_TABLE_COLUMNS = [
  {
    colKey: 'index',
    title: window.i18n.t('序号'),
    width: 80,
  },
  {
    colKey: 'raw_log',
    title: window.i18n.t('原始数据'),
  },
  {
    colKey: 'sampling_time',
    title: window.i18n.t('采样时间'),
    width: 200,
  },
  {
    colKey: 'operations',
    title: window.i18n.t('操作'),
    width: 180,
  },
] as const;
