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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { EmptyStatusOperationType, EmptyStatusType, IEmptyStatusTextMap } from './types';

import './empty-status.scss';

/* bk-exception组件Type */
interface IEmptyStatusProps {
  type?: EmptyStatusType;
  scene?: 'page' | 'part';
  showOperation?: boolean;
  textMap?: IEmptyStatusTextMap;
}

interface IEmptyStatusEvent {
  onOperation: (type: EmptyStatusOperationType) => void;
}

// 默认类型对应的文本枚举
export const defaultTextMap: IEmptyStatusTextMap = {
  empty: window.i18n.t('查无数据'),
  'search-empty': window.i18n.t('搜索结果为空'),
  500: window.i18n.t('数据获取异常'),
  403: window.i18n.t('无业务权限')
};

@Component
export default class EmptyStatus extends tsc<IEmptyStatusProps, IEmptyStatusEvent> {
  @Prop({ default: 'empty', type: String }) type: EmptyStatusType;
  @Prop({ default: 'part', type: String }) scene: IEmptyStatusProps['scene'];
  @Prop({ default: true, type: Boolean }) showOperation: boolean;
  @Prop({ default: () => defaultTextMap, type: Object })
  textMap: IEmptyStatusProps['textMap'];

  get typeText() {
    return this.textMap[this.type];
  }

  // 默认类型的操作
  get defaultOperation() {
    if (this.type === 'empty') return undefined;
    if (this.type === 'search-empty') {
      return (
        <i18n
          class='operation-text'
          path='可以尝试{0}或{1}'
        >
          <span style='margin: 0 3px'>{this.$t('调整关键词')}</span>
          <span
            class='operation-btn'
            style='margin-left: 3px'
            onClick={() => this.handleOperation('clear-filter')}
          >
            {this.$t('清空筛选条件')}
          </span>
        </i18n>
      );
    }
    if (this.type === '500') {
      return (
        <span
          class='operation-btn'
          onClick={() => this.handleOperation('refresh')}
        >
          {this.$t('刷新')}
        </span>
      );
    }
    return undefined;
  }

  @Emit('operation')
  handleOperation(type: EmptyStatusOperationType) {
    return type;
  }

  render() {
    return (
      <div class='empty-status-container'>
        <bk-exception
          type={this.type}
          scene={this.scene}
          {...{ props: this.$attrs }}
        >
          <div class='empty-text-content'>
            <p class='empty-text'>{this.typeText}</p>
            {this.showOperation && (this.$slots.default || this.defaultOperation)}
          </div>
        </bk-exception>
      </div>
    );
  }
}
