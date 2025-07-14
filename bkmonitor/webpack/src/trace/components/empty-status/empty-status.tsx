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
import { useI18n } from 'vue-i18n';

import { Exception } from 'bkui-vue';

import type { TranslateResult } from 'vue-i18n';

import './empty-status.scss';

export type EmptyStatusType = '403' | '500' | 'empty' | 'search-empty' | string;
export type EmptyStatusScene = 'page' | 'part';
export type EmptyStatusOperationType = 'clear-filter' | 'refresh';
export type IEmptyStatusTextMap = {
  [key in EmptyStatusType]?: TranslateResult;
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
      default: () => null,
    },
  },
  emits: ['operation'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const defaultTextMap = {
      empty: t('暂无数据'),
      'search-empty': t('搜索结果为空'),
      500: t('数据获取异常'),
      403: t('无业务权限'),
    };
    const typeText = computed(() => (props.textMap || defaultTextMap)[props.type]);

    const handleOperation = (type: EmptyStatusOperationType) => {
      emit('operation', type);
    };

    return {
      typeText,
      handleOperation,
      t,
    };
  },
  render() {
    const defaultOperation = () => {
      if (this.type === 'empty') return undefined;
      if (this.type === 'search-empty') {
        return (
          <i18n-t
            class='operation-text'
            keypath='可以尝试{0}或{1}'
          >
            <span style='margin: 0 3px'>{this.t('调整关键词')}</span>
            <span
              style='margin-left: 3px'
              class='operation-btn'
              onClick={() => this.handleOperation('clear-filter')}
            >
              {this.t('清空筛选条件')}
            </span>
          </i18n-t>
        );
      }
      if (this.type === '500') {
        return (
          <span
            class='operation-btn'
            onClick={() => this.handleOperation('refresh')}
          >
            {this.t('刷新')}
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
