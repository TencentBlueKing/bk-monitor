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

import { type PropType, computed, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import QueryConfigDetail from '../query-config/query-config-detail';

import type { QueryConfig } from 'monitor-pc/pages/query-template/typings';

import './query-config-viewer.scss';

export default defineComponent({
  name: 'QueryConfigViewer',
  props: {
    queryConfigs: {
      type: Array as PropType<QueryConfig[]>,
      default: () => [],
    },
    expression: {
      type: String,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const showExpression = computed(() => props.queryConfigs?.length > 1);
    return { t, showExpression };
  },
  render() {
    return (
      <div class='query-config-viewer'>
        {this.showExpression ? (
          <div class='expression-view'>
            <div class='item-label'>
              <span>{`${this.t('表达式')} :`}</span>
            </div>
            <div class='item-value-view'>
              <span class='value'>{this.expression || '--'}</span>
            </div>
          </div>
        ) : null}
        <div class='config-view'>
          {this.queryConfigs.map((queryConfig, i) => (
            <QueryConfigDetail
              key={i}
              queryConfig={queryConfig}
              showAlias={this.showExpression}
            />
          ))}
        </div>
      </div>
    );
  },
});
