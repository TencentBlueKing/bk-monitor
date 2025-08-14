import { Component, Emit, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils';
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
import VueJsonPretty from 'vue-json-pretty';

import { getDefaultTimezone } from '../../../i18n/dayjs';
import { APIType } from '../api-utils';
import {
  type ConditionChangeEvent,
  type DimensionType,
  type ExploreEntitiesMap,
  type ExploreFieldMap,
  ExploreEntitiesTypeEnum,
} from '../typing';
import { type ExploreSubject, optimizedSplit } from '../utils';
import ExploreKvList, { type KVFieldList } from './explore-kv-list';

import './explore-expand-view-wrapper.scss';

enum ExploreViewTabEnum {
  JSON = 'json',
  KV = 'kv',
}

interface ExploreExpandViewWrapperEvents {
  onConditionChange(e: ConditionChangeEvent): void;
  onUpdateKvFieldCache: (originData, kvFieldItem: KVFieldList) => void;
}

interface ExploreExpandViewWrapperProps {
  data: Record<string, any>;
  detailData: Record<string, any>;
  entitiesMapList: ExploreEntitiesMap[];
  fieldMap: ExploreFieldMap;
  kvFieldCache: WeakMap<any, KVFieldList[]>;
  /** 滚动事件被观察者实例 */
  scrollSubject: ExploreSubject;
  source: APIType;
}

@Component
export default class ExploreExpandViewWrapper extends tsc<
  ExploreExpandViewWrapperProps,
  ExploreExpandViewWrapperEvents
> {
  /** 渲染数据 */
  @Prop({ type: Object, default: () => ({}) }) data: Record<string, any>;
  /** 用于从接口数据中获取 容器 跳转路径 */
  @Prop({ type: Object, default: () => ({}) }) detailData: Record<string, any>;
  /** 用于获取 data 数据中 key 的字段类型 */
  @Prop({ type: Object, default: () => ({ source: {}, target: {} }) }) fieldMap: ExploreFieldMap;
  /** 用于判断 data 数据中 key 是否提供跳转入口 */
  @Prop({ type: Array, default: () => [] }) entitiesMapList: ExploreEntitiesMap[];
  /** 滚动事件被观察者实例 */
  @Prop({ type: Object }) scrollSubject?: ExploreSubject;
  /** 来源 */
  @Prop({ type: String, default: APIType.MONITOR }) source: APIType;
  @Prop({ type: WeakMap }) kvFieldCache: WeakMap<any, KVFieldList[]>;
  /** 筛选时间范围-跳转时使用 */
  @InjectReactive('timeRange') timezone: string;
  /** 当前活跃的nav */
  activeTab = ExploreViewTabEnum.KV;

  get isKVTab() {
    return this.activeTab === ExploreViewTabEnum.KV;
  }

  /** KV列表 */
  get kvFieldList(): KVFieldList[] {
    if (this.kvFieldCache?.has?.(this.data)) {
      return this.kvFieldCache.get(this.data);
    }
    const kvFieldList = Object.entries(this.data).map(([key, sourceValue]) => {
      const entities = [];
      const fieldItem = this.fieldMap?.target?.[key] || {};
      const sourceName = fieldItem?.name as string;
      const canClick = sourceValue != null && sourceValue !== '' && !!sourceName;

      if (canClick) {
        for (const entitiesMap of this.entitiesMapList) {
          const item = entitiesMap?.[key];
          if (!item || item?.dependent_fields?.some(field => !this.data[field])) {
            continue;
          }
          const path = this.getEntitiesJumpLink(sourceName, sourceValue, item);
          if (!path) continue;

          entities.push({
            alias: item.alias,
            type: item.type,
            path,
          });
        }
      }
      const value = fieldItem.type === 'text' ? optimizedSplit(sourceValue) : sourceValue;
      const kvFieldItem = {
        name: key,
        type: fieldItem?.type as DimensionType,
        value: value as string,
        sourceName,
        entities,
        canOpenStatistics: fieldItem?.is_option_enabled || false,
        canClick,
      };
      return kvFieldItem;
    });
    this.$emit('updateKvFieldCache', this.data, kvFieldList);
    return kvFieldList;
  }

  @Emit('conditionChange')
  conditionChange(condition: ConditionChangeEvent) {
    return condition;
  }

  /**
   * @description 根据 sourceName 获取最终展示的value值(因为部分字段在 data 中对应的key是拼接处理过的字段)
   *
   */
  getValueBySourceName(name: string) {
    const finalName = this.fieldMap?.source?.[name]?.finalName;
    return this.data[finalName];
  }

  /**
   * @description 获取kv列表 容器/主机 跳转路径
   */
  getEntitiesJumpLink(fieldName, value, entitiesItem) {
    let path = '';
    const item = this.detailData[fieldName];
    path = item?.url || '';
    if (path) {
      return path;
    }
    const timezone = this.timezone?.length ? this.timezone : getDefaultTimezone();
    switch (entitiesItem.type) {
      case ExploreEntitiesTypeEnum.HOST:
        {
          const cloudId =
            this.getValueBySourceName('bk_cloud_id') || this.getValueBySourceName('bk_target_cloud_id') || '0';
          const endStr = `${value}${fieldName === 'bk_host_id' ? '' : `-${cloudId}`}`;
          const query = `?from=${timezone[0]}&to=${timezone[1]}`;
          path = `#/performance/detail/${endStr}${query}`;
        }
        break;
      case ExploreEntitiesTypeEnum.K8S:
        {
          if (fieldName === 'host') {
            const cluster = this.getValueBySourceName('bcs_cluster_id');
            const query = {
              sceneId: 'kubernetes',
              dashboardId: 'node',
              sceneType: 'detail',
              from: timezone[0],
              to: timezone[1],
              queryData: JSON.stringify({
                selectorSearch: [
                  {
                    bcs_cluster_id: cluster,
                  },
                  {
                    name: value,
                  },
                ],
              }),
            };
            const targetRoute = this.$router.resolve({
              path: '/k8s',
              query,
            });
            path = targetRoute.href;
          }
        }
        break;
    }
    return path;
  }

  /**
   * @description kv面板header右侧 复制按钮 点击事件
   *
   **/
  handleCopy() {
    copyText(JSON.stringify(this.data, null, 4), msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  handleTabChange(activeTab: ExploreViewTabEnum) {
    this.activeTab = activeTab;
  }

  render() {
    return (
      <div class='explore-expand-view-wrapper'>
        <div class='view-header'>
          <div class='header-tabs'>
            <span
              class={{ active: this.isKVTab }}
              onClick={() => this.handleTabChange(ExploreViewTabEnum.KV)}
            >
              KV
            </span>
            <span
              class={{ active: !this.isKVTab }}
              onClick={() => this.handleTabChange(ExploreViewTabEnum.JSON)}
            >
              JSON
            </span>
          </div>
        </div>
        <div
          class='view-content kv-view-content'
          v-show={this.isKVTab}
        >
          <div class='content-operation'>
            <i
              class='icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: this.$t('复制'), distance: 5 }}
              onClick={this.handleCopy}
            />
          </div>
          <ExploreKvList
            fieldList={this.kvFieldList}
            scrollSubject={this.scrollSubject}
            source={this.source}
            onConditionChange={this.conditionChange}
          />
        </div>
        <div
          class='view-content json-view-content'
          v-show={!this.isKVTab}
        >
          <div class='content-operation'>
            <i
              class='icon-monitor icon-mc-copy'
              v-bk-tooltips={{ content: this.$t('复制'), distance: 5 }}
              onClick={this.handleCopy}
            />
          </div>
          <VueJsonPretty
            collapsedOnClickBrackets={false}
            data={this.data}
            deep={5}
            showIcon={true}
            showKeyValueSpace={true}
          />
        </div>
      </div>
    );
  }
}
