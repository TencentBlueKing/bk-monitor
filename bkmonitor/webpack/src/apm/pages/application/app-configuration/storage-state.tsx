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

import { indicesInfo, metaConfigInfo, storageFieldInfo, storageInfo } from 'monitor-api/modules/apm_meta';

import Log from './storeInfo/log';
import Metric from './storeInfo/metric';
import Trace from './storeInfo/trace';
import TabList from './tabList';
import { ETelemetryDataType } from './type';

import type { ISetupData } from '../app-add/app-add';
import type { IAppInfo, IClusterItem, IFieldFilterItem, IFieldItem, IndicesItem } from './type';

import './storage-state.scss';
interface IStorageStateProps {
  appInfo: IAppInfo;
  clusterList: IClusterItem[];
}

@Component
export default class StorageState extends tsc<IStorageStateProps> {
  @PropSync('data', { type: Object, required: true }) appInfo: IAppInfo;
  @Prop({ type: Array, required: true }) clusterList: any[];

  /** 选择的tab*/
  activeTab = ETelemetryDataType.metric;
  /* 存储信息 */
  storageInfo = {
    [ETelemetryDataType.metric]: [],
    [ETelemetryDataType.log]: null,
    [ETelemetryDataType.tracing]: null,
    [ETelemetryDataType.profiling]: [],
  };
  storageLoading = false;
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

  @Emit('change')
  handleBaseInfoChange() {
    return true;
  }

  created() {
    for (const tab of this.tabList) {
      if (tab.status !== 'disabled') {
        this.activeTab = tab.name;
        break;
      }
    }
    this.getStorageInfo();
  }

  get tabList() {
    return [
      {
        name: ETelemetryDataType.metric,
        label: window.i18n.tc('指标'),
        status: this.appInfo.metric_data_status,
      },
      {
        name: ETelemetryDataType.log,
        label: window.i18n.tc('日志'),
        status: this.appInfo.log_data_status,
      },
      {
        name: ETelemetryDataType.tracing,
        label: window.i18n.tc('调用链'),
        status: this.appInfo.trace_data_status,
      },
      {
        name: ETelemetryDataType.profiling,
        label: window.i18n.tc('性能分析'),
        status: this.appInfo.profiling_data_status,
      },
    ];
  }

  /**
   * 获取存储信息列表
   */
  async getStorageInfo() {
    this.storageLoading = true;
    const data = await storageInfo(this.appInfo.application_id, {
      telemetry_data_type: this.activeTab,
    }).catch(() => null);
    this.storageInfo[this.activeTab] = data;
    this.storageLoading = false;
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
    this.indicesList = await indicesInfo(this.appInfo.application_id, {
      telemetry_data_type: this.activeTab,
    }).catch(() => []);
    this.indicesLoading = false;
  }
  /**
   * @desc 获取字段信息
   */
  async getFieldList() {
    this.fieldLoading = true;
    this.fieldList = await storageFieldInfo(this.appInfo.application_id, {
      telemetry_data_type: this.activeTab,
    }).catch(() => []);
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
    for (const item of list) {
      if (!setList.has(item.field_type)) {
        setList.add(item.field_type);
        filterList.push({
          text: item.field_type,
          value: item.field_type,
        });
      }
    }
    return filterList;
  }

  /** tab切换时 */
  handleChangeActiveTab(active: ETelemetryDataType) {
    this.activeTab = active;
    this.getStorageInfo();
    switch (active) {
      case ETelemetryDataType.log:
        this.getIndicesList();
        break;
      case ETelemetryDataType.tracing:
        this.getMetaConfigInfo();
        this.getIndicesList();
        this.getFieldList();
        break;
      default:
        break;
    }
  }

  /** 获取选择的tab组件 */
  getActiveComponent() {
    switch (this.activeTab) {
      case ETelemetryDataType.metric:
      case ETelemetryDataType.profiling:
        return (
          <Metric
            appInfo={this.appInfo}
            data={this.storageInfo[this.activeTab] || []}
            dataLoading={this.storageLoading}
          />
        );
      case ETelemetryDataType.log:
        return (
          <Log
            appInfo={this.appInfo}
            indicesList={this.indicesList}
            indicesLoading={this.indicesLoading}
            storageInfo={this.storageInfo[this.activeTab]}
            telemetryDataType={this.activeTab}
          />
        );
      case ETelemetryDataType.tracing:
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
            storageInfo={this.storageInfo[this.activeTab]}
            telemetryDataType={this.activeTab}
            onChange={this.handleBaseInfoChange}
          />
        );
    }
  }

  render() {
    return (
      <div class='conf-content storage-state-wrap'>
        <div class='storage-tab-wrap'>
          <TabList
            activeTab={this.activeTab}
            tabList={this.tabList}
            onChange={this.handleChangeActiveTab}
          />
        </div>
        <div class='storage-content'>{this.getActiveComponent()}</div>
      </div>
    );
  }
}
