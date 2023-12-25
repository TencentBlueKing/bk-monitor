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

import { EventRetrievalViewType } from '../../typings';

import KVList from './kv-list';

import './expand-view-wrapper.scss';
import 'vue-json-pretty/lib/styles.css';

interface IProps {
  data: object;
}

interface IEvent {
  onDrillSearch: EventRetrievalViewType.IDrillModel;
}

@Component
export default class FieldFiltering extends tsc<IProps, IEvent> {
  @Prop({ default: () => ({}), type: Object }) data: object;

  /** 当前活跃的nav */
  activeExpandView = 'kv';

  @Emit('drillSearch')
  handleMenuClick(keywords: EventRetrievalViewType.IDrillModel) {
    return keywords;
  }

  render() {
    return (
      <div class='expand-view-wrapper'>
        <div class='view-tab'>
          <span
            class={{ active: this.activeExpandView === 'kv' }}
            onClick={() => (this.activeExpandView = 'kv')}
          >
            KV
          </span>
          <span
            class={{ active: this.activeExpandView === 'json' }}
            onClick={() => (this.activeExpandView = 'json')}
          >
            JSON
          </span>
        </div>
        <div
          class='view-content kv-view-content'
          v-show={this.activeExpandView === 'kv'}
        >
          <KVList
            data={this.data}
            onDrillSearch={this.handleMenuClick}
          />
        </div>
        <div
          class='view-content json-view-content'
          v-show={this.activeExpandView === 'json'}
        >
          <VueJsonPretty
            data={this.data}
            collapsedOnClickBrackets={false}
            deep={5}
          />
        </div>
      </div>
    );
  }
}
