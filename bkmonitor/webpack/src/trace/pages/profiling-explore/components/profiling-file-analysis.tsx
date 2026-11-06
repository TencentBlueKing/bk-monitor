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
import { type PropType, computed, defineComponent, onScopeDispose, watch } from 'vue';

import { Button, Exception, Loading, Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useProfileResults } from '../composables/use-profile-results';
import { getExportUrl } from '../services/profiling';
import { fileStatusLabels } from '../utils/file';
import ProfileVisualization from './profile-visualization/profile-visualization';
import ProfilingEmptyState from './profiling-empty-state';
import ProfilingFilter from './profiling-filter';
import ProfilingSkeleton from './profiling-skeleton';

import type { UseProfilingFilesReturn } from '../composables/use-profiling-files';
import type { FileQueryState } from '../types/file';

export default defineComponent({
  name: 'ProfilingFileAnalysis',
  props: {
    query: { type: Object as PropType<UseProfilingFilesReturn>, required: true },
    state: { type: Object as PropType<FileQueryState>, required: true },
    selectedFavorite: { type: Object, default: null },
  },
  emits: { favorite: (_edit: boolean) => true, upload: () => true },
  setup(props) {
    const { t } = useI18n();
    const results = useProfileResults({
      query: props.query.submitted,
      active: props.query.active,
      revision: props.query.revision,
      timeComparison: computed(() => false),
      traceMode: computed(() => false),
      graphMode: computed({
        get: () => props.state.view.graphMode,
        set: graphMode => props.query.patchView({ graphMode }),
      }),
      trendsEnabled: false,
    });
    watch(
      results.graphLoading,
      value => {
        props.query.setRefreshBusy(value);
      },
      { immediate: true }
    );
    onScopeDispose(() => {
      props.query.setRefreshBusy(false);
    });
    function exportProfile() {
      if (!props.query.submitted.value) return;
      const link = document.createElement('a');
      link.href = getExportUrl(props.query.submitted.value);
      link.click();
    }
    return { t, results, exportProfile, fileStatusLabels };
  },
  render() {
    const q = this.query;
    const r = this.results;
    const file = q.selected.value;
    const state = this.state;
    const initializing = q.initializing.value;
    const failed = file && ['parsing_failed', 'store_failed'].includes(file.status);
    const parsing = file && ['uploaded', 'parsing_succeed'].includes(file.status);
    return (
      <div class='profiling-application profiling-file-analysis'>
        {(initializing || file?.status === 'store_succeed') && (
          <ProfilingFilter
            key={state.profileId}
            commonWhere={state.commonWhere}
            configKey={`profiling_file_${state.profileId}`}
            fields={q.fields.value}
            getValues={q.getFieldValues}
            loading={initializing}
            selectedFavorite={this.selectedFavorite}
            where={state.where}
            onChange={where => q.changeFilters({ where })}
            onCommonChange={commonWhere => q.changeFilters({ commonWhere })}
            onFavorite={edit => this.$emit('favorite', edit)}
            onSearch={() => q.executeQuery()}
          />
        )}
        {!initializing && q.error.value && q.submitted.value && (
          <div class='profiling-inline-error'>
            {q.error.value}
            <Button
              theme='primary'
              text
              onClick={() => q.refreshRecords(true)}
            >
              {this.t('重试')}
            </Button>
          </div>
        )}
        {q.labelError.value && (
          <div class='profiling-inline-error'>
            {q.labelError.value}
            <Button
              theme='primary'
              text
              onClick={q.loadLabels}
            >
              {this.t('重试')}
            </Button>
          </div>
        )}
        <div class='profiling-results'>
          {initializing ? (
            <div
              class='profiling-data-options profiling-options-skeleton'
              aria-hidden='true'
            >
              <i class='skeleton-element' />
              <i class='skeleton-element' />
            </div>
          ) : (
            file?.status === 'store_succeed' && (
              <div class='profiling-data-options'>
                <div>
                  <span>{this.t('数据类型')}:</span>
                  <Radio.Group
                    modelValue={state.dataType}
                    size='small'
                    onChange={q.selectDataType}
                  >
                    {file.data_types.map(item => (
                      <Radio.Button
                        key={item.key}
                        label={item.key}
                      >
                        {item.name}
                      </Radio.Button>
                    ))}
                  </Radio.Group>
                </div>
                <div>
                  <span>{this.t('汇聚方法')}:</span>
                  <Radio.Group
                    modelValue={state.aggregation}
                    size='small'
                    onChange={aggregation => {
                      q.patchFile({ aggregation });
                      q.executeQuery();
                    }}
                  >
                    {['AVG', 'SUM', 'LAST'].map(method => (
                      <Radio.Button
                        key={method}
                        label={method}
                      >
                        {method}
                      </Radio.Button>
                    ))}
                  </Radio.Group>
                </div>
              </div>
            )
          )}
          {initializing ? (
            <section
              class='profile-visualization profiling-file-loading'
              aria-busy='true'
              aria-label={this.t('正在加载文件分析')}
            >
              <div
                class='profiling-file-loading-toolbar'
                aria-hidden='true'
              >
                <i class='skeleton-element' />
                <i class='skeleton-element' />
                <i class='skeleton-element' />
              </div>
              <div class='profile-visualization-content'>
                {['table', 'combined'].includes(state.view.graphMode) && (
                  <div class='profile-table-pane'>
                    <ProfilingSkeleton variant='table' />
                  </div>
                )}
                {['flame', 'combined'].includes(state.view.graphMode) && (
                  <div class='profile-flame-pane'>
                    <ProfilingSkeleton variant='flame' />
                  </div>
                )}
                {state.view.graphMode === 'callgraph' && <ProfilingSkeleton variant='callgraph' />}
              </div>
            </section>
          ) : q.submitted.value ? (
            <ProfileVisualization
              v-slots={{
                empty: () => (
                  <div class='profiling-file-state'>
                    <Exception
                      description={this.t('请调整时间范围或检索条件后重试')}
                      scene='part'
                      title={this.t('未找到匹配的数据')}
                      type='empty'
                    />
                  </div>
                ),
              }}
              callGraph={r.callGraph.value}
              data={r.graph.value}
              dataType={state.dataType.split('/')[0]}
              error={r.graphError.value}
              loading={r.graphLoading.value}
              mode={state.view.graphMode}
              view={state.view}
              onExport={this.exportProfile}
              onModeChange={graphMode => q.patchView({ graphMode })}
              onRetry={r.retryGraph}
              onViewChange={q.patchView}
            />
          ) : !file && !q.error.value ? (
            <ProfilingEmptyState
              description={this.t('通过火焰图和函数列表，定位耗时热点与调用关系')}
              hint={this.t('单个文件不超过 50 MB，支持批量上传')}
              icon='upload-cloud'
              title={this.t('上传文件，开始 Profiling 分析')}
            >
              {{
                default: () => (
                  <Button
                    theme='primary'
                    onClick={() => this.$emit('upload')}
                  >
                    <i class='icon-monitor icon-upload-cloud' />
                    {this.t('上传文件')}
                  </Button>
                ),
                footer: () => (
                  <>
                    {this.t('支持 pprof、perf_script 格式')}
                    <br />
                    {this.t('上传后自动解析，完成后即可查看分析结果')}
                  </>
                ),
              }}
            </ProfilingEmptyState>
          ) : (
            <div
              class='profiling-file-state profiling-file-state-card'
              role='status'
            >
              {q.error.value ? (
                <Exception
                  description={q.error.value}
                  scene='part'
                  title={this.t('文件分析暂不可用')}
                  type='500'
                >
                  <div class='profiling-file-state-actions'>
                    <Button
                      theme='primary'
                      onClick={() => q.refreshRecords(true)}
                    >
                      {this.t('重试')}
                    </Button>
                    <Button onClick={() => this.$emit('upload')}>{this.t('上传文件')}</Button>
                  </div>
                </Exception>
              ) : parsing ? (
                <div class='profiling-file-processing'>
                  <Loading
                    mode='spin'
                    size='large'
                    theme='primary'
                  >
                    <div class='profiling-file-processing-indicator' />
                  </Loading>
                  <h3>{this.t('文件解析中')}</h3>
                  <p
                    class='profiling-file-processing-name'
                    title={file.file_name}
                  >
                    {file.file_name}
                  </p>
                  <p>{this.t('解析完成后自动展示分析结果，也可在上方选择其他文件')}</p>
                </div>
              ) : (
                <Exception
                  description={
                    failed
                      ? this.t('可在文件详情中查看失败原因，或重新上传文件')
                      : file
                        ? this.t('请选择其他文件，或重新上传后分析')
                        : this.t('上传 pprof 或 perf_script 文件，查看函数耗时与调用关系')
                  }
                  title={
                    failed
                      ? this.t(this.fileStatusLabels[file.status])
                      : file
                        ? this.t('暂无可用的数据类型')
                        : this.t('暂无 Profiling 文件')
                  }
                  scene='part'
                  type={failed ? '500' : 'empty'}
                >
                  <Button
                    theme='primary'
                    onClick={() => this.$emit('upload')}
                  >
                    <i class='icon-monitor icon-upload-cloud' /> {this.t(file ? '重新上传' : '上传文件')}
                  </Button>
                </Exception>
              )}
            </div>
          )}
        </div>
      </div>
    );
  },
});
