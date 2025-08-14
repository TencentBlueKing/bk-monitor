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
  <div :class="['drag-list', { 'is-check': isCheck }]">
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
        :class="[
          { 'is-dragover': dragover.itemId === item.id },
          { 'content-item-check': isCheck },
          { 'is-hidden': item.hidden },
        ]"
        @dragstart.stop="handleDragStart(item, group, $event)"
        @dragend.stop="handleDragEnd"
        @dragover.stop="handleDragOver(item, group, $event)"
        @drop="handleDrop(item, group, $event)"
      >
        <template v-if="!isCheck">
          <span class="item-title">{{ item.title }}</span>
          <span class="item-operate">
            <i
              :class="['icon-monitor', !item.hidden ? 'icon-mc-visual' : 'icon-mc-invisible']"
              @click="handleToggleVisible(group, item)"
            />
            <i class="ml10 icon-monitor icon-mc-tuozhuai" />
          </span>
        </template>
        <template v-else>
          <!-- 可选中 -->
          <i class="ml10 icon-monitor icon-mc-tuozhuai" />
          <bk-checkbox
            ext-cls="item-check"
            :true-value="true"
            :false-value="false"
            :value="checkList.includes(item.id)"
            @change="v => checkChange(v, item)"
          />
          <span class="item-title">{{ item.title }}</span>
          <span class="item-operate">
            <span
              v-if="enableAutoGrouping && item.match_type.includes('auto') && item.match_type.length === 1"
              class="auto-tag"
            >
              {{ $t('自动匹配') }}
            </span>
            <i
              :class="['icon-monitor', !item.hidden ? 'icon-mc-visual' : 'icon-mc-invisible']"
              @click="handleToggleVisible(group, item)"
            />
          </span>
        </template>
      </li>
    </transition-group>
    <div
      v-else
      class="content-empty"
      @drop="handleDrop({}, group, $event)"
    >
      <i class="icon-monitor icon-mind-fill" />
      {{ $t('将已有视图拖拽至此') }}
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

import type { IGroupItem, IHostGroup } from '../performance-type';

@Component({ name: 'SortDragList' })
export default class SortDragList extends Vue {
  @Prop({ required: true }) group: IHostGroup;
  @Prop({ required: true }) dragover: {};
  @Prop({ required: true }) transitionName: '';
  @Prop({ type: Boolean, default: false }) isCheck: boolean;
  @Prop({ type: Boolean, default: false }) enableAutoGrouping: boolean;

  checked = {
    id: '',
    panels: [],
  };

  @Emit('check-change')
  checkChange(val: boolean, item: IGroupItem) {
    if (val) {
      this.checked.panels.push(item);
    } else {
      const index = this.checked.panels.findIndex(panel => panel.id === item.id);
      index > -1 && this.checked.panels.splice(index, 1);
    }
    this.checked.id = this.group.id;
    return this.checked;
  }

  get checkList(): string[] {
    return this.checked.panels.map(item => item.id);
  }

  clearChecked() {
    this.checked.panels = [];
  }

  @Emit('drag-end')
  handleDragEnd(e: DragEvent) {
    return e;
  }
  handleDragStart(item: IGroupItem, group: IHostGroup, $event: DragEvent) {
    this.$emit('drag-start', item, group, $event);
  }
  handleDragOver(item: IGroupItem, group: IHostGroup, e: DragEvent) {
    e.preventDefault();
    this.$emit('drag-over', item, group, e);
  }
  handleDrop(item: IGroupItem, group: IHostGroup, e: DragEvent) {
    e.preventDefault();
    this.$emit('drop', item, group, e);
  }
  handleToggleVisible(group: IHostGroup, item: IGroupItem) {
    this.$emit('toggle-visible', group, item);
  }
}
</script>
<style lang="scss" scoped>
.flip-list-move {
  transition: transform 0.5s;
}

.drag-list {
  padding: 0 20px;

  &.is-check {
    /* stylelint-disable-next-line declaration-no-important */
    padding: 0 0 18px 0 !important;
  }

  .icon-mc-tuozhuai {
    position: relative;
    height: 14px;

    /* stylelint-disable-next-line declaration-no-important */
    font-size: 12px !important;
    color: #c4c6cc;
    cursor: move;
    // &::after {
    //   content: ' ';
    //   height: 14px;
    //   width: 2px;
    //   position: absolute;
    //   top: 0;
    //   border-left: 2px dotted #979ba5;
    //   border-right: 2px dotted #979ba5;
    // }
  }

  .content-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 64px;
    color: #979ba5;
    background: #fafbfd;
    border: 1px solid #f0f1f5;
    border-radius: 2px;

    i {
      position: relative;
      top: 1px;
      margin-right: 6px;
      font-size: 14px;
    }
  }

  .content-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 32px;
    padding: 0 24px 0 12px;
    margin-bottom: 2px;
    background: #f5f6fa;
    border: 1px solid transparent;
    border-radius: 2px;

    &-check {
      justify-content: flex-start;

      .item-check {
        margin-left: 14px;
      }

      .item-title {
        margin-left: 6px;
      }

      .item-operate {
        margin: 0 0 0 auto;
      }
    }

    .item-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .item-operate {
      display: flex;
      align-items: center;
    }

    .auto-tag {
      display: flex;
      align-items: center;
      height: 22px;
      padding: 0 10px;
      margin-right: 17px;
      color: #14a568;
      background: #e4faf0;
      border: 1px solid rgba(20, 165, 104, 0.3);
      border-radius: 2px;
    }

    i {
      font-size: 16px;
    }

    &.is-hidden {
      color: #c4c6cc;
      background: #fafbfd;

      :deep(.bk-form-checkbox) {
        .bk-checkbox {
          border: 1px solid #dcdee5;
        }
      }
    }

    &:hover {
      cursor: pointer;
      background: #e1ecff;
      border-color: #a3c5fd;
    }

    &.is-dragover {
      background: #e1ecff;
    }
  }
}
</style>
