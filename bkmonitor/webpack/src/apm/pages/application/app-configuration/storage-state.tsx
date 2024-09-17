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

import { Component, Emit, Prop, PropSync } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { indicesInfo, metaConfigInfo, storageFieldInfo } from 'monitor-api/modules/apm_meta';

import Log from './storeInfo/log';
import Metric from './storeInfo/metric';
import Trace from './storeInfo/trace';
import TabList from './tabList';

import type { ISetupData } from '../app-add/app-add';
import type { IAppInfo, IClusterItem, IFieldFilterItem, IFieldItem, IndicesItem, IStoreItem } from './type';

import './storage-state.scss';
interface IStorageStateProps {
  appInfo: IAppInfo;
  clusterList: IClusterItem[];
}

const TAB_LIST = [
  {
    name: 'metric',
    label: '指标',
  },
  {
    name: 'log',
    label: '日志',
  },

  {
    name: 'trace',
    label: '调用链',
  },
  {
    name: 'performance',
    label: '性能分析',
  },
];

@Component
export default class StorageState extends tsc<IStorageStateProps> {
  @PropSync('data', { type: Object, required: true }) appInfo: IAppInfo;
  @Prop({ type: Array, required: true }) clusterList: any[];

  /** 选择的tab*/
  activeTab = 'metric';
  /** 存储信息列表 */
  storeList: IStoreItem[] = [];
  storeListLoading = false;
  indicesLoading = false;
  fieldLoading = false;
  indicesList: IndicesItem[] = []; // 物理索引
  fieldList: IFieldItem[] = []; // 字段信息
  fieldFilterList: IFieldFilterItem[] = []; // 字段信息过滤列表

  /** 集群信息 索引名 过期时间 副本数 */
  setupData: ISetupData = {
    index_prefix_name: '',
    es_retention_days: {
      default: 0,
      default_es_max: 0,
      private_es_max: 0,
    },
    es_number_of_replicas: {
      default: 0,
      default_es_max: 0,
      private_es_max: 0,
    },
  };

  /** 获取选择的tab组件 */
  getActiveComponent() {
    switch (this.activeTab) {
      case 'metric':
        return (
          <Metric
            appInfo={this.appInfo}
            data={this.storeList}
            dataLoading={this.storeListLoading}
          />
        );
      case 'log':
        return (
          <Log
            appInfo={this.appInfo}
            indicesList={this.indicesList}
            indicesLoading={this.indicesLoading}
          />
        );
      case 'performance':
      case 'trace':
        return (
          <Trace
            appInfo={this.appInfo}
            clusterList={this.clusterList}
            fieldFilterList={this.fieldFilterList}
            fieldList={this.fieldList}
            fieldLoading={this.fieldLoading}
            indicesList={this.indicesList}
            indicesLoading={this.indicesLoading}
            setupData={this.setupData}
            onChange={this.handleBaseInfoChange}
          />
        );
    }
  }

  @Emit('change')
  handleBaseInfoChange() {
    return true;
  }

  created() {
    this.getStoreList();
  }

  /**
   * 获取存储信息列表
   */
  async getStoreList() {
    this.storeListLoading = true;
    const data: IStoreItem[] = await new Promise(resolve => {
      resolve([]);
    });
    this.storeList = data;
    this.storeListLoading = false;
  }
  /**
   * @desc 获取过期时间最大值
   */
  async getMetaConfigInfo() {
    const data = await metaConfigInfo().catch(() => null);
    this.setupData = data.setup;
  }

  /**
   * @desc 获取物理索引
   */
  async getIndicesList() {
    this.indicesLoading = true;
    this.indicesList = await indicesInfo(this.appInfo.application_id).catch(() => []);
    this.indicesLoading = false;
  }
  /**
   * @desc 获取字段信息
   */
  async getFieldList() {
    this.fieldLoading = true;
    this.fieldList = await storageFieldInfo(this.appInfo.application_id).catch(() => []);
    this.fieldFilterList = this.getFieldFilterList(this.fieldList);
    this.fieldLoading = false;
  }
  /**
   * @desc: 获取字段过滤列表
   * @param { Array } list 被处理的列表
   * @returns { Array } 返回值
   */
  getFieldFilterList(list) {
    const setList = new Set();
    const filterList = [];
    list.forEach(item => {
      if (!setList.has(item.field_type)) {
        setList.add(item.field_type);
        filterList.push({
          text: item.field_type,
          value: item.field_type,
        });
      }
    });
    return filterList;
  }

  /** tab切换时 */
  handleChangeActiveTab(active: string) {
    this.activeTab = active;
    switch (active) {
      case 'log':
        this.getIndicesList();
        break;
      case 'metric':
        this.getStoreList();
        break;
      case 'trace':
      case 'performance':
        this.getMetaConfigInfo();
        this.getIndicesList();
        this.getFieldList();
        break;
      default: {
      }
    }
  }
  render() {
    return (
      <div class='conf-content storage-state-wrap'>
        <div class='storage-tab-wrap'>
          <TabList
            activeTab={this.activeTab}
            tabList={TAB_LIST}
            onChange={this.handleChangeActiveTab}
          />
        </div>
        <div class='storage-content'>{this.getActiveComponent()}</div>
      </div>
    );
  }
}
