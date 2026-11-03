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
import { type PropType, defineComponent, shallowRef, watch } from 'vue';

import { Button, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import {
  createHistoryFilters,
  parseProcessSelection,
  processCandidateOptions,
  restoreProcessSelection,
} from '../../utils/collection-history';

import type {
  CollectionCandidate,
  CollectionCandidateField,
  CollectionHistoryFilters,
} from '../../types/collection-history';

export default defineComponent({
  name: 'CollectionFilters',
  props: {
    filters: { type: Object as PropType<CollectionHistoryFilters>, required: true },
    candidates: {
      type: Object as PropType<Partial<Record<CollectionCandidateField, CollectionCandidate[]>>>,
      required: true,
    },
    loading: Boolean,
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
    watch(
      () => props.filters,
      value => {
        draft.value = { ...value };
        processes.value = restoreProcessSelection(value, processes.value);
      },
      { immediate: true }
    );
    function submit() {
      if (JSON.stringify(props.filters) === JSON.stringify(draft.value)) emit('refresh');
      else emit('change', { ...draft.value });
    }
    // 选中即写入草稿；autoQuery 面板直接提交，其余面板等用户点查询
    function apply(patch: Partial<CollectionHistoryFilters>) {
      draft.value = { ...draft.value, ...patch };
      if (props.autoQuery) submit();
    }
    function reset() {
      draft.value = createHistoryFilters();
      processes.value = [];
      submit();
    }
    return { t, draft, processes, submit, apply, reset };
  },
  render() {
    const { draft } = this;
    const options = (field: 'target' | 'task_name') =>
      (this.candidates[field] || []).map(item => (
        <Select.Option
          id={String(item.value)}
          key={`${field}:${item.value}`}
          name={item.alias || String(item.value)}
        />
      ));
    // 按任务 ID 进入时该任务名可能不在候选中，补一个选项让任务下拉回显名称
    const taskOptions = () => {
      const items = this.candidates.task_name || [];
      const options = items.map(item => (
        <Select.Option
          id={String(item.value)}
          key={`task_name:${item.value}`}
          name={item.alias || String(item.value)}
        />
      ));
      const name = this.taskName;
      if (draft.task_id && name && !items.some(item => String(item.value) === name)) {
        options.unshift(
          <Select.Option
            id={name}
            key={`task_name:${name}`}
            name={name}
          />
        );
      }
      return options;
    };
    return (
      <div class='collection-history-filters'>
        <label>
          <span>IP</span>
          <Select
            loading={this.loading}
            modelValue={draft.ips}
            allowCreate
            collapseTags
            filterable
            inputSearch
            multiple
            onChange={ips => {
              this.apply({ ips: ips || [] });
            }}
          >
            {options('target')}
          </Select>
        </label>
        <label>
          <span>{this.t('任务')}</span>
          <Select
            loading={this.loading}
            modelValue={draft.task_id ? this.taskName : draft.task_name}
            allowCreate
            filterable
            inputSearch
            onChange={value => {
              // 选择任务名后改为按名称筛选，不再按任务 ID 定位
              this.apply({ task_id: null, task_name: String(value || '') });
            }}
          >
            {taskOptions()}
          </Select>
        </label>
        <label>
          <span>{this.t('进程')}</span>
          <Select
            loading={this.loading}
            modelValue={this.processes}
            multipleMode='tag'
            placeholder={this.t('进程名或 PID')}
            allowCreate
            filterable
            inputSearch
            multiple
            onChange={values => {
              this.processes = values || [];
              this.apply(parseProcessSelection(this.processes));
            }}
          >
            {processCandidateOptions(this.candidates, this.processes).map(option => (
              <Select.Option
                id={option.id}
                key={option.id}
                name={option.name}
              />
            ))}
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
    );
  },
});
