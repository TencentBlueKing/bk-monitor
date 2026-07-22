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

import { Button, Dialog, Input, Popover } from 'bkui-vue';
import { debounce } from 'lodash';
import { useI18n } from 'vue-i18n';

import { type MetricGroupModel, type MetricItemModel, UNGROUP_ID } from '../../types/metric-group';
import GroupSelect from './group-select';
import MetricGroupList, { GROUP_ID_ALL } from './metric-group-list';
import MetricTable from './metric-table';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { MetricGroupPanelOrder } from '../../types/panel-order';

import './group-manage-dialog.scss';
/** 将 groups + metrics 反向转换为 MetricGroupPanelOrder[]（供保存时提交） */
export const convertToOrderData = (
  groups: MetricGroupModel[],
  metrics: MetricItemModel[],
  ungroupTitle: string
): MetricGroupPanelOrder[] => {
  const groupMap = new Map<string, MetricItemModel[]>();
  for (const m of metrics) {
    const list = groupMap.get(m.groupId) ?? [];
    list.push(m);
    groupMap.set(m.groupId, list);
  }

  const orderedIds = [...groups.map(g => g.id), UNGROUP_ID];
  return orderedIds
    .filter(id => groupMap.has(id))
    .map(id => ({
      id,
      title: id === UNGROUP_ID ? ungroupTitle : groups.find(g => g.id === id)?.title || '',
      panels: (groupMap.get(id) ?? []).map(m => ({ id: m.id, title: m.title, hidden: m.hidden })),
    }));
};

export default defineComponent({
  name: 'GroupManageDialog',
  props: {
    /** 是否展示 */
    isShow: {
      type: Boolean,
      default: false,
    },
    /** 后端返回的分组与指标排序配置 */
    orderData: {
      type: Array as PropType<MetricGroupPanelOrder[]>,
      default: () => [],
    },
    submitLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'update:isShow': (_v: boolean) => true,
    success: () => true,
    reset: () => true,
    save: (_value: MetricGroupPanelOrder[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const generateGroupsAndMetrics = (order: MetricGroupPanelOrder[]) => {
      const groups = order.filter(g => g.id !== UNGROUP_ID).map(group => ({ id: group.id, title: group.title }));
      const metrics = order.flatMap(group =>
        group.panels.map(panel => ({ groupId: group.id, id: panel.id, title: panel.title, hidden: panel.hidden }))
      );
      return { groups, metrics };
    };

    // 工作副本：编辑期间不影响已生效数据，保存时再提交
    const localGroups = shallowRef<MetricGroupModel[]>([]);
    const localMetrics = shallowRef<MetricItemModel[]>([]);
    const activeGroupId = shallowRef<string>(GROUP_ID_ALL);
    const selectedIds = shallowRef<string[]>([]);
    const tableKeyword = shallowRef('');
    const deleteGroupShow = shallowRef(false);

    const unGroup = computed(
      () => props.orderData.find(g => g.id === UNGROUP_ID) || { id: UNGROUP_ID, title: t('未分组的指标') }
    );

    watch(
      () => props.isShow,
      show => {
        if (show) {
          const { groups, metrics } = generateGroupsAndMetrics(props.orderData);
          localGroups.value = groups;
          localMetrics.value = metrics;
          activeGroupId.value = GROUP_ID_ALL;
          selectedIds.value = [];
          tableKeyword.value = '';
        }
      }
    );

    /** 「所属分组」下拉可选项（含未分组） */
    const groupOptions = computed(() => [
      ...localGroups.value.map(g => ({ id: g.id, name: g.title })),
      { id: UNGROUP_ID, name: unGroup.value?.title },
    ]);

    /** 当前作用域标题 */
    const scopeTitle = computed(() => {
      if (activeGroupId.value === GROUP_ID_ALL) return t('全部指标');
      if (activeGroupId.value === UNGROUP_ID) return unGroup.value?.title;
      return localGroups.value.find(g => g.id === activeGroupId.value)?.title || '';
    });

    /** 是否为可删除的真实分组 */
    const isRealGroup = computed(() => activeGroupId.value !== GROUP_ID_ALL && activeGroupId.value !== UNGROUP_ID);

    const handleTableKeywordChange = (keyword: string) => {
      tableKeyword.value = keyword;
    };

    const handleTableKeywordChangeDebounced = debounce(handleTableKeywordChange, 200);

    /** 表格当前展示行 */
    const scopedRows = computed(() => {
      let list = localMetrics.value;
      if (activeGroupId.value !== GROUP_ID_ALL) {
        list = list.filter(m => m.groupId === activeGroupId.value);
      }
      const key = tableKeyword.value.trim().toLowerCase();
      if (key) list = list.filter(m => m.title.toLowerCase().includes(key));
      return list;
    });

    /** 仅在未做关键字筛选时允许拖拽，避免顺序歧义 */
    const draggable = computed(() => !tableKeyword.value.trim());

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
    };

    const handleAddGroup = (name: string) => {
      const group: MetricGroupModel = { id: `group_${Date.now()}`, title: name };
      localGroups.value = [...localGroups.value, group];
    };

    const handleReorderGroups = (next: MetricGroupModel[]) => {
      localGroups.value = next;
    };

    /** 全局点击事件，关闭所有操作弹窗 */
    const documentClickFn = () => {
      deleteGroupShow.value = false;
    };
    const handleDeleteGroupShowChange = (show: boolean) => {
      deleteGroupShow.value = show;
      if (show) {
        document.addEventListener('click', documentClickFn);
      } else {
        document.removeEventListener('click', documentClickFn);
      }
    };

    const handleDeleteGroup = () => {
      const target = activeGroupId.value;
      localMetrics.value = localMetrics.value.map(m => (m.groupId === target ? { ...m, groupId: UNGROUP_ID } : m));
      localGroups.value = localGroups.value.filter(g => g.id !== target);
      activeGroupId.value = GROUP_ID_ALL;
    };

    const handleClose = () => emit('update:isShow', false);

    const handleSave = () => {
      emit('save', convertToOrderData(localGroups.value, localMetrics.value, unGroup.value.title));
    };

    const handleReset = () => {
      emit('reset');
    };

    const renderFooter = () => (
      <div class='group-manage-dialog-footer'>
        <Button
          loading={props.submitLoading}
          theme='primary'
          onClick={handleSave}
        >
          {t('保存')}
        </Button>
        <Button
          loading={props.submitLoading}
          onClick={handleReset}
        >
          {t('恢复默认')}
        </Button>
        <Button onClick={handleClose}>{t('取消')}</Button>
      </div>
    );

    return () => (
      <Dialog
        width={960}
        class='group-manage-dialog'
        v-slots={{ footer: renderFooter }}
        isShow={props.isShow}
        title={t('视图分组管理')}
        onClosed={handleClose}
      >
        <div class='group-manage-dialog-content'>
          <div class='group-manage-wrap'>
            <MetricGroupList
              activeGroupId={activeGroupId.value}
              groups={localGroups.value}
              metrics={localMetrics.value}
              onAddGroup={handleAddGroup}
              onChange={(id: string) => (activeGroupId.value = id)}
              onReorder={handleReorderGroups}
            />
          </div>
          <div class='group-metric-wrap'>
            <div class='group-metric-wrap-header'>
              <span class='group-title'>{scopeTitle.value}</span>
              {isRealGroup.value && (
                <Popover
                  width={320}
                  v-slots={{
                    content: () => (
                      <div class='delete-host-group-confirm-popover-content'>
                        <div class='delete-host-group-info'>
                          <div class='info-icon'>
                            <i class='icon-monitor icon-mc-chart-alert' />
                          </div>
                          <div class='info-text'>
                            <div class='group-delete-title'>{t('确认删除该分组？')}</div>
                            <div class='group-delete-name'>
                              {t('分组名称')}：{scopeTitle.value}
                            </div>
                            <div class='group-delete-tip'>
                              {t('分组删除后，相关指标将被移动到 <{name}>', { name: t(unGroup.value.title) })}
                            </div>
                          </div>
                        </div>
                        <div class='delete-host-group-btns'>
                          <Button
                            size='small'
                            theme='primary'
                            onClick={handleDeleteGroup}
                          >
                            {t('删除')}
                          </Button>
                          <Button
                            size='small'
                            outline
                            onClick={e => {
                              e.stopPropagation();
                              handleDeleteGroupShowChange(false);
                            }}
                          >
                            {t('取消')}
                          </Button>
                        </div>
                      </div>
                    ),
                  }}
                  isShow={deleteGroupShow.value}
                  theme='light delete-host-group-confirm-popover'
                  trigger='manual'
                >
                  <Button
                    size='small'
                    theme='danger'
                    outline
                    onClick={e => {
                      e.stopPropagation();
                      handleDeleteGroupShowChange(true);
                    }}
                  >
                    {t('删除分组')}
                  </Button>
                </Popover>
              )}
            </div>
            <div class='group-metric-wrap-operations'>
              <GroupSelect
                disabled={!selectedIds.value.length}
                groupOptions={groupOptions.value}
                onAddGroup={handleAddGroup}
                onChange={handleBatchMove}
              >
                {{
                  trigger: () => (
                    <Button
                      disabled={!selectedIds.value.length}
                      outline
                    >
                      <span>{t('批量移动至')}</span>
                      <i class='icon-monitor icon-arrow-down' />
                    </Button>
                  ),
                }}
              </GroupSelect>
              <Input
                class='group-metric-search'
                modelValue={tableKeyword.value}
                placeholder={t('搜索 指标名称')}
                type='search'
                clearable
                onClear={() => {
                  tableKeyword.value = '';
                }}
                onInput={handleTableKeywordChangeDebounced}
              />
            </div>
            <div class='group-metric-wrap-table'>
              <MetricTable
                draggable={draggable.value}
                groupOptions={groupOptions.value}
                rows={scopedRows.value}
                selectedIds={selectedIds.value}
                onAddGroup={handleAddGroup}
                onChangeGroup={handleChangeGroup}
                onDragSort={handleDragSort}
                onSelectChange={(ids: string[]) => (selectedIds.value = ids)}
                onToggleHidden={handleToggleHidden}
              >
                {{
                  empty: () => (
                    <EmptyStatus
                      type={tableKeyword.value ? 'search-empty' : 'empty'}
                      onOperation={() => {
                        tableKeyword.value = '';
                      }}
                    />
                  ),
                }}
              </MetricTable>
            </div>
          </div>
        </div>
      </Dialog>
    );
  },
});
