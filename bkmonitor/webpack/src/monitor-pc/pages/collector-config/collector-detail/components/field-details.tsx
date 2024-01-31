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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import Collapse from '../../../../components/collapse/collapse';
import { DetailData } from '../typings/detail';

import './field-details.scss';

interface FieldDetailsProps {
  detailData: DetailData;
}

@Component
export default class FieldDetails extends tsc<FieldDetailsProps> {
  @Prop({ type: Object, required: true }) detailData: DetailData;

  metricList = [];

  @Watch('detailData')
  handleDetailDataChange(val: DetailData) {
    if (val) {
      this.metricList = val.metric_list.map(item => ({ ...item, collapse: true }));
    }
  }

  getTitle(table) {
    if (this.$i18n.locale !== 'enUS') {
      return `${table.id}（${table.name}）`;
    }
    return table.id;
  }

  render() {
    return (
      <div class='field-details-component'>
        <div class='metric-dimension'>
          <div class='table-wrap'>
            {this.metricList.map((item, index) => (
              <div class='table-item'>
                <div
                  class={{ 'table-item-title': true, 'is-collapse': item.collapse }}
                  onClick={() => (item.collapse = !item.collapse)}
                >
                  <i class={['bk-icon', 'title-icon', item.collapse ? 'icon-down-shape' : 'icon-right-shape']} />
                  {this.getTitle(item)}
                </div>

                <Collapse
                  key={index}
                  expand={item.collapse}
                  renderContent={false}
                  needCloseButton={false}
                >
                  <bk-table
                    class='metric-wrap-table'
                    data={item.list}
                    empty-text={this.$t('无数据')}
                    max-height={350}
                  >
                    <bk-table-column
                      label={this.$t('指标/维度')}
                      width='150'
                      scopedSlots={{
                        default: ({ row }) =>
                          row.metric === 'metric' ? this.$t('指标（Metric）') : this.$t('维度（Dimension）')
                      }}
                    />
                    <bk-table-column
                      label={this.$t('英文名')}
                      min-width='150'
                      scopedSlots={{
                        default: ({ row }) => <span title={row.englishName}>{row.englishName || '--'}</span>
                      }}
                    />

                    <bk-table-column
                      label={this.$t('别名')}
                      min-width='150'
                      scopedSlots={{
                        default: ({ row }) => <span title={row.aliaName}>{row.aliaName || '--'}</span>
                      }}
                    />
                    <bk-table-column
                      label={this.$t('类型')}
                      width='80'
                      scopedSlots={{
                        default: ({ row }) => <span title={row.type}>{row.type || '--'}</span>
                      }}
                    />
                    <bk-table-column
                      label={this.$t('单位')}
                      width='100'
                      scopedSlots={{
                        default: ({ row }) => <span title={row.unit}>{row.unit || '--'}</span>
                      }}
                    />
                  </bk-table>
                </Collapse>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
}
