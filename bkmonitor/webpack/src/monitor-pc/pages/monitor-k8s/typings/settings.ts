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
import type { IBookMark, ICurVarItem } from 'monitor-ui/chart-plugins/typings';
import type { VNode } from 'vue';
/** 编辑页签  编辑变量 编辑视图 */
export type SettingType = 'edit-dashboard' | 'edit-tab' | 'edit-variate';
export type ISettingTpl = Record<SettingType, VNode>;

/** 设置组件 */
export declare namespace SettingsWrapType {
  interface IProps {
    active: SettingType;
    bookMarkData: IBookMark[];
    activeTab: string;
    viewType: string;
    sceneId: string;
    title: string;
    initAddSetting?: boolean;
    enableAutoGrouping?: boolean;
  }
  interface IEvents {
    onSaveVar: SettingsVarType.IEvents['onSave'];
    onActiveChange: SettingType;
    onUpdataTabList: void;
    onPanelChange: string;
  }
  /** 设置保存接口config参数 */
  interface ISettingsSaveConfig {
    index?: number; // 排序索引
    mode?: 'auto' | 'custom'; // 平铺 | 自定义
    variables?: ISaveVarItem; // 变量
    order?: any[];
    panels?: any[]; // 图表
    list?: object;
    options?: object;
  }
  /** 变量参数 */
  type ISaveVarItem = Array<any>;
}

/** 页签设置组件 */
export declare namespace SettingsTabType {
  interface IProps {
    canAddTab: boolean;
    activeTab: string;
    bookMarkData: IBookMark[];
    title: string;
    needAutoAdd?: boolean;
  }
  /** 页签信息表单 */
  interface ITabForm {
    id?: string;
    name?: string;
    show_panel_count?: boolean;
    view_order?: string[];
  }
  interface IEvents {
    onSave: ITabForm;
    onDelete: string;
  }
}

/** 变量设置组件 */
export declare namespace SettingsVarType {
  interface IProps {
    bookMarkData: IBookMark[];
    activeTab: string;
    sceneId: string;
    viewType: string;
    title: string;
    needAutoAdd?: boolean;
    getTabDetail: (tabId: string) => void;
  }

  interface IVarChangeData {
    id: string;
    name: string;
    data: ICurVarItem[];
  }
  interface IEvents {
    onSave: IVarChangeData;
    onVarListChange: IVarChangeData;
    onTabChange: string;
  }
}

type TMatchType = 'auto' | 'manual';
/** 视图设置组件 */
export declare namespace SettingsDashboardType {
  interface IProps {
    activeTab: string;
    bookMarkData: IBookMark[];
    title: string;
    enableAutoGrouping?: boolean;
  }
  interface IGroupItem {
    id: string;
    key?: string;
    title: string;
    hidden: boolean;
    match_type?: TMatchType[];
    match_rules: string[];
  }
  interface IPanelGroup {
    id: string;
    title: string;
    panels: IGroupItem[];
    type?: string;
    auto_rules?: string[];
    manual_list?: string[];
  }
  interface IPanelData {
    id: string;
    name: string;
    data: IPanelGroup[];
  }
  interface IEvents {
    onSave: IPanelData;
    onGetSceneView: string;
    onGetTabDetail: string;
  }
}
