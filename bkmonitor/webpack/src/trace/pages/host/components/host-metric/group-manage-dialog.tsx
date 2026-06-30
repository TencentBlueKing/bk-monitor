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

import { Button, Dialog, Input, PopConfirm, Select } from 'bkui-vue';
import { cloneDeep } from 'lodash';
import { useI18n } from 'vue-i18n';

import { MOCK_METRIC_GROUPS, MOCK_METRICS } from '../../mock/metric-groups';
import { type MetricGroupModel, type MetricItemModel, UNGROUP_ID } from '../../types/metric-group';
import MetricGroupList, { GROUP_ID_ALL } from './metric-group-list';
import MetricTable, { type HiddenFilter } from './metric-table';

import './group-manage-dialog.scss';

export default defineComponent({
  name: 'GroupManageDialog',
  props: {
    /** 是否展示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 已生效的分组 */
    groups: {
      type: Array as PropType<MetricGroupModel[]>,
      default: () => [],
    },
    /** 已生效的指标 */
    metrics: {
      type: Array as PropType<MetricItemModel[]>,
      default: () => [],
    },
  },
  emits: {
    save: (_groups: MetricGroupModel[], _metrics: MetricItemModel[]) => true,
    'update:isShow': (_v: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    // 工作副本：编辑期间不影响已生效数据，保存时再提交
    const localGroups = shallowRef<MetricGroupModel[]>([]);
    const localMetrics = shallowRef<MetricItemModel[]>([]);
    const activeGroupId = shallowRef<string>(GROUP_ID_ALL);
    const selectedIds = shallowRef<string[]>([]);
    const tableKeyword = shallowRef('');
    const hiddenFilter = shallowRef<HiddenFilter>('all');
    const moveTargetValue = shallowRef('');

    watch(
      () => props.isShow,
      show => {
        if (show) {
          localGroups.value = cloneDeep(props.groups);
          localMetrics.value = cloneDeep(props.metrics);
          activeGroupId.value = GROUP_ID_ALL;
          selectedIds.value = [];
          tableKeyword.value = '';
          hiddenFilter.value = 'all';
          moveTargetValue.value = '';
        }
      }
    );

    /** 「所属分组」下拉可选项（含未分组） */
    const groupOptions = computed(() => [
      ...localGroups.value.map(g => ({ id: g.id, name: g.title })),
      { id: UNGROUP_ID, name: t('未分组的指标') },
    ]);

    /** 当前作用域标题 */
    const scopeTitle = computed(() => {
      if (activeGroupId.value === GROUP_ID_ALL) return t('全部指标');
      if (activeGroupId.value === UNGROUP_ID) return t('未分组的指标');
      return localGroups.value.find(g => g.id === activeGroupId.value)?.title || '';
    });

    /** 是否为可删除的真实分组 */
    const isRealGroup = computed(() => activeGroupId.value !== GROUP_ID_ALL && activeGroupId.value !== UNGROUP_ID);

    /** 表格当前展示行 */
    const scopedRows = computed(() => {
      let list = localMetrics.value;
      if (activeGroupId.value !== GROUP_ID_ALL) {
        list = list.filter(m => m.groupId === activeGroupId.value);
      }
      const key = tableKeyword.value.trim().toLowerCase();
      if (key) list = list.filter(m => m.title.toLowerCase().includes(key));
      if (hiddenFilter.value === 'visible') list = list.filter(m => !m.hidden);
      if (hiddenFilter.value === 'hidden') list = list.filter(m => m.hidden);
      return list;
    });

    /** 仅在未做关键字/显示筛选时允许拖拽，避免顺序歧义 */
    const draggable = computed(() => !tableKeyword.value.trim() && hiddenFilter.value === 'all');

    const updateMetric = (id: string, patch: Partial<MetricItemModel>) => {
      localMetrics.value = localMetrics.value.map(m => (m.id === id ? { ...m, ...patch } : m));
    };

    const handleToggleHidden = (payload: { hidden: boolean; id: string }) => {
      updateMetric(payload.id, { hidden: payload.hidden });
    };

    const handleChangeGroup = (payload: { groupId: string; id: string }) => {
      updateMetric(payload.id, { groupId: payload.groupId });
    };

    const handleDragSort = (newRows: MetricItemModel[]) => {
      if (activeGroupId.value === GROUP_ID_ALL) {
        localMetrics.value = newRows;
        return;
      }
      // 单分组作用域：用新顺序回填该分组在全局数组中的占位，保持其它分组位置不变
      const queue = [...newRows];
      localMetrics.value = localMetrics.value.map(m =>
        m.groupId === activeGroupId.value ? (queue.shift() as MetricItemModel) : m
      );
    };

    const handleBatchMove = (groupId: string) => {
      if (!groupId || !selectedIds.value.length) return;
      const ids = new Set(selectedIds.value);
      localMetrics.value = localMetrics.value.map(m => (ids.has(m.id) ? { ...m, groupId } : m));
      selectedIds.value = [];
      moveTargetValue.value = '';
    };

    const handleAddGroup = (name: string) => {
      const group: MetricGroupModel = { id: `group_${Date.now()}`, title: name };
      localGroups.value = [...localGroups.value, group];
    };

    const handleReorderGroups = (next: MetricGroupModel[]) => {
      localGroups.value = next;
    };

    const handleDeleteGroup = () => {
      const target = activeGroupId.value;
      localMetrics.value = localMetrics.value.map(m => (m.groupId === target ? { ...m, groupId: UNGROUP_ID } : m));
      localGroups.value = localGroups.value.filter(g => g.id !== target);
      activeGroupId.value = GROUP_ID_ALL;
    };

    const handleClose = () => emit('update:isShow', false);

    const handleSave = () => {
      emit('save', cloneDeep(localGroups.value), cloneDeep(localMetrics.value));
      handleClose();
    };

    const handleReset = () => {
      localGroups.value = cloneDeep(MOCK_METRIC_GROUPS);
      localMetrics.value = cloneDeep(MOCK_METRICS);
      activeGroupId.value = GROUP_ID_ALL;
      selectedIds.value = [];
    };

    const renderFooter = () => (
      <div class='group-manage-dialog__footer'>
        <Button
          theme='primary'
          onClick={handleSave}
        >
          {t('保存')}
        </Button>
        <Button onClick={handleReset}>{t('恢复默认')}</Button>
        <Button onClick={handleClose}>{t('取消')}</Button>
      </div>
    );

    return () => (
      <Dialog
        width={960}
        v-slots={{ footer: renderFooter }}
        isShow={props.isShow}
        title={t('视图分组管理')}
        onClosed={handleClose}
      >
        <div class='group-manage-dialog'>
          <div class='group-manage-dialog__aside'>
            <MetricGroupList
              activeGroupId={activeGroupId.value}
              groups={localGroups.value}
              metrics={localMetrics.value}
              onAddGroup={handleAddGroup}
              onChange={(id: string) => (activeGroupId.value = id)}
              onReorder={handleReorderGroups}
            />
          </div>
          <div class='group-manage-dialog__main'>
            <div class='group-manage-dialog__header'>
              <span class='group-manage-dialog__title'>{scopeTitle.value}</span>
              {isRealGroup.value && (
                <PopConfirm
                  width={320}
                  v-slots={{
                    content: () => (
                      <div class='group-manage-dialog__delete-confirm'>
                        <div class='group-manage-dialog__delete-title'>{t('确认删除该分组？')}</div>
                        <div class='group-manage-dialog__delete-name'>
                          {t('分组名称')}：{scopeTitle.value}
                        </div>
                        <div class='group-manage-dialog__delete-tip'>
                          {t('分组删除后，相关指标将被移动到 <未分组的指标>')}
                        </div>
                      </div>
                    ),
                  }}
                  trigger='click'
                  onConfirm={handleDeleteGroup}
                >
                  <Button
                    size='small'
                    theme='danger'
                  >
                    {t('删除分组')}
                  </Button>
                </PopConfirm>
              )}
            </div>
            <div class='group-manage-dialog__operations'>
              <Select
                class='group-manage-dialog__batch-move'
                disabled={!selectedIds.value.length}
                modelValue={moveTargetValue.value}
                placeholder={t('批量移动至')}
                onChange={handleBatchMove}
              >
                {groupOptions.value.map(item => (
                  <Select.Option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  />
                ))}
              </Select>
              <Input
                class='group-manage-dialog__search'
                v-model={tableKeyword.value}
                placeholder={t('搜索 指标名称')}
                type='search'
                clearable
              />
            </div>
            <MetricTable
              draggable={draggable.value}
              groupOptions={groupOptions.value}
              hiddenFilter={hiddenFilter.value}
              rows={scopedRows.value}
              selectedIds={selectedIds.value}
              onChangeGroup={handleChangeGroup}
              onDragSort={handleDragSort}
              onHiddenFilterChange={(v: HiddenFilter) => (hiddenFilter.value = v)}
              onSelectChange={(ids: string[]) => (selectedIds.value = ids)}
              onToggleHidden={handleToggleHidden}
            />
          </div>
        </div>
      </Dialog>
    );
  },
});
