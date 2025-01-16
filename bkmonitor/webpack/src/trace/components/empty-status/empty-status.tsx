/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { type PropType, computed, defineComponent } from 'vue';

import { Exception } from 'bkui-vue';

import type { TranslateResult } from 'vue-i18n';

import './empty-status.scss';

export type EmptyStatusType = '403' | '500' | 'empty' | 'search-empty' | string;
type EmptyStatusScene = 'page' | 'part';
type EmptyStatusOperationType = 'clear-filter' | 'refresh';
export type IEmptyStatusTextMap = {
  [key in EmptyStatusType]?: TranslateResult;
};

const defaultTextMap: IEmptyStatusTextMap = {
  empty: window.i18n.t('暂无数据'),
  'search-empty': window.i18n.t('无数据'),
  500: window.i18n.t('数据获取异常'),
  403: window.i18n.t('无业务权限'),
};

export default defineComponent({
  name: 'EmptyStatus',
  props: {
    type: {
      type: String as PropType<EmptyStatusType>,
      default: 'empty',
    },
    scene: {
      type: String as PropType<EmptyStatusScene>,
      default: 'part',
    },
    showOperation: {
      type: Boolean,
      default: true,
    },
    textMap: {
      type: Object as PropType<IEmptyStatusTextMap>,
      default: defaultTextMap,
    },
  },
  emits: ['operation'],
  setup(props, { emit }) {
    const typeText = computed(() => props.textMap[props.type]);

    const handleOperation = (type: EmptyStatusOperationType) => {
      emit('operation', type);
    };

    return {
      typeText,
      handleOperation,
    };
  },
  render() {
    const defaultOperation = () => {
      if (this.type === 'empty') return undefined;
      if (this.type === 'search-empty') {
        return (
          <i18n
            class='operation-text'
            path='可以尝试{0}或{1}'
          >
            <span style='margin: 0 3px'>{this.$t('调整关键词')}</span>
            <span
              style='margin-left: 3px'
              class='operation-btn'
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
    };

    return (
      <div class='empty-status-container'>
        <Exception
          scene={this.scene}
          type={this.type}
          {...this.$attrs}
        >
          <div class='empty-text-content'>
            <p class='empty-text'>{this.typeText}</p>
            {this.showOperation && (this.$slots.default?.() || defaultOperation())}
          </div>
        </Exception>
      </div>
    );
  },
});
