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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { transformDataKey } from 'monitor-common/utils/utils';

import MetricListItem from '../components/metric-list-item';
import StrategyTargetTable from '../strategy-config-detail-table.vue';

import type { IFunctionsValue } from '../../strategy-config-set-new/monitor-data/function-select';
import type { MetricDetail } from '../../strategy-config-set-new/typings';

import './query-configs-main.scss';

interface IProps {
  metricData: MetricDetail[];
  editMode: 'Edit' | 'Source';
  expression: string;
  expFunctions: IFunctionsValue[];
  sourceData: {
    sourceCode: string;
    step: number | string;
  };
  targetsDesc: string;
  targetDetail: Record<string, any>;
}

@Component({
  components: {
    StrategyTargetTable,
    PromqlMonacoEditor: () =>
      import(/* webpackChunkName: 'PromqlMonacoEditor' */ '../../../../components/promql-editor/promql-editor'),
  },
})
export default class DataQuery extends tsc<IProps> {
  // 展示选中的监控目标
  showTargetTable = false;

  // 警告等级划分
  levelList = [
    { id: 1, name: this.$t('致命'), icon: 'icon-danger' },
    { id: 2, name: this.$t('预警'), icon: 'icon-mind-fill' },
    { id: 3, name: this.$t('提醒'), icon: 'icon-tips' },
  ];

  // 指标数据
  @Prop({ type: Array, default: null }) metricData: MetricDetail[];

  // 编辑模式
  @Prop({ type: String }) editMode: 'Edit' | 'Source';

  // 表达式
  @Prop({ type: String }) expression: string;

  // 表达式函数
  @Prop({ type: Array, default: null }) expFunctions: IFunctionsValue[];

  // source数据 此数据与指标数据隔离
  @Prop({ type: Object }) sourceData: Record<number | string, string>;

  // 监控目标数据
  @Prop({ type: String }) targetsDesc: string;

  // 当前告警等级
  // @Prop({ type: Object }) currentAlertLevel: Record<string, number | string>;

  // 监控目标
  @Prop({ type: Object }) targetDetail: Record<string, any>;

  // 查看监控主机的数据
  get targetsTableData() {
    return this.targetDetail.detail ? transformDataKey(this.targetDetail.detail) : null;
  }

  // 当前警告数据
  get currentAlertData() {
    const targetData = this.metricData
      .slice(0, 1)
      .find(item => item.metricMetaId === 'bk_monitor|event' || item.data_type_label === 'alert');
    if (targetData) {
      return this.levelList[targetData.level - 1];
    }
    return null;
  }

  handleShowTargetTable() {
    this.showTargetTable = true;
  }

  render() {
    return (
      <div class='query-configs-main'>
        {(() => {
          if (this.editMode === 'Edit') {
            return [
              this.metricData.map((metricItem, index) => (
                <MetricListItem
                  key={index}
                  metric={metricItem}
                />
              )),
              this.expression?.trim()?.length > 2 ? (
                <MetricListItem
                  key='expression'
                  expFunctions={this.expFunctions}
                  expression={this.expression}
                />
              ) : undefined,
            ];
          }
          return (
            <div class='promql-content'>
              <div class='edit-wrap'>
                <promql-monaco-editor
                  minHeight={160}
                  readonly={true}
                  value={this.sourceData.sourceCode}
                />
              </div>
              <div class='step-wrap'>
                <bk-input
                  class='step-input'
                  min={10}
                  type='number'
                  value={this.sourceData.step}
                  disabled
                >
                  <div
                    class='step-input-prepend'
                    slot='prepend'
                  >
                    <span>{'Step'}</span>
                    <span
                      class='icon-monitor icon-hint'
                      v-bk-tooltips={{
                        content: this.$t('数据步长'),
                        placements: ['top'],
                      }}
                    />
                  </div>
                </bk-input>
              </div>
            </div>
          );
        })()}

        {this.targetsDesc && (
          <div class='targets-desc'>
            <span onClick={this.handleShowTargetTable}>
              <i class='icon-monitor icon-mc-tv' />
              <span class='targets-desc-text'>{this.targetsDesc}</span>
            </span>
          </div>
        )}

        {this.currentAlertData ? (
          <div class='event-alert-level'>
            <span class='level-label'>{this.$t('告警级别')} : </span>
            <span class='level-content'>
              <i class={['icon-monitor', this.currentAlertData.icon, `level-icon-${this.currentAlertData.id}`]} />
              <span class='level-text'>{this.currentAlertData.name}</span>
            </span>
          </div>
        ) : undefined}

        <div>
          {this.targetsTableData && (
            <bk-dialog
              width={1100}
              ext-cls='target-table-wrap'
              v-model={this.showTargetTable}
              header-position='left'
              show-footer={false}
              title={this.$t('监控目标')}
            >
              <strategy-target-table
                objType={this.metricData[0]?.objectType || this.targetDetail?.instance_type || ''}
                tableData={this.targetsTableData}
                targetType={this.metricData[0]?.targetType || this.targetDetail?.node_type || ''}
              />
            </bk-dialog>
          )}
        </div>
      </div>
    );
  }
}
