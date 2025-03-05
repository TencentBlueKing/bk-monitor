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
import { Component, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ExploreKvList from './explore-kv-list';

import './explore-expand-view-wrapper.scss';

interface ExploreExpandViewWrapperProps {
  data: Record<string, any>;
}

enum ExploreViewTabEnum {
  JSON = 'json',
  KV = 'kv',
}

@Component
export default class ExploreExpandViewWrapper extends tsc<ExploreExpandViewWrapperProps> {
  @Prop({ type: Object, default: () => ({}) }) data: Record<string, any>;
  @InjectReactive('entitiesMapByField') entitiesMapByField;

  /** 当前活跃的nav */
  activeTab = ExploreViewTabEnum.KV;

  get isKVTab() {
    return this.activeTab === ExploreViewTabEnum.KV;
  }

  handleTabChange(activeTab: ExploreViewTabEnum) {
    this.activeTab = activeTab;
  }

  render() {
    return (
      <div class='explore-expand-view-wrapper'>
        <div class='view-tab'>
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
        <div
          class='view-content kv-view-content'
          v-show={this.isKVTab}
        >
          <ExploreKvList data={this.data} />
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
          />
        </div>
      </div>
    );
  }
}
