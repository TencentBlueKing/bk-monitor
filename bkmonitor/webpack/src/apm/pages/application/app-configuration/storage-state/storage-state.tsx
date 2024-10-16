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

import {
  indicesInfo,
  metaConfigInfo,
  storageFieldInfo,
  storageInfo,
  storageStatus,
} from 'monitor-api/modules/apm_meta';

import PanelItem from '../../../../components/panel-item/panel-item';
import StorageInfoSkeleton from '../skeleton/storage-info-skeleton';
import TabList from '../tabList';
import { ETelemetryDataType } from '../type';
import Log from './storage-state-log';
import Metric from './storage-state-metric';
import Trace from './storage-state-trace';

import type { IAppInfo, IClusterItem, IFieldFilterItem, IFieldItem, IndicesItem } from '../type';

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
  activeTab = ETelemetryDataType.trace;
  tabList = [
    {
      name: ETelemetryDataType.metric,
      label: window.i18n.tc('指标'),
      status: 'disabled',
      disabledTips: window.i18n.tc('指标数据未开启'),
      noDataTips: window.i18n.tc('指标无最新数据'),
    },
    {
      name: ETelemetryDataType.log,
      label: window.i18n.tc('日志'),
      status: 'disabled',
      disabledTips: window.i18n.tc('日志数据未开启'),
      noDataTips: window.i18n.tc('日志无最新数据'),
    },
    {
      name: ETelemetryDataType.trace,
      label: window.i18n.tc('调用链'),
      status: 'disabled',
      disabledTips: window.i18n.tc('调用链数据未开启'),
      noDataTips: window.i18n.tc('调用链无最新数据'),
    },
    {
      name: ETelemetryDataType.profiling,
      label: window.i18n.tc('性能分析'),
      status: 'disabled',
      disabledTips: window.i18n.tc('性能分析数据未开启'),
      noDataTips: window.i18n.tc('性能分析无最新数据'),
    },
  ];
  /* 存储信息 */
  storageInfo = {
    [ETelemetryDataType.metric]: [],
    [ETelemetryDataType.log]: null,
    [ETelemetryDataType.trace]: null,
    [ETelemetryDataType.profiling]: [],
  };
  storageLoading = true;
  indicesLoading = false;
  fieldLoading = false;
  indicesList: IndicesItem[] = []; // 物理索引
  fieldList: IFieldItem[] = []; // 字段信息
  fieldFilterList: IFieldFilterItem[] = []; // 字段信息过滤列表

  /** 集群信息 索引名 过期时间 副本数 */
  setupData = {
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

  storageStatusLoading = false;
  storageStatus = {
    [ETelemetryDataType.metric]: 'disabled',
    [ETelemetryDataType.log]: 'disabled',
    [ETelemetryDataType.trace]: 'disabled',
    [ETelemetryDataType.profiling]: 'disabled',
  };

  @Emit('change')
  handleBaseInfoChange() {
    return true;
  }

  created() {
    this.getStorageStatus();
  }

  async getStorageStatus() {
    this.storageStatusLoading = true;
    const data = await storageStatus(this.appInfo.application_id).catch(() => this.storageStatus);
    if (data) {
      this.storageStatus = data;
      for (const tab of this.tabList) {
        tab.status = this.storageStatus[tab.name];
      }
      if (this.tabList.find(item => item.name === this.activeTab)?.status === 'disabled') {
        this.activeTab = this.tabList.find(item => item.status !== 'disabled')?.name || ETelemetryDataType.trace;
      }
      this.storageStatusLoading = false;
      this.handleChangeActiveTab(this.activeTab);
    }
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
      case ETelemetryDataType.trace:
        this.getMetaConfigInfo();
        this.getIndicesList();
        this.getFieldList();
        break;
      default:
        break;
    }
  }

  logStorageChange(params) {
    this.storageInfo[ETelemetryDataType.log] = {
      ...this.storageInfo[ETelemetryDataType.log],
      ...params,
    };
  }

  traceStorageChange(params) {
    this.storageInfo[ETelemetryDataType.trace] = {
      ...this.storageInfo[ETelemetryDataType.trace],
      ...params,
    };
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
            clusterList={this.clusterList}
            dataLoading={this.storageLoading}
            indicesList={this.indicesList}
            indicesLoading={this.indicesLoading}
            storageInfo={this.storageInfo[this.activeTab]}
            telemetryDataType={this.activeTab}
            onChange={params => this.logStorageChange(params)}
          />
        );
      case ETelemetryDataType.trace:
        return (
          <Trace
            appInfo={this.appInfo}
            clusterList={this.clusterList}
            dataLoading={this.storageLoading}
            fieldFilterList={this.fieldFilterList}
            fieldList={this.fieldList}
            fieldLoading={this.fieldLoading}
            indicesList={this.indicesList}
            indicesLoading={this.indicesLoading}
            setupData={this.setupData}
            storageInfo={this.storageInfo[this.activeTab]}
            telemetryDataType={this.activeTab}
            onChange={params => this.traceStorageChange(params)}
          />
        );
    }
  }

  render() {
    return (
      <div class='conf-content storage-state-wrap'>
        <div class='storage-tab-wrap'>
          {this.storageStatusLoading ? (
            <div class='skeleton-element w-300 h-32' />
          ) : (
            <TabList
              activeTab={this.activeTab}
              tabList={this.tabList}
              onChange={this.handleChangeActiveTab}
            />
          )}
        </div>
        <div class='storage-content'>
          {this.storageStatusLoading ? (
            <PanelItem title={this.$tc('存储信息')}>
              <StorageInfoSkeleton />
            </PanelItem>
          ) : (
            this.getActiveComponent()
          )}
        </div>
      </div>
    );
  }
}
