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

import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import EmptyStatus from '../../../../../components/empty-status/empty-status';

import './explore-table-empty.scss';

export default defineComponent({
  name: 'ExploreTableEmpty',
  emits: {
    dataSourceConfigClick: () => true,
    clearFilter: () => true,
  },
  setup() {
    const { t } = useI18n();
    return { t };
  },
  render() {
    return (
      <EmptyStatus
        class='explore-table-empty'
        type='search-empty'
      >
        <div class='search-empty-content'>
          <div class='tips'>
            <span>{this.t('请调整关键字')}</span>&nbsp;
            <span>{this.t('或')}</span>&nbsp;
            <span
              class='link'
              onClick={() => this.$emit('clearFilter')}
            >
              {this.t('清空检索条件')}
            </span>
          </div>
          {/* <div class='tips'>{this.t('您可以按照以下方式优化检索结果')}</div>
          <div class='description'>
            1. {this.t('检查')}
            <span
              class='link'
              onClick={() => this.$emit('dataSourceConfigClick')}
            >
              {this.t('数据源配置')}
            </span>
            {this.t('情况')}
          </div>
          <div class='description'>2. {this.t('检查右上角的时间范围')}</div>
          <div class='description'>3. {this.t('是否启用了采样，采样不保证全量数据')}</div>
          <div class='description'>
            4. {this.t('优化查询语句')}
            <div class='sub-description'>{`${this.t('带字段全文检索更高效')}：log:abc`}</div>
            <div class='sub-description'>{`${this.t('模糊检索使用通配符')}：log:abc* ${this.t('或')} log:ab?c`}</div>
            <div class='sub-description'>{`${this.t('双引号匹配完整字符串')}: log:"ERROR MSG"`}</div>
            <div class='sub-description'>{`${this.t('数值字段范围匹配')}: count:[1 TO 5]`}</div>
            <div class='sub-description'>{`${this.t('正则匹配')}：name:/joh?n(ath[oa]n/`}</div>
            <div class='sub-description'>{`${this.t('组合检索注意大写')}：log: (error OR info)`}</div>
          </div>
          <div
            style='margin-top: 8px'
            class='description link'
          >
            {this.t('查看更多语法规则')}
            <span class='icon-monitor icon-fenxiang' />
          </div> */}
        </div>
      </EmptyStatus>
    );
  },
});
