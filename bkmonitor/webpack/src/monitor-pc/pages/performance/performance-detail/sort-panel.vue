<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
-->
<template>
  <performance-dialog
    :class="[{ 'not-dialog': isNotDialog }, { nochecked: !isGroupsChecked }]"
    :title="$t('视图排序')"
    :value="value"
    :ok-text="$t('保存')"
    :cancel-text="$t('重置')"
    :loading="loading"
    @change="handleDialogValueChange"
    @cancel="handleReset"
    @undo="handleUndo"
    @confirm="handleSave"
  >
    <div
      v-if="needGroup && !isNotDialog"
      :class="['create-group', { edit: !showCreateBtn }]"
    >
      <template v-if="showCreateBtn">
        <i class="icon-monitor icon-mc-add" />
        <bk-button
          class="ml5 create-btn"
          text
          @click="handleCreateGroup"
        >
          {{ $t('创建分组') }}
        </bk-button>
      </template>
      <template v-else>
        <bk-input
          ref="groupInput"
          v-model="newGroupName"
          :maxlength="30"
          @enter="() => handleSaveNewGroup(false)"
        />
        <i
          class="ml5 bk-icon icon-check-1"
          @click="() => handleSaveNewGroup(false)"
        />
        <i
          class="ml5 icon-monitor icon-mc-close"
          @click="showCreateBtn = true"
        />
      </template>
    </div>
    <template v-for="(group, index) in groups">
      <bk-collapse
        v-if="needGroup"
        :key="group.id"
        v-model="activeName"
      >
        <transition-group
          :name="transitionName"
          tag="div"
        >
          <bk-collapse-item
            :key="group.id"
            class="group-item"
            :class="{ 'is-dragover': dragover.groupId === group.id }"
            :style="{
              'border-top-color': dragover.groupId === group.id ? '#a3c5fd' : index === 0 ? '#f0f1f5' : 'transparent',
            }"
            hide-arrow
            :name="group.id"
            :draggable="group.id !== '__UNGROUP__' && !editId"
            @dragstart.native="handleDragGroupStart(group, $event)"
            @dragend.native="handleDragEnd"
            @dragover.native="handleDragGroupOver(group, $event)"
            @drop.native="group.id !== '__UNGROUP__' && handleGroupDrop(group, $event)"
          >
            <div
              :class="[
                'group-item-title',
                { 'enable-auto-grouping': enableAutoGrouping && group.id !== '__UNGROUP__' },
              ]"
              @mouseenter="handleMouseEnter(group)"
              @mouseleave="handleMouseLeave"
            >
              <div class="title-left">
                <span
                  v-if="group.id !== '__UNGROUP__' && !editId"
                  class="icon-monitor icon-mc-tuozhuai"
                />
                <i
                  v-if="group.id !== '__UNGROUP__' || isNotDialog"
                  :class="['icon-monitor icon-mc-triangle-down', { expand: activeName.includes(group.id) }]"
                />
                <!-- 分组名称 -->
                <span
                  v-if="group.id !== editId"
                  class="ml5 text-ellipsis"
                  :title="group.title"
                  >{{ group.title
                  }}<span style="color: #979ba5">{{
                    group.id === '__UNGROUP__' ? `（${group.panels.length}）` : ''
                  }}</span>
                  <span
                    v-if="enableAutoGrouping && group.id !== '__UNGROUP__'"
                    class="icon-monitor icon-bianji"
                    @click.stop="handleEditGroup(group)"
                  />
                </span>
                <!-- 分组编辑态 -->
                <div
                  v-else
                  class="title-edit"
                  @click.stop="() => {}"
                >
                  <bk-input
                    ref="editGroupInput"
                    :value="group.title"
                    @change="handleGroupNameChange"
                    @enter="handleEditSave(group)"
                  />
                  <i
                    class="ml5 bk-icon icon-check-1"
                    @click="handleEditSave(group)"
                  />
                  <i
                    class="ml5 icon-monitor icon-mc-close"
                    @click="handleEditCancel"
                  />
                </div>
                <!-- 组内显隐统计数 -->
                <span class="hidden-num">
                  <span class="hidden-num-item">
                    <span class="icon-monitor icon-mc-visual" />
                    <span class="num">{{ getHiddenNum(group.panels, false) }}</span>
                  </span>
                  <span class="hidden-num-item">
                    <span class="icon-monitor icon-mc-invisible" />
                    <span class="num">{{ getHiddenNum(group.panels, true) }}</span>
                  </span>
                </span>
                <!-- 匹配规则 -->
                <span
                  v-if="enableAutoGrouping && group.id !== '__UNGROUP__' && group.id !== editId"
                  class="auto-rules"
                >
                  <span class="auto-rules-title">{{ $t('匹配规则') }}</span>
                  <span
                    class="auto-rules-content"
                    @click.stop="() => {}"
                  >
                    <more-list
                      :key="`${group.id}_${JSON.stringify(group.auto_rules)}`"
                      :list="group.auto_rules"
                      @change="value => handleAtuoRulesChange(value, index)"
                    />
                  </span>
                </span>
              </div>
              <!-- 分组操作项（未分组和编辑态时不显示） -->
              <template v-if="group.id !== '__UNGROUP__' && group.id !== editId">
                <div
                  v-show="hoverGroupId === group.id && !isDashboardPanel"
                  class="title-right"
                >
                  <!-- 编辑分组 -->
                  <i
                    class="icon-monitor icon-mc-edit"
                    @click.stop="handleEditGroup(group)"
                  />
                  <!-- 删除分组 -->
                  <i
                    class="ml10 icon-monitor icon-mc-delete-line"
                    @click.stop="handleDeleteGroup(group)"
                  />
                  <!-- 移动分组 -->
                  <i class="ml10 icon-drag" />
                </div>
                <div
                  v-show="isDashboardPanel"
                  class="title-right last-right"
                >
                  <!-- 删除分组 -->
                  <i
                    class="icon-monitor icon-mc-delete-line"
                    @click.stop="handleDeleteGroup(group)"
                  />
                </div>
              </template>
            </div>
            <!-- 分组内容 -->
            <template #content>
              <div
                v-if="false"
                class="group-item-content"
              >
                <transition-group
                  v-if="group.panels.length"
                  :name="transitionName"
                  tag="ul"
                >
                  <li
                    v-for="item in group.panels"
                    :key="item.id"
                    draggable
                    class="content-item"
                    :class="{ 'is-dragover': dragover.itemId === item.id }"
                    @dragstart.stop="handleItemDragStart(item, group, $event)"
                    @dragend.stop="handleDragEnd"
                    @dragover.stop="handleItemDragOver(item, group, $event)"
                    @drop="handleItemDrop(item, group, $event)"
                  >
                    <span>{{ item.title }}</span>
                    <span class="item-operate">
                      <i
                        :class="['icon-monitor', item.visible ? 'icon-mc-visual' : 'icon-mc-invisible-fill']"
                        @click="handleToggleVisible(group, item)"
                      />
                      <i class="ml10 icon-drag" />
                    </span>
                  </li>
                </transition-group>
                <div
                  v-else
                  class="content-empty"
                  @drop="handleItemDrop({}, group, $event)"
                >
                  <i class="icon-monitor icon-mind-fill" />
                  {{ $t('暂无任何视图') }}
                </div>
              </div>
              <sort-drag-list
                :ref="`sortDragList${index}`"
                :class="{ 'is-group': needGroup }"
                :group="group"
                :dragover="dragover"
                :transition-name="transitionName"
                :is-check="isNotDialog"
                :enable-auto-grouping="enableAutoGrouping"
                @drag-start="handleItemDragStart"
                @drag-end="handleDragEnd"
                @drag-over="handleItemDragOver"
                @drop="handleItemDrop"
                @toggle-visible="handleToggleVisible"
                @check-change="handleCheckChange"
              />
            </template>
          </bk-collapse-item>
        </transition-group>
      </bk-collapse>
      <template v-else>
        <sort-drag-list
          :key="group.id"
          :style="{ 'margin-top': index === 0 ? '20px' : '0' }"
          :group="group"
          :dragover="dragover"
          :transition-name="transitionName"
          :is-check="isNotDialog"
          @drag-start="handleItemDragStart"
          @drag-end="handleDragEnd"
          @drag-over="handleItemDragOver"
          @drop="handleItemDrop"
          @toggle-visible="handleToggleVisible"
          @check-change="handleCheckChange"
        />
      </template>
    </template>
  </performance-dialog>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Vue, Watch } from 'vue-property-decorator';

import { deepClone, typeTools } from 'monitor-common/utils/utils';

import MoreList from '../../custom-escalation/more-list.tsx';
import { matchRuleFn } from '../../monitor-k8s/utils';
import PerformanceDialog from '../components/performance-dialog.vue';
import SortDragList from './sort-drag-list.vue';

import type { orderList } from '../../collector-config/collector-view/type';
import type { IDragItem, IGroupItem, IHostGroup } from '../performance-type';

@Component({
  name: 'sort-panel',
  components: {
    PerformanceDialog,
    SortDragList,
    MoreList,
  },
})
export default class SortPanel extends Vue {
  @Model('update-value', { type: Boolean }) readonly value: boolean;
  @Prop({ default: () => [], type: Array }) readonly groupsData: IHostGroup[];
  @Prop({ default: true }) readonly needGroup: boolean;
  @Prop({ default: false }) readonly loading: boolean;
  @Prop({ default: false }) readonly isNotDialog: boolean;
  @Prop({ default: false }) readonly isDashboardPanel: boolean;
  @Prop({ default: () => [], type: Array }) defaultOrderList: orderList[];
  @Prop({ default: false, type: Boolean }) enableAutoGrouping: boolean;

  private groups: IHostGroup[] = [];
  // 当前激活项
  private activeName = ['__UNGROUP__'];
  // 当前编辑的分组ID
  private editId = '';
  // 当前编辑分组的名称
  private curEditName = '';
  // 当前悬浮组的ID
  private hoverGroupId = '';
  // 创建分组
  private showCreateBtn = true;
  // 新分组名
  private newGroupName = '';
  private dragover = {
    groupId: '',
    itemId: '',
  };
  private dragging = {
    groupId: '',
    itemId: '',
  };
  private isDraging = false;
  private dragoverTimer = null;

  private groupsChecked: any[] = [];

  // 拖拽动画
  get transitionName() {
    return this.isDraging ? 'flip-list' : '';
  }
  // 是否选中
  get isGroupsChecked() {
    return this.groupsChecked.some(item => item.panels.length > 0);
  }

  @Watch('groupsData', { immediate: true })
  handleGroupDataChange(v) {
    this.groups = JSON.parse(
      JSON.stringify(
        v.map(item => ({
          ...item,
          id: item.id === '' ? '__UNGROUP__' : item.id,
        }))
      )
    );
  }

  @Emit('reset')
  handleReset() {
    if (!this.enableAutoGrouping) {
      this.handleGroupDataChange(this.groupsData);
    }
  }

  @Emit('save')
  handleSave() {
    return this.groups;
  }
  @Emit('undo')
  handleUndo() {
    if (this.isDashboardPanel) {
      this.$emit('restore');
      return;
    }
    if (this.isNotDialog) {
      this.groups = deepClone(this.defaultOrderList);
    }
    return this.groups;
  }

  @Emit('update-value')
  handleDialogValueChange(v: boolean) {
    return v;
  }

  @Emit('groups-change')
  handleGroupsChange() {
    return this.enableAutoGrouping ? this.groups : this.groups.map(item => ({ id: item.id, title: item.title }));
  }

  @Emit('checked-change')
  emitCheckChange(v) {
    return v;
  }
  @Emit('checked-count')
  handleCheckCount(v) {
    return v;
  }

  handleCheckChange(obj: any) {
    const group = this.groupsChecked.find(item => item.id === obj.id);
    if (group) {
      group.panels = obj.panels;
    } else {
      this.groupsChecked.push(obj);
    }
    const panelsId = new Set();
    this.groupsChecked.forEach(item => {
      item.panels.forEach(panel => {
        panelsId.add(panel.id);
      });
    });
    this.handleCheckCount([...panelsId].length);
    this.emitCheckChange(this.groupsChecked.some(item => item.panels.length > 0));
    this.handleGroupsChange();
  }
  checkedSortSet(id: string) {
    const delIndexList = [];
    const addPanels = [];
    const checkedPanelsObj = {};
    this.groupsChecked.forEach(item => {
      checkedPanelsObj[item.id] = item.panels;
      addPanels.push(...item.panels);
    });
    this.groups.forEach(item => {
      if (checkedPanelsObj?.[item.id]) {
        const panels = checkedPanelsObj[item.id];
        const delIndexObj = { id: item.id, panels: [] };
        panels.forEach(panel => {
          const index = item.panels.findIndex(group => group.id === panel.id);
          index > -1 && delIndexObj.panels.push(index);
        });
        delIndexList.push(delIndexObj);
      }
    });
    delIndexList.forEach(item => {
      const group = this.groups.find(group => group.id === item.id);
      const len = group.panels.length;
      const ids = checkedPanelsObj[item.id].map(obj => obj.id);
      for (let i = len - 1; i >= 0; i--) {
        ids.includes(group.panels[i].id) && group.panels.splice(i, 1);
      }
    });
    const group = this.groups.find(item => item.id === id);
    /* 显示的数据优先放在前面，隐藏的数据优先放在后面  */
    const hiddenAddPanels = addPanels.filter(item => item.hidden);
    const showAddPanels = addPanels.filter(item => !item.hidden);
    group.panels.unshift(...showAddPanels);
    group.panels.push(...hiddenAddPanels);
    // group.panels.push(...addPanels);
    this.groupsChecked = [];
    this.groups.forEach((item, index) => {
      const sortRef: any = this.$refs[`sortDragList${index}`]?.[0];
      sortRef?.clearChecked?.();
    });
    this.emitCheckChange(false);
  }
  /* 加入分组（批量） */
  checkedAddGroup(ids: string[]) {
    const checkedPanelsObj = {};
    const addPanels = [];
    const addPanelsId = new Set();
    const addGroupsId = new Set();
    const addGroupsIdOfChild = new Map();
    this.groupsChecked.forEach(item => {
      addGroupsId.add(item.id);
      checkedPanelsObj[item.id] = item.panels;
      addGroupsIdOfChild.set(
        item.id,
        item.panels.map(p => p.id)
      );
      item.panels.forEach(panel => {
        if (!addPanelsId.has(panel.id)) addPanels.push(panel);
        addPanelsId.add(panel.id);
      });
    });
    const matchFn = (panel, rules) => {
      const targetRules = [];
      rules.forEach(r => {
        if (matchRuleFn(panel.title, rules)) targetRules.push(r);
      });
      return {
        ...panel,
        match_rule: targetRules,
        match_type: targetRules.length ? ['manual', 'auto'] : ['manual'],
      };
    };
    this.groups.forEach(item => {
      if (ids.includes(item.id)) {
        // 只添加
        const targetPanels = [];
        const diffPanels = [];
        const panelsId = new Set(item.panels.map(p => p.id));
        addPanels.forEach(p => {
          if (!panelsId.has(p.id)) {
            diffPanels.push(matchFn(p, item.auto_rules));
          }
        });
        targetPanels.push(...item.panels);
        targetPanels.unshift(...diffPanels);
        targetPanels.forEach(target => {
          if (addPanelsId.has(target.id)) {
            target.match_type = [...new Set(target.match_type.concat(['manual']))];
          }
        });
        item.panels = targetPanels;
      } else if (addGroupsId.has(item.id)) {
        // 只删除
        const targetPanels = [];
        item.panels.forEach(p => {
          if (addGroupsIdOfChild.get(item.id).includes(p.id)) {
            const isHasAuto = p.match_type.includes('auto'); // 不删除
            if (isHasAuto) {
              targetPanels.push(p);
            }
          } else {
            targetPanels.push(p);
          }
        });
        item.panels = targetPanels;
      }
    });
    this.groupsChecked = [];
    this.groups.forEach((item, index) => {
      const sortRef: any = this.$refs[`sortDragList${index}`]?.[0];
      sortRef?.clearChecked?.();
    });
    this.emitCheckChange(false);
  }
  // 分组title悬浮事件
  handleMouseEnter(item: IHostGroup) {
    this.hoverGroupId = item.id;
  }

  handleMouseLeave() {
    this.hoverGroupId = '';
  }
  // 编辑分组
  handleEditGroup(group: IHostGroup) {
    this.editId = group.id;
    this.$nextTick(() => {
      this.$refs.editGroupInput && (this.$refs.editGroupInput[0] as any).focus();
    });
  }

  // 删除分组
  handleDeleteGroup(group: IHostGroup) {
    const index = this.groups.findIndex(data => data.id === group.id);
    if (!group.panels.length) {
      this.groups.splice(index, 1);
      this.handleGroupsChange();
      return;
    }

    let unknownGroupIndex = this.groups.findIndex(data => data.id === '__UNGROUP__');
    if (unknownGroupIndex === -1) {
      const len = this.groups.push({
        id: '__UNGROUP__',
        title: this.$tc('未分组的指标'),
        panels: [],
      });
      unknownGroupIndex = len - 1;
    }
    if (this.enableAutoGrouping) {
      const targetPanels = [];
      const oldPanelIdSet = new Set();
      /* 其他分组已有的无需加入未分组 */
      this.groups.forEach((g, gIndex) => {
        if (gIndex !== index) {
          g.panels.forEach(panel => {
            oldPanelIdSet.add(panel.id);
          });
        }
      });
      group.panels.forEach(panel => {
        if (!oldPanelIdSet.has(panel.id)) {
          targetPanels.push({
            ...panel,
            match_type: ['manual'],
            match_rules: [],
          });
        }
      });
      this.groups[unknownGroupIndex].panels.push(...targetPanels);
    } else {
      this.groups[unknownGroupIndex].panels.push(...group.panels);
    }
    this.groups.splice(index, 1);
    this.$emit('order-list-change', this.groups);
    this.handleGroupsChange();
  }

  // 指标显示和隐藏
  handleToggleVisible(group: IHostGroup, item: IGroupItem) {
    this.isDraging = true;
    const groupData = this.groups.find(data => data.id === group.id);
    const itemData = groupData.panels.find(data => data.id === item.id);
    itemData.hidden = !itemData.hidden;
    setTimeout(() => {
      this.isDraging = false;
    }, 500);
  }
  // 分组拖拽开始事件
  handleDragGroupStart(group: IHostGroup, e: DragEvent) {
    e.dataTransfer.setData('groupId', group.id);
    this.dragging = {
      groupId: group.id,
      itemId: '',
    };
    this.isDraging = true;
  }

  handleDrag(e: DragEvent) {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop;
    if (e.y < 180) {
      window.scrollTo(e.x, scrollTop - 9);
    }
  }
  // 分组拖拽结束事件
  handleDragEnd(e: DragEvent) {
    e.preventDefault();
    setTimeout(() => {
      this.isDraging = false;
      this.handleClearDragData();
    }, 500);
  }

  handleDragGroupOver(group, e: DragEvent) {
    e.preventDefault();
    if (this.dragover.groupId !== group.id) {
      clearTimeout(this.dragoverTimer);
    }
    this.dragover.groupId = group.id;
    this.dragoverTimer = setTimeout(() => {
      if (!this.activeName.includes(group.id) && this.dragover.groupId === group.id) {
        this.activeName.push(group.id);
      }
    }, 500);
  }

  // 分组拖拽drop事件
  handleGroupDrop(group: IHostGroup, e: DragEvent) {
    e.preventDefault();
    const dragGroupId = e.dataTransfer.getData('groupId');
    if (dragGroupId === group.id) return;

    const dragIndex = this.groups.findIndex(data => data.id === dragGroupId);
    const dropIndex = this.groups.findIndex(data => data.id === group.id);
    if (dragIndex === -1 || dropIndex === -1) return;

    const tmp = this.groups.splice(dragIndex, 1);
    this.groups.splice(dropIndex, 0, tmp[0]);
    this.handleClearDragData();
    this.handleGroupsChange();
  }
  handleClearDragData() {
    this.dragover = {
      groupId: '',
      itemId: '',
    };
    this.dragging = {
      groupId: '',
      itemId: '',
    };
  }
  // 指标项拖拽开始事件
  handleItemDragStart(item, group: IHostGroup, e: DragEvent) {
    e.dataTransfer.setData(
      'item',
      JSON.stringify({
        itemId: item.id,
        groupId: group.id,
      })
    );
    this.dragging = {
      itemId: item.id,
      groupId: group.id,
    };
    this.isDraging = true;
  }
  handleItemDragOver(item, group: IHostGroup, e: DragEvent) {
    e.preventDefault();
    this.dragover.groupId = group.id;
    this.dragover.itemId = item.id;
  }
  // 指标项拖拽drop事件
  handleItemDrop(item, group: IHostGroup, e: DragEvent) {
    e.preventDefault();
    try {
      const dragItem: IDragItem = JSON.parse(e.dataTransfer.getData('item'));
      if (dragItem.itemId === item.id && dragItem.groupId === group.id) return;

      const dragGroup = this.groups.find(data => data.id === dragItem.groupId);
      const dropGroup = this.groups.find(data => data.id === group.id);
      if (!dragGroup || !dropGroup) return;

      const dragIndex = dragGroup.panels.findIndex(data => data.id === dragItem.itemId);
      const dropIndex = dropGroup.panels.findIndex(data => data.id === item.id);
      if (dragIndex === -1) return;

      /* 判断不同组的匹配规则匹配的视图替换改为复制 dragGroup抓取位置  dropGroup目标位置 */
      const dragPanel = dragGroup.panels.slice(dragIndex, dragIndex + 1)[0];
      const dropPanelsId = dropGroup.panels.map(p => p.id);

      if (dropPanelsId.includes(dragPanel.id) && dragGroup.id !== dropGroup.id) {
        if (dragPanel.match_type.includes('manual') && !dragPanel.match_type.includes('auto')) {
          const targetPaneldId = dragGroup.panels[dragIndex].id;
          dragGroup.panels.splice(dragIndex, 1);
          if (this.enableAutoGrouping) {
            const targetDropPanel = dropGroup.panels.find(p => p.id === targetPaneldId);
            targetDropPanel.match_type = [...new Set(targetDropPanel.match_type.concat(['manual']))];
          }
        } else if (dragPanel.match_type.includes('auto') && dragPanel.match_type.includes('manual')) {
          dragGroup.panels[dragIndex].match_type = ['auto'];
        }
        /* 更新数据（便于导出） */
        if (this.enableAutoGrouping) {
          this.$emit('order-list-change', this.groups);
        }
        return;
      }
      if (this.enableAutoGrouping && dragGroup.id !== dropGroup.id && dragPanel.match_type.includes('auto')) {
        const tmp = dragGroup.id !== '__UNGROUP__' ? deepClone(dragPanel) : dragGroup.panels.splice(dragIndex, 1)[0];
        /* 判断目标匹配规则是否匹配 */
        const rules = dropGroup.auto_rules;
        const filterRules = rules.filter(r => matchRuleFn(tmp.title, r));
        if (filterRules.length) {
          tmp.match_type = ['manual', 'auto'];
          tmp.match_rules = filterRules;
        } else {
          tmp.match_type = ['manual'];
          tmp.match_rules = [];
        }
        if (
          dragGroup.id !== '__UNGROUP__' &&
          dragPanel.match_type.includes('auto') &&
          dragPanel.match_type.includes('manual')
        ) {
          dragGroup.panels[dragIndex].match_type = ['auto'];
        }
        dropGroup.panels.splice(dropIndex, 0, tmp);
      } else {
        const tmp = dragGroup.panels.splice(dragIndex, 1);
        dropGroup.panels.splice(dropIndex, 0, tmp[0]);
      }
      /* 更新数据（便于导出） */
      if (this.enableAutoGrouping) {
        this.$emit('order-list-change', this.groups);
      }

      // 判断未分组指标数量
      // const unknownGroupIndex = this.groups.findIndex(data => data.id === '__UNGROUP__')
      // if (unknownGroupIndex > -1 && !this.groups[unknownGroupIndex].panels.length) {
      //   this.groups.splice(unknownGroupIndex, 1)
      // }
      this.dragover.groupId = '';
      this.dragover.itemId = '';
    } catch {
      console.warn('parse drag data error');
    }
  }
  handleGroupNameChange(v) {
    this.curEditName = v;
  }
  // 保存分组名称
  handleEditSave(group: IHostGroup) {
    group.title = this.curEditName || group.title;
    this.handleEditCancel();
    this.handleGroupsChange();
    this.$emit('order-list-change', this.groups);
  }
  // 取消编辑分组名称
  handleEditCancel() {
    this.curEditName = '';
    this.editId = '';
  }
  handleCreateGroup() {
    this.showCreateBtn = false;
    this.$nextTick(() => {
      this.$refs.groupInput && (this.$refs.groupInput as any).focus();
    });
  }
  handleSaveNewGroup(val = '') {
    if (val !== '' && val) {
      this.newGroupName = val;
    }
    if (typeTools.isNull(this.newGroupName)) return;
    const group = {
      id: `custom_${new Date().getTime()}`,
      title: this.newGroupName,
      panels: [],
    };
    this.groups.unshift(group);
    if (this.enableAutoGrouping) {
      this.$emit('add-group-change', group);
    }
    this.newGroupName = '';
    this.showCreateBtn = true;
    this.handleGroupsChange();
  }

  /* 隐藏及不隐藏的数目 */
  getHiddenNum(panels: { hidden: boolean }[], isHidden: boolean) {
    if (isHidden) {
      return panels.filter(item => item.hidden).length;
    }
    return panels.filter(item => !item.hidden).length;
  }

  /* 匹配规则更新 */
  handleAtuoRulesChange(value: string[], index: number) {
    this.groups[index].auto_rules = value;
    this.$emit('auto-rule-change', { id: this.groups[index].id, value });
  }
}
</script>
<style lang="scss" scoped>
.not-dialog {
  position: relative;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  width: 100%;
  border-radius: 0;
  box-shadow: none;

  :deep(.dialog-header) {
    display: none;
  }

  :deep(.dialog-footer) {
    position: fixed;
    bottom: 0;
    width: 520px;
    padding: 16px 0 24px 20px;
    background: #fff;
    opacity: 1;
  }

  :deep(.dialog-content) {
    max-height: none;
    padding: 216px 26px 150px 45px;
  }

  &.nochecked {
    :deep(.dialog-content) {
      padding: 174px 26px 150px 45px;
    }
  }

  :deep(.bk-collapse-item-content) {
    padding: 0;
  }
}

.flip-list-move {
  transition: transform 0.5s;
}

.create-group {
  display: flex;
  align-items: center;
  height: 42px;
  padding: 0 14px;

  i {
    font-size: 24px;
    cursor: pointer;
  }

  &.edit {
    padding: 0 20px;

    i {
      color: #979ba5;
    }
  }

  .icon-mc-add {
    color: #3a84ff;
  }

  .create-btn {
    font-size: 12px;
  }
}

.group-item {
  border: 1px solid transparent;
  border-bottom: 1px solid #f0f1f5;

  .text-ellipsis {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :deep(.bk-collapse-item-hover) {
    padding: 0 12px;

    &:hover {
      color: #63656e;
    }
  }

  &.is-dragover {
    border-color: #a3c5fd;
  }

  .icon-drag {
    position: relative;
    height: 14px;
    cursor: move;

    &::after {
      position: absolute;
      top: 0;
      width: 2px;
      height: 14px;
      content: ' ';
      border-right: 2px dotted #979ba5;
      border-left: 2px dotted #979ba5;
    }
  }

  &-title {
    display: flex;
    justify-content: space-between;
    font-size: 12px;

    .title-left {
      display: flex;
      flex: 1;
      align-items: center;
      color: #313238;

      .icon-mc-tuozhuai {
        margin-right: 4px;
        color: #c4c6cc;
        cursor: move;
      }

      .icon-mc-triangle-down {
        color: #c4c6cc;
        transition: transform 0.2s ease-in-out;
        transform: rotate(-90deg);

        &.expand {
          transform: rotate(0);
        }
      }

      i {
        font-size: 24px;
        color: #979ba5;
      }

      .title-edit {
        display: flex;
        flex: 1;
        align-items: center;
      }

      .hidden-num {
        margin-left: 16px;
        color: #979ba5;

        .hidden-num-item {
          display: inline-flex;
          align-items: center;
          margin-right: 14px;

          .icon-mc-visual,
          .icon-mc-invisible {
            margin-right: 4px;
            font-size: 16px;
          }
        }
      }
    }

    .title-right {
      display: flex;
      align-items: center;
      padding-right: 16px;
      font-size: 16px;
      color: #979ba5;
    }

    .last-right {
      padding-right: 0;

      .icon-mc-delete-line {
        font-size: 20px;
        color: #63656e;

        &:hover {
          color: #ff5656;
        }
      }
    }

    &.enable-auto-grouping {
      .text-ellipsis {
        width: 150px;
        max-width: 150px;
      }

      .title-left {
        .icon-bianji {
          position: relative;
          top: 5px;
          font-size: 24px;
          line-height: 12px;
          color: #979ba5;
          cursor: pointer;
        }

        .auto-rules {
          display: flex;
          align-items: center;

          &-title {
            margin-right: 4px;
          }

          &-content {
            display: flex;
            align-items: flex-start;
            width: 500px;
            height: 32px;
          }
        }
      }
    }
  }

  .is-group {
    padding: 0 6px 18px 30px;
  }
}
</style>
