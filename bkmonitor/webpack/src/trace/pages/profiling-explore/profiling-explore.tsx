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
import { computed, defineComponent, shallowRef, watch } from 'vue';

import { Button, Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import ProfileVisualization from './components/profile-visualization/profile-visualization';
import ProfilingEmptyState from './components/profiling-empty-state';
import ProfilingFavoritePreview from './components/profiling-favorite-preview';
import ProfilingFileAnalysis from './components/profiling-file-analysis';
import ProfilingFileTools from './components/profiling-file-tools';
import ProfilingFilter from './components/profiling-filter';
import ProfilingHeader from './components/profiling-header';
import ProfilingTrend from './components/profiling-trend';
import { useProfileResults } from './composables/use-profile-results';
import { useProfilingFavorite } from './composables/use-profiling-favorite';
import { useProfilingQuery } from './composables/use-profiling-query';
import { getExportUrl } from './services/profiling';
import { useDocumentLink } from '@/hooks/documentLink';
import FavoriteBox, { EditFavorite } from '@/pages/trace-explore/components/favorite-box';

import type { ProfilingFavorite, ProfilingTab } from './types';

import './components/profiling-file-analysis.scss';
import './profiling-explore.scss';

export default defineComponent({
  name: 'ProfilingExplore',
  setup() {
    const { t } = useI18n();
    const query = useProfilingQuery();
    const fileTools = shallowRef<InstanceType<typeof ProfilingFileTools>>();
    const header = shallowRef<InstanceType<typeof ProfilingHeader>>();
    const { handleGotoLink } = useDocumentLink();
    const active = query.active;
    const tab = computed({
      get: () => query.state.value.view.tab,
      set: (tab: ProfilingTab) => {
        query.changeTab(tab);
      },
    });
    const results = useProfileResults({
      query: query.submitted,
      graphMode: computed({
        get: () => query.state.value.view.graphMode,
        set: graphMode => query.patchView({ graphMode }),
      }),
      traceMode: computed({
        get: () => query.state.value.view.traceMode,
        set: traceMode => query.patchView({ traceMode }),
      }),
      active,
      revision: query.revision,
      timeComparison: computed(() => query.state.value.mode === 'time'),
    });
    watch([results.graphLoading, results.trendLoading], ([graph, trend]) => {
      query.refreshBusy.value = graph || trend;
    });
    const favorite = useProfilingFavorite({
      state: query.state,
      initial: query.initialFavorite,
      apply: query.applyState,
    });
    const favoriteBox = shallowRef<{ refreshGroupList: () => void }>();
    const refreshFavorites = () => favoriteBox.value?.refreshGroupList();
    const saveFavorite = (edit: boolean) => favorite.save(edit, refreshFavorites);
    const combinedSeries = computed(() =>
      results.trends.value.flatMap((result, index) =>
        result.series.map(series => ({
          ...series,
          alias:
            query.state.value.mode !== 'none'
              ? results.trends.value.length === 2
                ? t(index === 0 ? '查询项' : '对比项')
                : series.dimensions?.device_name
              : series.target,
        }))
      )
    );
    const renderFavoriteQuery = (item: ProfilingFavorite) => {
      const value = item.config?.profiling;
      if (!value) return <span>--</span>;
      return <ProfilingFavoritePreview value={value} />;
    };
    function exportProfile() {
      if (!query.submitted.value) return;
      const link = document.createElement('a');
      link.href = getExportUrl(query.submitted.value);
      link.click();
    }
    return {
      t,
      tab,
      query,
      fileTools,
      header,
      handleGotoLink,
      results,
      favorite,
      favoriteBox,
      combinedSeries,
      refreshFavorites,
      saveFavorite,
      renderFavoriteQuery,
      exportProfile,
    };
  },
  render() {
    const q = this.query;
    const r = this.results;
    const f = this.favorite;
    const state = q.state.value;
    const comparingTime = state.mode === 'time';
    const applicationReady = !!q.detail.value?.data_types.length;
    return (
      <div class='profiling-explore'>
        <aside
          style={{ display: f.visible.value ? '' : 'none' }}
          class='profiling-favorites'
        >
          <FavoriteBox
            ref='favoriteBox'
            v-slots={{ renderFavoriteQuery: this.renderFavoriteQuery }}
            type='profiling'
            onChange={f.select}
            onClose={() => {
              f.visible.value = false;
            }}
            onOpenBlank={f.open}
          />
        </aside>
        <main class='profiling-main'>
          <ProfilingHeader
            ref='header'
            v-slots={{
              fileTools: () => (
                <ProfilingFileTools
                  key={q.files.bizId.value}
                  ref='fileTools'
                  fileName={state.file.fileName}
                  loading={q.files.loading.value}
                  profileId={state.file.profileId}
                  records={q.files.records.value}
                  onRefresh={() => q.files.refreshRecords()}
                  onSelect={q.files.selectFile}
                  onUploaded={q.files.acceptUploaded}
                />
              ),
            }}
            detail={q.detail.value}
            favoriteShow={f.visible.value}
            loading={q.loading.value}
            serviceOptions={q.serviceOptions.value}
            state={state}
            tab={this.tab}
            onFavoriteToggle={() => {
              f.visible.value = !f.visible.value;
            }}
            onModeChange={q.changeMode}
            onPatch={q.patch}
            onSearch={() => q.executeQuery(true)}
            onServiceChange={q.selectService}
            onTabChange={tab => {
              this.tab = tab;
            }}
          />
          {this.tab === 'application' ? (
            <div class='profiling-application'>
              {(q.loading.value || applicationReady) && (
                <ProfilingFilter
                  commonWhere={state.commonWhere}
                  configKey={`profiling_${state.appName}_${state.serviceName}_baseline`}
                  fields={q.fields.value}
                  getValues={q.getFieldValues}
                  label={comparingTime ? this.t('查询项') : ''}
                  loading={q.loading.value}
                  selectedFavorite={f.selected.value}
                  where={state.where}
                  onChange={where => q.changeFilters({ where })}
                  onCommonChange={commonWhere => q.changeFilters({ commonWhere })}
                  onFavorite={this.saveFavorite}
                  onSearch={() => q.executeQuery()}
                />
              )}
              {(q.loading.value || applicationReady) && state.mode !== 'none' && (
                <ProfilingFilter
                  commonWhere={state.comparisonCommonWhere}
                  configKey={`profiling_${state.appName}_${state.serviceName}_comparison`}
                  fields={q.fields.value}
                  getValues={q.getFieldValues}
                  label={this.t('对比项')}
                  loading={q.loading.value}
                  where={state.comparisonWhere}
                  onChange={comparisonWhere => q.changeFilters({ comparisonWhere })}
                  onCommonChange={comparisonCommonWhere => q.changeFilters({ comparisonCommonWhere })}
                  onFavorite={this.saveFavorite}
                  onSearch={() => q.executeQuery()}
                />
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
              <div
                class='profiling-results'
                aria-busy={q.loading.value}
              >
                {q.error.value && (
                  <div class='profiling-inline-error'>
                    {q.error.value}
                    <Button
                      theme='primary'
                      text
                      onClick={q.initialize}
                    >
                      {this.t('重试')}
                    </Button>
                  </div>
                )}
                {q.loading.value ? (
                  <div
                    class='profiling-data-options profiling-options-skeleton'
                    aria-hidden='true'
                  >
                    <i class='skeleton-element' />
                    <i class='skeleton-element' />
                  </div>
                ) : (
                  !!q.detail.value?.data_types.length && (
                    <div class='profiling-data-options'>
                      <div>
                        <span>{this.t('数据类型')}:</span>
                        <Radio.Group
                          modelValue={state.dataType}
                          size='small'
                          onChange={q.selectDataType}
                        >
                          {q.detail.value.data_types.map(type => (
                            <Radio.Button
                              key={type.key}
                              label={type.key}
                            >
                              {type.name}
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
                            q.patch({ aggregation });
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
                {q.submitted.value || q.loading.value ? (
                  <>
                    <div class={['profiling-trends', { 'time-comparison': comparingTime }]}>
                      {comparingTime ? (
                        (['baseline', 'comparison'] as const).map((side, index) => (
                          <ProfilingTrend
                            key={side}
                            defaultRange={
                              q.bounds.value
                                ? index === 0
                                  ? [q.bounds.value[0], Math.floor((q.bounds.value[0] + q.bounds.value[1]) / 2)]
                                  : [Math.floor((q.bounds.value[0] + q.bounds.value[1]) / 2), q.bounds.value[1]]
                                : null
                            }
                            bounds={q.bounds.value}
                            color={index === 0 ? '#3a84ff' : '#ea3636'}
                            error={r.trendError.value}
                            loading={q.loading.value || r.trendLoading.value}
                            range={side === 'baseline' ? state.baselineRange : state.comparisonRange}
                            series={r.trends.value[index]?.series || []}
                            timezone={state.timezone}
                            title={this.t(index === 0 ? '查询项' : '对比项')}
                            selection
                            onRetry={r.retryTrends}
                            onSelect={range => q.selectRange(side, range)}
                          />
                        ))
                      ) : (
                        <ProfilingTrend
                          appName={state.appName}
                          bounds={q.bounds.value}
                          collapsed={state.view.trendCollapsed}
                          error={r.trendError.value}
                          legend={state.view.legend}
                          loading={q.loading.value || r.trendLoading.value}
                          series={this.combinedSeries}
                          timezone={state.timezone}
                          trace={r.traceMode.value}
                          onCollapseChange={trendCollapsed => q.patchView({ trendCollapsed })}
                          onLegendChange={legend => q.patchView({ legend })}
                          onRetry={r.retryTrends}
                          onTraceChange={value => {
                            r.traceMode.value = value;
                          }}
                        />
                      )}
                    </div>
                    <ProfileVisualization
                      callGraph={r.callGraph.value}
                      compared={state.mode !== 'none'}
                      data={r.graph.value}
                      dataType={state.dataType.split('/')[0]}
                      error={r.graphError.value}
                      loading={q.loading.value || r.graphLoading.value}
                      mode={r.graphMode.value}
                      view={state.view}
                      onExport={this.exportProfile}
                      onModeChange={mode => {
                        r.graphMode.value = mode;
                      }}
                      onRetry={r.retryGraph}
                      onViewChange={q.patchView}
                    />
                  </>
                ) : (
                  !q.error.value && (
                    <ProfilingEmptyState
                      title={this.t(
                        q.serviceOptions.value.some(item => item.services.length)
                          ? '当前服务暂无 Profiling 数据'
                          : '暂无可分析的应用服务'
                      )}
                      description={this.t('接入 Profiling 并上报数据后，即可分析服务的性能热点')}
                      hint={this.t('也可以上传本地文件，无需接入应用即可开始分析')}
                      icon='mc-flame'
                    >
                      {{
                        default: () => (
                          <>
                            <Button
                              theme='primary'
                              onClick={() => this.header?.createApplication()}
                            >
                              {this.t('新增接入')}
                            </Button>
                            <Button
                              onClick={() => {
                                this.tab = 'file';
                              }}
                            >
                              {this.t('分析本地文件')}
                            </Button>
                          </>
                        ),
                        footer: () => (
                          <>
                            <Button
                              theme='primary'
                              text
                              onClick={() => this.handleGotoLink('profiling_docs')}
                            >
                              {this.t('查看接入指引')}
                            </Button>
                            <Button
                              theme='primary'
                              text
                              onClick={q.initialize}
                            >
                              {this.t('已上报数据？刷新列表')}
                            </Button>
                          </>
                        ),
                      }}
                    </ProfilingEmptyState>
                  )
                )}
              </div>
            </div>
          ) : this.tab === 'file' ? (
            <ProfilingFileAnalysis
              key={q.files.bizId.value}
              query={q.files}
              selectedFavorite={f.selected.value}
              state={state.file}
              onFavorite={this.saveFavorite}
              onUpload={() => this.fileTools?.openUpload()}
            />
          ) : (
            <div class={`profiling-${this.tab}-placeholder`} />
          )}
        </main>
        {f.editing.value && (
          <EditFavorite
            v-slots={{ renderFavoriteQuery: this.renderFavoriteQuery }}
            data={f.editData.value}
            isCreate
            isShow
            onClose={() => {
              f.editing.value = false;
            }}
          />
        )}
      </div>
    );
  },
});
