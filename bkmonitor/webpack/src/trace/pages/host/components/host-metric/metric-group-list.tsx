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

import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Input, PopConfirm } from 'bkui-vue';
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
    const newGroupName = shallowRef('');
    /** 拖拽起始下标 */
    const dragIndex = shallowRef(-1);

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
    const renderGroups = computed(() => {
      const key = searchKey.value.trim().toLowerCase();
      if (!key) return props.groups;
      return props.groups.filter(g => g.title.toLowerCase().includes(key));
    });

    const handleAddConfirm = () => {
      const name = newGroupName.value.trim();
      if (!name) return;
      emit('addGroup', name);
      newGroupName.value = '';
    };

    /** 拖拽排序（仅真实分组，未受搜索影响时才允许） */
    const handleDrop = (targetIndex: number) => {
      const from = dragIndex.value;
      dragIndex.value = -1;
      if (from < 0 || from === targetIndex) return;
      const next = [...props.groups];
      const [moved] = next.splice(from, 1);
      next.splice(targetIndex, 0, moved);
      emit('reorder', next);
    };

    const renderCount = (count: { hidden: number; visible: number }) => (
      <div class='metric-group-list__count'>
        <span class='metric-group-list__count-item'>
          <i class='icon-monitor icon-mc-visual' />
          {count.visible}
        </span>
        <span class='metric-group-list__count-item'>
          <i class='icon-monitor icon-mc-invisible' />
          {count.hidden}
        </span>
      </div>
    );

    const draggable = computed(() => !searchKey.value.trim());

    return () => (
      <div class='metric-group-list'>
        <div
          class={['metric-group-list__item', 'is-all', { 'is-active': props.activeGroupId === GROUP_ID_ALL }]}
          onClick={() => emit('change', GROUP_ID_ALL)}
        >
          <i class='icon-monitor icon-all metric-group-list__flag' />
          <span class='metric-group-list__name'>{t('全部指标')}</span>
          {renderCount(allCount.value)}
        </div>
        <div class='metric-group-list__filter'>
          <PopConfirm
            width={280}
            v-slots={{
              content: () => (
                <div class='metric-group-list__add-form'>
                  <div class='metric-group-list__add-title'>{t('新建分组')}</div>
                  <Input
                    v-model={newGroupName.value}
                    placeholder={t('请输入分组名称')}
                  />
                </div>
              ),
            }}
            trigger='click'
            onConfirm={handleAddConfirm}
          >
            <div class='metric-group-list__add-btn'>
              <i class='icon-monitor icon-mc-add' />
            </div>
          </PopConfirm>
          <Input
            v-model={searchKey.value}
            placeholder={t('搜索 指标分组')}
            type='search'
          />
        </div>
        <div class='metric-group-list__custom'>
          {renderGroups.value.map((group, index) => (
            <div
              key={group.id}
              class={['metric-group-list__item', { 'is-active': props.activeGroupId === group.id }]}
              draggable={draggable.value}
              onClick={() => emit('change', group.id)}
              onDragover={(e: DragEvent) => e.preventDefault()}
              onDragstart={() => (dragIndex.value = index)}
              onDrop={() => handleDrop(index)}
            >
              {draggable.value && <i class='icon-monitor icon-mc-tuozhuai metric-group-list__drag' />}
              <span
                class='metric-group-list__name'
                v-bk-tooltips={{ content: group.title, delay: 300 }}
              >
                {group.title}
              </span>
              {renderCount(countOf(group.id))}
            </div>
          ))}
        </div>
        <div
          class={['metric-group-list__item', 'is-ungroup', { 'is-active': props.activeGroupId === UNGROUP_ID }]}
          onClick={() => emit('change', UNGROUP_ID)}
        >
          <span class='metric-group-list__name'>{t('未分组的指标')}</span>
          {renderCount(ungroupCount.value)}
        </div>
      </div>
    );
  },
});
