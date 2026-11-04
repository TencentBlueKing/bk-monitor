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
import { type PropType, computed, defineComponent, shallowRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Alert, Button, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useCollectionCandidates } from '../../composables/use-collection-candidates';
import {
  createHistoryFilters,
  parseProcessSelection,
  processCandidateOptions,
  restoreProcessSelection,
} from '../../utils/collection-history';
import EmptyStatus from '@/components/empty-status/empty-status';
import { TraceCellSkeleton } from '@/pages/trace-explore/components/trace-explore-skeleton';

import type { SelectionRange } from '../../types';
import type { CollectionHistoryFilters } from '../../types/collection-history';

import './collection-filters.scss';

// 输入停顿后才请求候选值，避免逐字符调用 topk 接口
const SEARCH_DEBOUNCE_TIME = 300;
// 候选加载中的骨架行数，与下拉高度 200px 下的选项行数一致
const SKELETON_ROWS = 6;

// allowCreate 的触发器输入清空时，Select 会抛出与内部选中态不一致的空 change（handleInputChange 副作用）；
// 空值先与组件内部 selected 核对（兼容 ref 未解包形态），仅内部也为空才视为真实清空
function isInternalSelectionEmpty(refs: Record<string, unknown>, name: string) {
  const raw = (refs[name] as undefined | { selected?: unknown })?.selected;
  const selected = (raw as undefined | { value?: unknown })?.value ?? raw;
  return !Array.isArray(selected) || selected.length === 0;
}

export default defineComponent({
  name: 'CollectionFilters',
  props: {
    filters: { type: Object as PropType<CollectionHistoryFilters>, required: true },
    bizId: { type: Number, required: true },
    // 结果页没有时间范围时不传，候选值也随之清空
    range: { type: Array as unknown as PropType<null | SelectionRange>, default: null },
    // 选中筛选值后立即查询，无须再点查询按钮
    autoQuery: Boolean,
    // 按任务 ID 筛选时的任务名，用于任务下拉回显
    taskName: { type: String, default: '' },
  },
  emits: { change: (_value: CollectionHistoryFilters) => true, refresh: () => true },
  setup(props, { emit }) {
    const { t } = useI18n();
    const draft = shallowRef(createHistoryFilters());
    const processes = shallowRef<string[]>([]);
    const bizId = computed(() => props.bizId);
    const range = computed(() => props.range);
    // 三个下拉各自维护候选值，按需远程搜索与滚动加载
    const targetCandidates = useCollectionCandidates(bizId, range, ['target']);
    const taskCandidates = useCollectionCandidates(bizId, range, ['task_name']);
    const processCandidates = useCollectionCandidates(bizId, range, ['process_names', 'process_pids']);
    const searchTargets = useDebounceFn((keyword: string) => targetCandidates.search(keyword), SEARCH_DEBOUNCE_TIME);
    const searchTasks = useDebounceFn((keyword: string) => taskCandidates.search(keyword), SEARCH_DEBOUNCE_TIME);
    const searchProcesses = useDebounceFn((keyword: string) => processCandidates.search(keyword), SEARCH_DEBOUNCE_TIME);
    // 下拉的远程搜索回调需要返回 Promise，防抖函数返回的 Promise 类型带额外成员，用普通函数转一次
    async function remoteTargets(keyword: string) {
      await searchTargets(keyword);
    }
    async function remoteTasks(keyword: string) {
      await searchTasks(keyword);
    }
    async function remoteProcesses(keyword: string) {
      await searchProcesses(keyword);
    }
    // 任一候选接口失败即提示，具体文案与重试入口由渲染层提供
    const candidateError = computed(
      () => targetCandidates.error.value || taskCandidates.error.value || processCandidates.error.value
    );
    // 候选值加载中的骨架行
    function renderSkeleton() {
      return (
        <li class='collection-filter-loading'>
          {Array.from({ length: SKELETON_ROWS }, (_, index) => (
            <div
              key={index}
              class='collection-filter-loading-row'
            >
              <TraceCellSkeleton
                field='name'
                index={index}
              />
            </div>
          ))}
        </li>
      );
    }
    // 下拉没有候选值时统一用空态：加载中显示骨架行，带关键字时按「搜索结果为空」区分文案
    function renderEmpty(state: ReturnType<typeof useCollectionCandidates>) {
      if (state.loading.value) return renderSkeleton();
      return (
        <li class='collection-filter-empty'>
          <EmptyStatus
            showOperation={false}
            type={state.keyword.value ? 'search-empty' : 'empty'}
          />
        </li>
      );
    }
    // 重试时三个下拉一起重查，失败提示也随之统一消失
    function reloadCandidates() {
      targetCandidates.reload();
      taskCandidates.reload();
      processCandidates.reload();
    }
    // 外部筛选变化时同步草稿，并按新条件恢复进程下拉的回显值
    watch(
      () => props.filters,
      value => {
        draft.value = { ...value };
        processes.value = restoreProcessSelection(value, processes.value);
      },
      { immediate: true }
    );
    // 条件未变化时只刷新列表；有变化才抛出 change，避免重复写入筛选状态
    function submit() {
      if (JSON.stringify(props.filters) === JSON.stringify(draft.value)) emit('refresh');
      else emit('change', { ...draft.value });
    }
    // 选中即写入草稿；autoQuery 面板直接提交，其余面板等用户点查询
    function apply(patch: Partial<CollectionHistoryFilters>) {
      draft.value = { ...draft.value, ...patch };
      if (props.autoQuery) submit();
    }
    // 重置后立即按空条件重新查询，不保留上一次的筛选状态
    function reset() {
      draft.value = createHistoryFilters();
      processes.value = [];
      submit();
    }
    return {
      t,
      draft,
      processes,
      targetCandidates,
      taskCandidates,
      processCandidates,
      remoteTargets,
      remoteTasks,
      remoteProcesses,
      candidateError,
      reloadCandidates,
      renderEmpty,
      renderSkeleton,
      submit,
      apply,
      reset,
    };
  },
  render() {
    const { draft } = this;
    // 已选值可能不在当前候选里（远程搜索替换了列表），补成选项保证回显
    const targetOptions = () => {
      const items = this.targetCandidates.candidates.value.target || [];
      const options = items.map(item => (
        <Select.Option
          id={String(item.value)}
          key={`target:${item.value}`}
          name={item.alias || String(item.value)}
        />
      ));
      for (const ip of draft.ips) {
        if (!items.some(item => String(item.value) === ip)) {
          options.unshift(
            <Select.Option
              id={ip}
              key={`target:${ip}`}
              name={ip}
            />
          );
        }
      }
      return options.length ? options : [this.renderEmpty(this.targetCandidates)];
    };
    // 按任务 ID 进入或选中值不在候选里时，补一个选项让任务下拉回显名称
    const taskOptions = () => {
      const items = this.taskCandidates.candidates.value.task_name || [];
      const options = items.map(item => (
        <Select.Option
          id={String(item.value)}
          key={`task_name:${item.value}`}
          name={item.alias || String(item.value)}
        />
      ));
      const name = draft.task_id ? this.taskName : draft.task_name;
      if (name && !items.some(item => String(item.value) === name)) {
        options.unshift(
          <Select.Option
            id={name}
            key={`task_name:${name}`}
            name={name}
          />
        );
      }
      return options.length ? options : [this.renderEmpty(this.taskCandidates)];
    };
    // 进程名与 PID 共用一份候选，已选值不在候选里时由 processCandidateOptions 补回显
    const processOptions = () => {
      const options = processCandidateOptions(this.processCandidates.candidates.value, this.processes).map(option => (
        <Select.Option
          id={option.id}
          key={option.id}
          name={option.name}
        />
      ));
      return options.length ? options : [this.renderEmpty(this.processCandidates)];
    };
    return (
      <>
        <div class='collection-history-filters'>
          <label>
            <span>IP</span>
            <Select
              ref='ipSelect'
              inputSearch={false}
              loading={this.targetCandidates.loading.value}
              modelValue={draft.ips}
              remoteMethod={this.remoteTargets}
              scrollLoading={this.targetCandidates.loading.value && !this.targetCandidates.searching.value}
              allowCreate
              collapseTags
              customContent
              filterable
              multiple
              onChange={ips => {
                const next = ips || [];
                if (next.length || isInternalSelectionEmpty(this.$refs, 'ipSelect')) this.apply({ ips: next });
              }}
              onScroll-end={() => this.targetCandidates.loadMore()}
            >
              {this.targetCandidates.searching.value ? this.renderSkeleton() : targetOptions()}
            </Select>
          </label>
          <label>
            <span>{this.t('任务')}</span>
            <Select
              ref='taskSelect'
              inputSearch={false}
              loading={this.taskCandidates.loading.value}
              modelValue={draft.task_id ? this.taskName : draft.task_name}
              remoteMethod={this.remoteTasks}
              scrollLoading={this.taskCandidates.loading.value && !this.taskCandidates.searching.value}
              allowCreate
              customContent
              filterable
              onChange={value => {
                // 选择任务名后改为按名称筛选，不再按任务 ID 定位
                if (value || isInternalSelectionEmpty(this.$refs, 'taskSelect')) {
                  this.apply({ task_id: null, task_name: String(value || '') });
                }
              }}
              onScroll-end={() => this.taskCandidates.loadMore()}
            >
              {this.taskCandidates.searching.value ? this.renderSkeleton() : taskOptions()}
            </Select>
          </label>
          <label>
            <span>{this.t('进程')}</span>
            <Select
              inputSearch={false}
              loading={this.processCandidates.loading.value}
              modelValue={this.processes}
              multipleMode='tag'
              placeholder={this.t('进程名或 PID')}
              remoteMethod={this.remoteProcesses}
              scrollLoading={this.processCandidates.loading.value && !this.processCandidates.searching.value}
              allowCreate
              customContent
              filterable
              multiple
              onChange={values => {
                this.processes = values || [];
                this.apply(parseProcessSelection(this.processes));
              }}
              onScroll-end={() => this.processCandidates.loadMore()}
            >
              {this.processCandidates.searching.value ? this.renderSkeleton() : processOptions()}
            </Select>
          </label>
          <div class='collection-history-query'>
            <Button
              v-tippy={this.t('按当前筛选条件查询')}
              theme='primary'
              onClick={this.submit}
            >
              {this.t('查询')}
            </Button>
            <Button
              v-tippy={this.t('清空筛选条件并重新查询')}
              onClick={this.reset}
            >
              {this.t('重置')}
            </Button>
          </div>
        </div>
        {this.candidateError && (
          <Alert
            v-slots={{
              title: () => (
                <i18n-t
                  v-slots={{
                    retry: () => (
                      <Button
                        v-tippy={this.t('重新加载筛选候选项')}
                        theme='primary'
                        text
                        onClick={this.reloadCandidates}
                      >
                        {this.t('重试')}
                      </Button>
                    ),
                  }}
                  keypath='部分筛选候选加载失败，可手动输入条件或 {retry}'
                />
              ),
            }}
            theme='warning'
          />
        )}
      </>
    );
  },
});
