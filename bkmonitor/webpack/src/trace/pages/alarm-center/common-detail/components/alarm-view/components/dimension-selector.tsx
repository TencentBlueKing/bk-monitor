/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { defineComponent, shallowRef } from 'vue';

import { Checkbox, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './dimension-selector.scss';

export default defineComponent({
  name: 'DimensionSelector',
  props: {
    a: {
      type: String,
      default: '',
    },
  },
  emits: {
    change: (_val: any) => true,
  },
  setup() {
    const { t } = useI18n();

    const searchValue = shallowRef('');
    return {
      searchValue,
      t,
    };
  },
  render() {
    return (
      <div class='dimension-analysis-dimension-selector'>
        <div class='header-title'>
          <span class='title'>{this.t('维度分析')}</span>
          <Checkbox>{this.t('多选')}</Checkbox>
        </div>
        <div class='search-wrap'>
          <Input
            v-model={this.searchValue}
            type='search'
          />
        </div>
        <div class='dimension-list'>
          <div>dimension01</div>
          <div>dimension02</div>
        </div>
      </div>
    );
  },
});
