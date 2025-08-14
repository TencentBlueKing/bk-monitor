import type { VNode } from 'vue';

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
export type ISettingTpl = Record<SettingType, VNode>;
/** 编辑页签  编辑变量 编辑视图 */
export type SettingType = 'edit-dashboard' | 'edit-tab' | 'edit-variate';

/** 设置组件 */
export declare namespace SettingsWrapType {
  interface IEvents {
    onActiveChange: SettingType;
    onPanelChange: string;
    onSaveVar: SettingsVarType.IEvents['onSave'];
    onUpdataTabList: void;
  }
  interface IProps {
    active: SettingType;
    activeTab: string;
    bookMarkData: IBookMark[];
    enableAutoGrouping?: boolean;
    initAddSetting?: boolean;
    sceneId: string;
    title: string;
    viewType: string;
  }
  /** 变量参数 */
  type ISaveVarItem = Array<any>;
  /** 设置保存接口config参数 */
  interface ISettingsSaveConfig {
    index?: number; // 排序索引
    list?: object;
    mode?: 'auto' | 'custom'; // 平铺 | 自定义
    options?: object;
    order?: any[];
    panels?: any[]; // 图表
    variables?: ISaveVarItem; // 变量
  }
}

/** 页签设置组件 */
export declare namespace SettingsTabType {
  interface IEvents {
    onDelete: string;
    onSave: ITabForm;
  }
  interface IProps {
    activeTab: string;
    bookMarkData: IBookMark[];
    canAddTab: boolean;
    needAutoAdd?: boolean;
    title: string;
  }
  /** 页签信息表单 */
  interface ITabForm {
    id?: string;
    name?: string;
    show_panel_count?: boolean;
    view_order?: string[];
  }
}

/** 变量设置组件 */
export declare namespace SettingsVarType {
  interface IEvents {
    onSave: IVarChangeData;
    onTabChange: string;
    onVarListChange: IVarChangeData;
  }

  interface IProps {
    activeTab: string;
    bookMarkData: IBookMark[];
    needAutoAdd?: boolean;
    sceneId: string;
    title: string;
    viewType: string;
    getTabDetail: (tabId: string) => void;
  }
  interface IVarChangeData {
    data: ICurVarItem[];
    id: string;
    name: string;
  }
}

type TMatchType = 'auto' | 'manual';
/** 视图设置组件 */
export declare namespace SettingsDashboardType {
  interface IEvents {
    onGetSceneView: string;
    onGetTabDetail: string;
    onSave: IPanelData;
  }
  interface IGroupItem {
    hidden: boolean;
    id: string;
    key?: string;
    match_rules: string[];
    match_type?: TMatchType[];
    title: string;
  }
  interface IPanelData {
    data: IPanelGroup[];
    id: string;
    name: string;
  }
  interface IPanelGroup {
    auto_rules?: string[];
    id: string;
    manual_list?: string[];
    panels: IGroupItem[];
    title: string;
    type?: string;
  }
  interface IProps {
    activeTab: string;
    bookMarkData: IBookMark[];
    enableAutoGrouping?: boolean;
    title: string;
  }
}
