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
import type { IOption } from '.';
import type { IFavList } from '../components/panel-header/favorites-list/favorites-list';
import type { TranslateResult } from 'vue-i18n';

/** 面板工具的类型 */
export declare namespace PanelToolsType {
  /** 对比数据类型 */
  type Compare = CompareOneOf<PanelToolsType.CompareId>;
  /** 不对比 | 时间对比 | 目标对比 | 指标对比 */
  type CompareId = 'metric' | 'none' | 'target' | 'time';
  interface CompareOneOf<T extends CompareId> {
    type: CompareId;
    value: CompareValue<T>;
  }
  type CompareValue<T extends CompareId> = ICompareValueType[T];
  /** 对比方法可选项 */
  interface ICompareListItem {
    id: CompareId;
    name: string | TranslateResult;
  }
  interface ICompareValueType {
    metric: string[];
    none: boolean;
    target: string[];
    time: string[];
  }
  interface IEvents {
    onCompareChange?: Compare;
    onLayoutChange?: LayoutId;
    onSplitChange?: boolean;
  }
  interface IProps {
    compareListEnable?: CompareId[];
    disabledLayout?: boolean;
    layoutActive?: number;
    needLayout?: boolean;
    needSplit?: boolean;
    split?: boolean;
  }
  /** 图表布局 */
  type LayoutId = 0 | 1 | 2;
}

export interface OptionsItem {
  id: string;
  name: string | TranslateResult;
}

export const COMPARE_KEY = ['none', 'time', 'target', 'metric'];

export const COMPARE_LIST: PanelToolsType.ICompareListItem[] = [
  {
    id: 'none',
    name: window.i18n.t('不对比'),
  },
  {
    id: 'target',
    name: window.i18n.t('目标对比'),
  },
  {
    id: 'time',
    name: window.i18n.t('时间对比'),
  },
  {
    id: 'metric',
    name: window.i18n.t('指标对比'),
  },
];

export const PANEL_LAYOUT = [
  {
    id: 'icon-mc-one-column',
    name: window.i18n.t('一列'),
  },
  {
    id: 'icon-mc-two-column',
    name: window.i18n.t('两列'),
  },
  {
    id: 'icon-mc-three-column',
    name: window.i18n.t('三列'),
  },
];
export const PANEL_LAYOUT_LIST = [
  {
    id: 1,
    name: window.i18n.t('一列'),
  },
  {
    id: 2,
    name: window.i18n.t('两列'),
  },
  {
    id: 3,
    name: window.i18n.t('三列'),
  },
  {
    id: 4,
    name: window.i18n.t('四列'),
  },
  {
    id: 5,
    name: window.i18n.t('五列'),
  },
];
export const COMPARE_TIME_OPTIONS = [
  {
    id: '1h',
    name: window.i18n.t('1 小时前'),
  },
  {
    id: '1d',
    name: window.i18n.t('昨天'),
  },
  {
    id: '1w',
    name: window.i18n.t('上周'),
  },
  {
    id: '1M',
    name: window.i18n.t('一月前'),
  },
];

export const TIME_RANGE_DEFAULT_LIST = [
  {
    name: window.i18n.t('1 小时'),
    value: 1 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('1 天'),
    value: 24 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('7 天'),
    value: 168 * 60 * 60 * 1000,
  },
  {
    name: window.i18n.t('1 个月'),
    value: 720 * 60 * 60 * 1000,
  },
];
export const METHOD_LIST: IOption[] = [
  {
    id: 'AVG',
    name: 'AVG',
  },
  {
    id: 'SUM',
    name: 'SUM',
  },
  {
    id: 'MIN',
    name: 'MIN',
  },
  {
    id: 'MAX',
    name: 'MAX',
  },
];
export const REFRESH_DEFAULT_LIST = [
  {
    name: 'off',
    id: -1,
  },
  {
    name: '1m',
    id: 60 * 1000,
  },
  {
    name: '5m',
    id: 5 * 60 * 1000,
  },
  {
    name: '15m',
    id: 15 * 60 * 1000,
  },
  {
    name: '30m',
    id: 30 * 60 * 1000,
  },
  {
    name: '1h',
    id: 60 * 60 * 1000,
  },
  {
    name: '2h',
    id: 60 * 2 * 60 * 1000,
  },
  {
    name: '1d',
    id: 60 * 24 * 60 * 1000,
  },
];

export declare namespace PanelHeaderType {
  interface IEvents {
    onDeleteFav: number;
    onDownSampleChange: string;
    onImmediateRefresh: void;
    onRefreshIntervalChange: number;
    onSelectFav: any;
    onTimeRangeChange: TimeRangeValue;
    onTimezoneChange: string;
  }
  interface IProps {
    downSampleRange?: string;
    eventSelectTimeRange?: TimeRangeValue;
    favCheckedValue?: IFavList.favList;
    favoritesList?: IFavList.favList[];
    refreshInterval: number;
    refreshList?: OptionsItem[];
    showDownSample: boolean;
    timeRange: TimeRangeValue;
    timeRangeList?: OptionsItem[];
    timezone: string;
  }
  type TimeRangeValue = number | string[];
}
