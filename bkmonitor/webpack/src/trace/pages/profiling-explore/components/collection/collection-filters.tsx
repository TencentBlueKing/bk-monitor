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

import { Button, Radio, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import {
  createHistoryFilters,
  parseProcessSelection,
  processCandidateOptions,
  restoreProcessSelection,
} from '../../utils/collection-history';
import CollectionExecutionStatus from './collection-execution-status';

import type {
  CollectionCandidate,
  CollectionCandidateField,
  CollectionHistoryFilters,
} from '../../types/collection-history';

// Radio 的 Boolean 优先类型会把空字符串转成 true，仅在界面使用非空值。
const ALL_STATUS = 'all';

export default defineComponent({
  name: 'CollectionFilters',
  props: {
    filters: { type: Object as PropType<CollectionHistoryFilters>, required: true },
    candidates: {
      type: Object as PropType<Partial<Record<CollectionCandidateField, CollectionCandidate[]>>>,
      required: true,
    },
    loading: Boolean,
    results: Boolean,
    // 选中筛选值后立即查询，无须再点查询按钮
    autoQuery: Boolean,
    // 表格列已提供状态筛选时，面板内不再重复展示
    statusFilter: { type: Boolean, default: true },
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
      (this.candidates[field] || []).map((item, index) => (
        <Select.Option
          id={String(item.value)}
          key={`${field}:${index}`}
          name={item.alias || String(item.value)}
        />
      ));
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
            modelValue={draft.task_name}
            allowCreate
            filterable
            inputSearch
            onChange={value => {
              this.apply({ task_name: String(value || '') });
            }}
          >
            {options('task_name')}
          </Select>
        </label>
        <label>
          <span>{this.t('进程')}</span>
          <Select
            loading={this.loading}
            modelValue={this.processes}
            placeholder={this.t('进程名或 PID')}
            allowCreate
            collapseTags
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
        {this.statusFilter && (
          <div class='collection-history-status-filter'>
            <span>{this.t('状态')}</span>
            <Radio.Group
              class='collection-history-status-options'
              modelValue={draft.status || ALL_STATUS}
              type='capsule'
              onChange={status => {
                this.draft = { ...draft, status: status === ALL_STATUS ? '' : String(status) };
              }}
            >
              {(this.results
                ? ['', 'running', 'succeed', 'outdate']
                : ['', 'running', 'succeed', 'partial_succeed', 'failed']
              ).map(status => (
                <Radio.Button
                  key={status || ALL_STATUS}
                  v-tippy={this.t('选择状态后点击查询生效')}
                  label={status || ALL_STATUS}
                >
                  {status ? (
                    <CollectionExecutionStatus
                      result={this.results}
                      status={status}
                    />
                  ) : (
                    this.t('全部')
                  )}
                </Radio.Button>
              ))}
            </Radio.Group>
          </div>
        )}
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
