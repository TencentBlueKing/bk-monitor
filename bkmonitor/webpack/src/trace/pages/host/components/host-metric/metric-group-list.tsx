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

import { type PropType, computed, defineComponent, shallowRef, TransitionGroup, watch } from 'vue';

import { useThrottleFn } from '@vueuse/core';
import { Button, Input, Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { type MetricGroupModel, type MetricItemModel, UNGROUP_ID } from '../../types/metric-group';

import './metric-group-list.scss';

/** 「全部指标」虚拟分组 id */
export const GROUP_ID_ALL = 'all';

export default defineComponent({
  name: 'MetricGroupList',
  props: {
    /** 真实分组列表（可拖拽排序，不含未分组） */
    groups: {
      type: Array as PropType<MetricGroupModel[]>,
      default: () => [],
    },
    /** 全部指标（用于统计可见/隐藏数量） */
    metrics: {
      type: Array as PropType<MetricItemModel[]>,
      default: () => [],
    },
    /** 当前选中分组 id */
    activeGroupId: {
      type: String,
      default: GROUP_ID_ALL,
    },
  },
  emits: {
    addGroup: (_name: string) => true,
    change: (_id: string) => true,
    reorder: (_groups: MetricGroupModel[]) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const searchKey = shallowRef('');
    const addGroupPopoverShow = shallowRef(false);
    const newGroupName = shallowRef('');
    const addGroupMessage = shallowRef('');
    /** 用于实时拖拽展示的本地分组副本 */
    const displayGroups = shallowRef<MetricGroupModel[]>([]);
    const isDragging = shallowRef(false);
    const draggingGroupId = shallowRef('');
    const targetGroupId = shallowRef('');

    watch(
      () => props.groups,
      groups => {
        if (!isDragging.value) {
          displayGroups.value = [...groups];
        }
      },
      { immediate: true }
    );

    /** 统计某分组的可见/隐藏数量；scope 为 'all' 时统计全部 */
    const countOf = (scope: string) => {
      const list = scope === GROUP_ID_ALL ? props.metrics : props.metrics.filter(m => m.groupId === scope);
      return {
        visible: list.filter(m => !m.hidden).length,
        hidden: list.filter(m => m.hidden).length,
      };
    };

    const allCount = computed(() => countOf(GROUP_ID_ALL));
    const ungroupCount = computed(() => countOf(UNGROUP_ID));

    /** 按搜索过滤后的分组 */
    const filteredGroups = computed(() => {
      const key = searchKey.value.trim().toLowerCase();
      if (!key) return displayGroups.value;
      return displayGroups.value.filter(g => g.title.toLowerCase().includes(key));
    });

    /** 全局点击事件，关闭所有操作弹窗 */
    const documentClickFn = () => {
      addGroupPopoverShow.value = false;
    };

    const handleAddGroupShowChange = (show: boolean) => {
      addGroupPopoverShow.value = show;
      if (!show) {
        newGroupName.value = '';
        addGroupMessage.value = '';
        document.removeEventListener('click', documentClickFn);
      } else {
        document.addEventListener('click', documentClickFn);
      }
    };

    const handleAddConfirm = () => {
      const name = newGroupName.value.trim();
      if (!name) {
        addGroupMessage.value = t('分组名称不能为空');
        return;
      }
      emit('addGroup', name);
      handleAddGroupShowChange(false);
    };

    /** 实时交换分组位置 */
    const transformGroupPosition = () => {
      if (!draggingGroupId.value || !targetGroupId.value || draggingGroupId.value === targetGroupId.value) {
        return;
      }
      const list = [...displayGroups.value];
      const sourceIndex = list.findIndex(g => g.id === draggingGroupId.value);
      const targetIndex = list.findIndex(g => g.id === targetGroupId.value);
      if (sourceIndex === -1 || targetIndex === -1 || sourceIndex === targetIndex) return;

      const [moved] = list.splice(sourceIndex, 1);
      list.splice(targetIndex, 0, moved);
      displayGroups.value = list;
      emit('reorder', list);
    };

    const throttleTransformGroupPosition = useThrottleFn(transformGroupPosition, 100);

    const handleDragstart = (e: DragEvent, groupId: string) => {
      isDragging.value = true;
      draggingGroupId.value = groupId;
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', groupId);
      (e.target as HTMLElement)?.classList.add('dragging');
    };

    const handleDragover = (e: DragEvent, groupId: string) => {
      if (!draggingGroupId.value || !isDragging.value) return;
      targetGroupId.value = groupId;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      throttleTransformGroupPosition();
    };

    const handleDragend = (e: DragEvent) => {
      transformGroupPosition();
      (e.target as HTMLElement)?.classList.remove('dragging');
      isDragging.value = false;
      draggingGroupId.value = '';
      targetGroupId.value = '';
    };

    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
    };

    const renderCount = (count: { hidden: number; visible: number }) => (
      <div class='metric-group-list-count'>
        <span class='metric-group-list-count-item'>
          <i class='icon-monitor icon-mc-visual' />
          {count.visible}
        </span>
        <span class='metric-group-list-count-item'>
          <i class='icon-monitor icon-mc-invisible' />
          {count.hidden}
        </span>
      </div>
    );

    const draggable = computed(() => !searchKey.value.trim());

    return () => (
      <div class='metric-group-list'>
        <div class='all-metric-group'>
          <div
            class={['metric-group-list-item', { 'is-active': props.activeGroupId === GROUP_ID_ALL }]}
            onClick={() => emit('change', GROUP_ID_ALL)}
          >
            <i class='icon-monitor icon-all metric-group-list-flag' />
            <span class='metric-group-list-name'>{t('全部指标')}</span>
            {renderCount(allCount.value)}
          </div>
        </div>

        <div class='metric-group-list-filter'>
          <Popover
            width={280}
            v-slots={{
              content: () => (
                <div class='add-host-group-popover-content'>
                  <div class='add-host-group-form'>
                    <div class='metric-group-list-add-title'>{t('新建分组')}</div>
                    <div class='form-label required'>{t('分组名称')}</div>
                    <Input
                      v-model={newGroupName.value}
                      placeholder={t('请输入分组名称')}
                    />
                    {addGroupMessage.value && <span class='err-msg'>{addGroupMessage.value}</span>}
                  </div>
                  <div class='add-host-group-btns'>
                    <Button
                      size='small'
                      theme='primary'
                      onClick={handleAddConfirm}
                    >
                      {t('确定')}
                    </Button>
                    <Button
                      size='small'
                      outline
                      onClick={e => {
                        e.stopPropagation();
                        handleAddGroupShowChange(false);
                      }}
                    >
                      {t('取消')}
                    </Button>
                  </div>
                </div>
              ),
            }}
            arrow={true}
            isShow={addGroupPopoverShow.value}
            theme='light add-host-group-popover'
            trigger='manual'
          >
            <div
              class='metric-group-list-add-btn'
              onClick={e => {
                e.stopPropagation();
                handleAddGroupShowChange(true);
              }}
            >
              <i class='icon-monitor icon-plus-line' />
            </div>
          </Popover>
          <Input
            v-model={searchKey.value}
            placeholder={t('搜索 指标分组')}
            type='search'
            clearable
          />
        </div>
        <div class={['metric-group-list-custom', { 'is-dragging': isDragging.value }]}>
          <TransitionGroup
            class='metric-group-list-transition'
            name={draggable.value ? 'drag' : ''}
            tag='div'
          >
            {filteredGroups.value.map(group => (
              <div
                key={group.id}
                class={['metric-group-list-item', { 'is-active': props.activeGroupId === group.id }]}
                draggable={draggable.value}
                onClick={() => emit('change', group.id)}
                onDragend={handleDragend}
                onDragover={(e: DragEvent) => handleDragover(e, group.id)}
                onDragstart={(e: DragEvent) => handleDragstart(e, group.id)}
                onDrop={handleDrop}
              >
                {draggable.value && <i class='icon-monitor icon-mc-tuozhuai metric-group-list-drag' />}
                <span
                  class='metric-group-list-name'
                  v-overflow-tips={{ content: group.title, delay: 300 }}
                >
                  {group.title}
                </span>
                {renderCount(countOf(group.id))}
              </div>
            ))}
          </TransitionGroup>
          <div
            class={['metric-group-list-item', 'is-ungroup', { 'is-active': props.activeGroupId === UNGROUP_ID }]}
            onClick={() => emit('change', UNGROUP_ID)}
          >
            <span class='metric-group-list-name'>{t('未分组的指标')}</span>
            {renderCount(ungroupCount.value)}
          </div>
        </div>
      </div>
    );
  },
});
