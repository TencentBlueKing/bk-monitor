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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils';

import ExploreKvList, { type KVFieldList } from './explore-kv-list';

import type { IWhereItem } from '../../../components/retrieval-filter/utils';
import type { DimensionType, ExploreEntitiesMap, ExploreEntitiesTypeEnum, ExploreFieldMap } from '../typing';

import './explore-expand-view-wrapper.scss';

interface ExploreExpandViewWrapperProps {
  data: Record<string, any>;
  fieldMap: ExploreFieldMap;
  entitiesMap: ExploreEntitiesMap;
}

interface ExploreExpandViewWrapperEvents {
  onConditionChange: (condition: IWhereItem[]) => void;
}

enum ExploreViewTabEnum {
  JSON = 'json',
  KV = 'kv',
}

@Component
export default class ExploreExpandViewWrapper extends tsc<
  ExploreExpandViewWrapperProps,
  ExploreExpandViewWrapperEvents
> {
  /** 渲染数据 */
  @Prop({ type: Object, default: () => ({}) }) data: Record<string, any>;
  /** 用于获取 data 数据中 key 的字段类型 */
  @Prop({ type: Object, default: () => ({ source: {}, target: {} }) }) fieldMap: ExploreFieldMap;
  /** 用于判断 data 数据中 key 是否提供跳转入口 */
  @Prop({ type: Object, default: () => ({}) }) entitiesMap: ExploreEntitiesMap;

  /** 当前活跃的nav */
  activeTab = ExploreViewTabEnum.KV;

  get isKVTab() {
    return this.activeTab === ExploreViewTabEnum.KV;
  }

  /** KV列表 */
  get kvFieldList(): KVFieldList[] {
    const externalParams = {
      cloudId: this?.data?.bk_cloud_id || this?.data?.bk_target_cloud_id || '0',
    };
    return Object.entries(this.data).map(([key, value]) => {
      const entities = this.entitiesMap[key];
      let hasEntities = true;
      let entitiesAlias: string = entities?.alias;
      let entitiesType = entities?.type as '' | ExploreEntitiesTypeEnum;
      if (!entities || entities?.dependent_fields?.some(field => !this.data[field])) {
        hasEntities = false;
        entitiesAlias = '';
        entitiesType = '';
      }

      const fieldItem = this.fieldMap?.target?.[key] || {};
      return {
        name: key,
        type: fieldItem?.type as DimensionType,
        value: value as string,
        sourceName: fieldItem?.name as string,
        entitiesType,
        hasEntities,
        canOpenStatistics: fieldItem?.is_option_enabled || false,
        entitiesAlias,
        externalParams,
      };
    });
  }

  @Emit('conditionChange')
  conditionChange(condition: IWhereItem[]) {
    return condition;
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
          <div class='header-operation'>
            <i
              class='icon-monitor icon-mc-copy'
              onClick={this.handleCopy}
            />
          </div>
        </div>
        <div
          class='view-content kv-view-content'
          v-show={this.isKVTab}
        >
          <ExploreKvList
            fieldList={this.kvFieldList}
            onConditionChange={this.conditionChange}
          />
        </div>
        <div
          class='view-content json-view-content'
          v-show={!this.isKVTab}
        >
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
