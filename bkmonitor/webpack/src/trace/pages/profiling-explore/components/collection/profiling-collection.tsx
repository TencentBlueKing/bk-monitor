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
import { type PropType, computed, defineComponent } from 'vue';

import { Alert, Button, Dialog, Tab } from 'bkui-vue';
import { commonPageSizeSet } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import { useCollectionTaskColumns } from '../../composables/use-collection-task-columns';
import { useProfilingCollection } from '../../composables/use-profiling-collection';
import CollectionHistory from './collection-history';
import CollectionOnboarding from './collection-onboarding';
import CollectionResults from './collection-results';
import CollectionSkeleton from './collection-skeleton';
import CollectionTaskDetail from './collection-task-detail';
import CollectionTaskForm from './collection-task-form';
import CollectionTaskTable from './collection-task-table';
import CollectionTaskToolbar from './collection-task-toolbar';
import { useAppStore } from '@/store/modules/app';

import type { SelectionRange } from '../../types';
import type { CollectionQueryState } from '../../types/collection';
import type { CollectionResultSelection } from '../../types/collection-history';

import './profiling-collection.scss';

const collectionTabs = [
  { name: 'results', label: 'Profiling 结果', icon: 'icon-Profiling' },
  { name: 'history', label: '采集任务历史', icon: 'icon-History' },
  { name: 'tasks', label: '任务管理', icon: 'icon-shezhi1' },
] as const;

export default defineComponent({
  name: 'ProfilingCollection',
  props: {
    state: { type: Object as PropType<CollectionQueryState>, required: true },
    timezone: { type: String, required: true },
    range: { type: Array as unknown as PropType<SelectionRange>, default: null },
    rangeError: { type: String, default: '' },
    revision: { type: Number, default: 0 },
    // 采集任务历史列表每次查询都重新解析时间，使相对时间取最新边界
    resolveRange: { type: Function as PropType<() => SelectionRange>, default: undefined },
  },
  emits: {
    change: (_value: Partial<CollectionQueryState>) => true,
    created: () => true,
    result: (_value: CollectionResultSelection, _newPage: boolean) => true,
    busy: (_value: boolean) => true,
    share: (_value?: CollectionResultSelection | null) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useAppStore();
    const bizId = computed(() => Number(store.bizId));
    const patch = (value: Partial<CollectionQueryState>) => emit('change', value);
    const collection = useProfilingCollection(
      bizId,
      computed(() => props.state),
      patch
    );
    // 任务列表的列由接口下发，列配置与显示列/列宽的持久化都在这里，表格只负责渲染
    const {
      tableColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
      handleSettingsChange,
      handleColumnResize,
    } = useCollectionTaskColumns(collection.taskColumns);
    return {
      t,
      bizId,
      patch,
      collection,
      tableColumns,
      storageColumns,
      allTableFields,
      lockedTableFields,
      changeTaskSettings: handleSettingsChange,
      resizeTaskColumns: handleColumnResize,
    };
  },
  render() {
    const c = this.collection;
    const state = this.state;
    if (!c.meta.value) {
      return (
        <section class='profiling-collection'>
          <div
            class={['collection-meta-state', { 'is-loading': c.loading.value }]}
            aria-busy={c.loading.value}
          >
            {c.loading.value ? (
              <CollectionSkeleton variant='page' />
            ) : (
              c.error.value && (
                <div class='collection-meta-error'>
                  <Alert
                    theme='danger'
                    title={c.error.value}
                  />
                  <Button
                    loading={c.loading.value}
                    onClick={c.refresh}
                  >
                    {this.t('重试')}
                  </Button>
                </div>
              )
            )}
          </div>
        </section>
      );
    }
    return (
      <section
        class={[
          'profiling-collection',
          {
            'has-tabs': c.meta.value.enabled,
            'is-history': c.meta.value.enabled && state.tab === 'history',
            'is-results': c.meta.value.enabled && state.tab === 'results',
          },
        ]}
      >
        {!c.meta.value.enabled ? (
          <CollectionOnboarding
            disabled={c.readonly || c.loading.value}
            loading={c.loading.value}
            onStart={() => c.openEditor()}
          />
        ) : (
          <>
            <div class='collection-tabs-header'>
              <Tab
                class='collection-tabs'
                active={state.tab}
                labelHeight={40}
                type='card-grid'
                onChange={tab => this.patch({ tab: tab as CollectionQueryState['tab'] })}
              >
                {collectionTabs.map(tab => (
                  <Tab.TabPanel
                    key={tab.name}
                    v-slots={{
                      label: () => (
                        <span class='collection-tab-label'>
                          <i class={['icon-monitor', 'collection-tab-icon', tab.icon, `is-${tab.name}`]} />
                          {this.t(tab.label)}
                        </span>
                      ),
                    }}
                    name={tab.name}
                  />
                ))}
              </Tab>
              <Button
                class='collection-create-btn'
                disabled={c.readonly}
                theme='primary'
                onClick={() => c.openEditor()}
              >
                <span class='collection-create-btn-inner'>
                  <i class='icon-monitor icon-a-1jiahao' />
                  {this.t('新建采集')}
                </span>
              </Button>
            </div>
            {state.tab === 'tasks' ? (
              <div class='collection-tab-panel collection-task-panel'>
                <CollectionTaskToolbar
                  keyword={state.keyword}
                  loading={c.loading.value}
                  onKeywordChange={keyword => this.patch({ keyword })}
                  onRefresh={c.refresh}
                >
                  {c.error.value && (
                    <Alert
                      class='collection-inline-alert'
                      theme='danger'
                      title={c.error.value}
                    />
                  )}
                  <CollectionTaskTable
                    tableSettings={{
                      checked: this.storageColumns,
                      fields: this.allTableFields,
                      disabled: this.lockedTableFields,
                    }}
                    busy={!!c.busy.value}
                    columns={this.tableColumns}
                    hasFilters={!!state.keyword || !!state.scheduleTypes.length || !!state.statuses.length}
                    loading={c.loading.value}
                    page={c.page.value}
                    pageSize={c.pageSize.value}
                    readonly={c.readonly}
                    rows={c.rows.value}
                    scheduleTypes={state.scheduleTypes}
                    sort={state.sort}
                    statuses={state.statuses}
                    timezone={this.timezone}
                    total={c.filtered.value.length}
                    onColumnResizeChange={this.resizeTaskColumns}
                    onDelete={row => {
                      c.deleting.value = row;
                    }}
                    onDetail={row => {
                      c.detailId.value = row.task_id;
                    }}
                    onEdit={row => c.openEditor(row)}
                    onExecute={row => {
                      c.executing.value = row;
                    }}
                    onFilterChange={this.patch}
                    onHistory={row => c.openHistory(row)}
                    onLimitChange={value => {
                      if (c.pageSize.value === value) return;
                      c.pageSize.value = value;
                      // 持久化到全局统一分页配置，与其他模块保持一致
                      commonPageSizeSet(value);
                    }}
                    onPageChange={value => {
                      c.page.value = value;
                    }}
                    onResetFilters={() => this.patch({ keyword: '', scheduleTypes: [], statuses: [] })}
                    onSettingsChange={this.changeTaskSettings}
                    onSortChange={sort => this.patch({ sort })}
                    onToggle={row => c.runAction(row, 'switch')}
                  />
                </CollectionTaskToolbar>
              </div>
            ) : state.tab === 'history' ? (
              <CollectionHistory
                key={this.bizId}
                bizId={this.bizId}
                filters={state.history}
                range={this.range}
                rangeError={this.rangeError}
                readonly={c.readonly}
                resolveRange={this.resolveRange}
                revision={this.revision}
                statusFilters={c.meta.value.execution_status_filters}
                timezone={this.timezone}
                onBusy={value => this.$emit('busy', value)}
                onChange={history => this.patch({ history, historyTaskName: history.task_name, historyTaskId: null })}
                onCreated={() => this.$emit('created')}
                onResult={(value, newPage) => this.$emit('result', value, newPage)}
                onShare={value => this.$emit('share', value)}
              />
            ) : (
              <CollectionResults
                key={this.bizId}
                bizId={this.bizId}
                range={this.range}
                rangeError={this.rangeError}
                readonly={c.readonly}
                revision={this.revision}
                selection={state.result}
                state={state.results}
                timezone={this.timezone}
                onBusy={value => this.$emit('busy', value)}
                onChange={this.patch}
                onCreate={() => {
                  this.patch({ tab: 'tasks' });
                  c.openEditor();
                }}
                onCreated={() => this.$emit('created')}
                onResult={(value, newPage) => this.$emit('result', value, newPage)}
                onShare={value => this.$emit('share', value)}
              />
            )}
          </>
        )}
        {c.editorOpen.value && c.meta.value && (
          <CollectionTaskForm
            key={`${this.bizId}:${c.editing.value?.task_id || 'new'}`}
            bizId={this.bizId}
            meta={c.meta.value}
            task={c.editing.value}
            timezone={this.timezone}
            onClose={() => {
              c.editorOpen.value = false;
            }}
            onSaved={c.saved}
          />
        )}
        {c.detail.value && (
          <CollectionTaskDetail
            busy={!!c.busy.value}
            hostError={c.detailHostError.value}
            hostLoading={c.detailHostLoading.value}
            hosts={c.detailHosts.value}
            readonly={c.readonly}
            task={c.detail.value}
            onClose={() => {
              c.detailId.value = undefined;
            }}
            onDelete={() => {
              c.deleting.value = c.detail.value;
            }}
            onEdit={() => c.openEditor(c.detail.value)}
            onHistory={() => c.openHistory(c.detail.value)}
            onRetryHosts={c.loadDetailHosts}
          />
        )}
        <Dialog
          beforeClose={() => !c.busy.value}
          isShow={!!c.deleting.value}
          quickClose={false}
          title={this.t('确认删除任务？')}
          transfer={false}
          onClosed={() => {
            if (!c.busy.value) c.deleting.value = undefined;
          }}
        >
          {{
            default: () => <p>{c.deleting.value?.name}</p>,
            footer: () => (
              <div class='collection-dialog-footer'>
                <Button
                  v-tippy={this.t('确认删除当前任务')}
                  loading={!!c.busy.value}
                  theme='danger'
                  onClick={() => c.runAction(c.deleting.value, 'delete')}
                >
                  {this.t('删除')}
                </Button>
                <Button
                  v-tippy={this.t('取消本次操作')}
                  disabled={!!c.busy.value}
                  onClick={() => {
                    c.deleting.value = undefined;
                  }}
                >
                  {this.t('取消')}
                </Button>
              </div>
            ),
          }}
        </Dialog>
        <Dialog
          beforeClose={() => !c.busy.value}
          isShow={!!c.executing.value}
          quickClose={false}
          title={this.t('确认立即执行任务？')}
          transfer={false}
          onClosed={() => {
            if (!c.busy.value) c.executing.value = undefined;
          }}
        >
          {{
            default: () => (
              <>
                <p>{c.executing.value?.name}</p>
                <p>{this.t('将使用当前配置发起一次采集，原有执行计划保持不变。')}</p>
                <p>{this.t('立即执行仅支持 Linux 主机，提交后可在采集任务历史查看进度')}</p>
              </>
            ),
            footer: () => (
              <div class='collection-dialog-footer'>
                <Button
                  v-tippy={this.t('使用当前配置立即执行一次采集')}
                  loading={!!c.busy.value}
                  theme='primary'
                  onClick={() => c.runAction(c.executing.value, 'execute')}
                >
                  {this.t('确定')}
                </Button>
                <Button
                  v-tippy={this.t('取消本次操作')}
                  disabled={!!c.busy.value}
                  onClick={() => {
                    c.executing.value = undefined;
                  }}
                >
                  {this.t('取消')}
                </Button>
              </div>
            ),
          }}
        </Dialog>
      </section>
    );
  },
});
