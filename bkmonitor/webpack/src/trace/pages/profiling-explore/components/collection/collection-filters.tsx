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

import { Alert, Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { createHistoryFilters, parseProcessSelection } from '../../utils/collection-history';
import CollectionSingleSelect from './collection-single-select';
import CollectionValueTagSelector from './collection-value-tag-selector';

import type { SelectionRange } from '../../types';
import type { CollectionHistoryFilters } from '../../types/collection-history';

import './collection-filters.scss';

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
    // IP、进程、任务的候选值都由各自的选择器加载
    const ipError = shallowRef(false);
    const processError = shallowRef(false);
    const taskError = shallowRef(false);
    // 已选值按候选字段分组传给新选择器，PID 的前缀由选择器内部维护
    const ipValue = computed(() => [{ field: 'target' as const, values: draft.value.ips }]);
    const processValue = computed(() => [
      { field: 'process_names' as const, values: draft.value.process_names },
      { field: 'process_pids' as const, values: draft.value.process_pids },
    ]);
    function setIpError(hasError: boolean) {
      if (ipError.value !== hasError) ipError.value = hasError;
    }
    function setProcessError(hasError: boolean) {
      if (processError.value !== hasError) processError.value = hasError;
    }
    function setTaskError(hasError: boolean) {
      if (taskError.value !== hasError) taskError.value = hasError;
    }
    // 任一候选接口失败即提示，具体文案由渲染层提供
    const candidateError = computed(() => ipError.value || processError.value || taskError.value);
    // 重试时清掉失败标记并递增版本号，强制重挂选择器重新预加载、重新拉取候选
    const revision = shallowRef(0);
    function reloadCandidates() {
      ipError.value = false;
      processError.value = false;
      taskError.value = false;
      revision.value += 1;
    }
    // 外部筛选变化时同步草稿
    watch(
      () => props.filters,
      value => {
        draft.value = { ...value };
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
      submit();
    }
    return {
      t,
      draft,
      ipError,
      processError,
      taskError,
      ipValue,
      processValue,
      setIpError,
      setProcessError,
      setTaskError,
      candidateError,
      revision,
      reloadCandidates,
      submit,
      apply,
      reset,
    };
  },
  render() {
    const { draft } = this;
    return (
      <>
        <div class='collection-history-filters'>
          <div class='collection-history-filter-item'>
            <span>IP</span>
            <CollectionValueTagSelector
              key={this.revision}
              bizId={this.bizId}
              fields={['target']}
              range={this.range}
              value={this.ipValue}
              onChange={ips => this.apply({ ips })}
              onError={this.setIpError}
            />
          </div>
          <div class='collection-history-filter-item'>
            <span>{this.t('任务')}</span>
            <CollectionSingleSelect
              key={this.revision}
              bizId={this.bizId}
              modelValue={draft.task_id ? this.taskName : draft.task_name}
              placeholder={this.t('请选择')}
              range={this.range}
              onChange={value => {
                // 选择任务名后改为按名称筛选，不再按任务 ID 定位
                this.apply({ task_id: null, task_name: value });
              }}
              onError={this.setTaskError}
            />
          </div>
          <div class='collection-history-filter-item'>
            <span>{this.t('进程')}</span>
            <CollectionValueTagSelector
              key={this.revision}
              bizId={this.bizId}
              fields={['process_names', 'process_pids']}
              placeholder={this.t('进程名或 PID')}
              range={this.range}
              value={this.processValue}
              onChange={values => {
                this.apply(parseProcessSelection(values));
              }}
              onError={this.setProcessError}
            />
          </div>
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
