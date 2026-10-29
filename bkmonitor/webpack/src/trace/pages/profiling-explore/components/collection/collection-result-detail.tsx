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
import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Button, Radio, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useCollectionResultDetail } from '../../composables/use-collection-result-detail';
import { collectionTypeLabels, formatCollectionTime } from '../../utils/collection';
import { createViewState } from '../../utils/query';
import ProfileVisualization from '../profile-visualization/profile-visualization';
import CollectionExecutionStatus from './collection-execution-status';
import SliderHeader from '@/components/slider-header/slider-header';

import type { CollectionResultSelection } from '../../types/collection-history';
import type { CollectionHostResult, CollectionResultsState } from '../../types/collection-results';

import './collection-result-detail.scss';

export default defineComponent({
  name: 'CollectionResultDetail',
  props: {
    bizId: { type: Number, required: true },
    selection: { type: Object as PropType<CollectionResultSelection>, required: true },
    source: { type: Object as PropType<CollectionHostResult>, default: undefined },
    state: { type: Object as PropType<CollectionResultsState>, required: true },
    timezone: { type: String, required: true },
    readonly: Boolean,
    busy: Boolean,
    // 叠加在其他侧弹之上时挂到 body，避免受父级定位上下文影响
    transfer: { type: [Boolean, String, Object] as PropType<boolean | HTMLElement | string>, default: false },
  },
  emits: {
    change: (_value: Partial<CollectionResultsState>) => true,
    close: () => true,
    share: () => true,
    execution: (_value: CollectionHostResult) => true,
    rerun: (_value: CollectionHostResult) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const fullscreen = shallowRef(false);
    const d = useCollectionResultDetail({
      bizId: computed(() => props.bizId),
      selection: computed(() => props.selection),
      source: computed(() => props.source),
      dataType: computed(() => props.state.dataType),
      onDataType: dataType => emit('change', { dataType }),
    });
    return { t, fullscreen, d };
  },
  render() {
    const d = this.d;
    const row = d.row.value;
    const processes = row?.processes.map(item => `${item.process_name} (${item.pid})`).join('，') || '--';
    return (
      <Sideslider
        width={this.fullscreen ? '100%' : '75%'}
        class='collection-result-detail'
        beforeClose={() => !this.busy}
        isShow={true}
        transfer={this.transfer}
        onClosed={() => this.$emit('close')}
      >
        {{
          header: () => (
            <SliderHeader title={this.t('采集结果')}>
              {{
                buttons: () => (
                  <>
                    <Button
                      class='collection-result-header-action'
                      text
                      onClick={() => {
                        this.fullscreen = !this.fullscreen;
                      }}
                    >
                      <i class={['icon-monitor', this.fullscreen ? 'icon-mc-unfull-screen' : 'icon-fullscreen']} />
                      {this.t(this.fullscreen ? '退出全屏' : '全屏')}
                    </Button>
                    <Button
                      class='collection-result-header-action'
                      v-tippy={this.t(
                        this.readonly
                          ? '暂无采集操作权限'
                          : this.busy
                            ? '正在提交采集任务'
                            : row?.status === 'running'
                              ? '采集中，暂不能重新采集'
                              : '使用历史配置重新采集当前主机'
                      )}
                      disabled={this.readonly || this.busy || !row || row.status === 'running'}
                      text
                      onClick={() => this.$emit('rerun', row)}
                    >
                      <i class='icon-monitor icon-mc-retry' />
                      {this.t('重新采集')}
                    </Button>
                    <Button
                      class='collection-result-header-action'
                      disabled={!row || !!d.error.value}
                      text
                      onClick={() => this.$emit('share')}
                    >
                      <i class='icon-monitor icon-mc-share' />
                      {this.t('分享结果')}
                    </Button>
                  </>
                ),
              }}
            </SliderHeader>
          ),
          default: () => (
            <>
              <div class='collection-result-summary'>
                <span class='collection-result-icon'>
                  <i />
                </span>
                <div class='collection-result-summary-fields'>
                  <div class='collection-result-summary-field'>
                    <label>{this.t('目标 IP')}：</label>
                    <span>{row?.ip || '--'}</span>
                  </div>
                  <div class='collection-result-summary-field'>
                    <label>{this.t('采集进程')}：</label>
                    <span title={processes}>{processes}</span>
                  </div>
                  <div class='collection-result-summary-field'>
                    <label>{this.t('采集类型')}：</label>
                    <span>{collectionTypeLabels[row?.collection_type] || '--'}</span>
                  </div>
                  <div class='collection-result-summary-field'>
                    <label>{this.t('采集任务')}：</label>
                    <Button
                      class='collect-task-btn'
                      v-tippy={{
                        content: `${row?.task.name || ''} · ${this.t('查看本次任务执行详情')}`,
                        allowHTML: false,
                      }}
                      disabled={!row}
                      theme='primary'
                      text
                      onClick={() => this.$emit('execution', row)}
                    >
                      {row?.task.name || '--'}
                      <i class='icon-monitor icon-fenxiang' />
                    </Button>
                  </div>
                  <div class='collection-result-summary-field'>
                    <label>{this.t('采集时间')}：</label>
                    <span>{formatCollectionTime(row?.started_at, this.timezone)}</span>
                  </div>
                  <div class='collection-result-summary-field'>
                    <label>{this.t('状态')}：</label>
                    {row ? (
                      <CollectionExecutionStatus
                        status={row.status}
                        result
                      />
                    ) : (
                      '--'
                    )}
                  </div>
                </div>
              </div>
              <div class='collection-result-body'>
                {!!d.types.value.length && (
                  <div class='collection-result-data-types'>
                    <span>{this.t('数据类型')}：</span>
                    <Radio.Group
                      modelValue={d.selectedType.value}
                      onChange={dataType =>
                        this.$emit('change', { dataType: String(dataType), view: createViewState() })
                      }
                    >
                      {d.types.value.map(type => (
                        <Radio.Button
                          key={type.key}
                          v-tippy={{ content: this.t('切换采样类型：{name}', { name: type.name }), allowHTML: false }}
                          label={type.key}
                        >
                          {type.name}
                        </Radio.Button>
                      ))}
                    </Radio.Group>
                  </div>
                )}
                <ProfileVisualization
                  allowCallGraph={false}
                  data={d.data.value}
                  dataType={d.selectedType.value.split('/')[0]}
                  error={d.error.value || d.graphError.value}
                  exporting={d.exporting.value}
                  loading={d.loading.value || d.graphLoading.value}
                  mode={this.state.view.graphMode}
                  view={this.state.view}
                  onExport={d.exportProfile}
                  onModeChange={graphMode => this.$emit('change', { view: { ...this.state.view, graphMode } })}
                  onRetry={d.error.value ? d.load : d.loadProfile}
                  onViewChange={view => this.$emit('change', { view: { ...this.state.view, ...view } })}
                />
              </div>
            </>
          ),
        }}
      </Sideslider>
    );
  },
});
