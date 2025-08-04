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
  <bk-dropdown-menu
    ext-cls="dropdown-menu"
    trigger="click"
    @show="dropdownShow"
    @hide="dropdownHide"
  >
    <template slot="dropdown-trigger">
      <div
        :class="['dropdown-trigger', { active: isDropdownShow, 'refresh-trigger': isRefreshInterval }]"
        @click="handleTirrger"
      >
        <div
          v-bk-tooltips="{ content: $t('自动刷新设置'), placement: 'bottom' }"
          :class="['trigger-name', { 'refresh-name': isRefreshInterval }]"
        >
          <i
            v-if="icon"
            :class="['icon-monitor', 'mr5', icon]"
          />
          <span
            v-if="iconTitle"
            class="icon-title"
          >
            {{ iconTitle }}
          </span>
          <span
            v-if="showName"
            :class="['trigger-text', { 'text-active': textActive }]"
          >
            {{ currentActive.name }}
          </span>
        </div>
        <i
          v-if="!isRefreshInterval && !readonly"
          :class="['bk-icon icon-angle-down', { 'icon-flip': isDropdownShow }]"
        />
        <i
          v-if="isRefreshInterval"
          v-bk-tooltips="{ content: $t('刷新'), placement: 'bottom' }"
          class="icon-monitor icon-mc-alarm-recovered"
          @click.stop="$emit('on-icon-click')"
        />
      </div>
    </template>
    <template slot="dropdown-content">
      <ul class="dropdown-list">
        <li
          v-for="item in list"
          :key="item.id"
          :class="['dropdown-list-item', { active: active === item.id }]"
          @click="handleChangeActive(item.id)"
        >
          <!-- 刷新文案改为关闭，但是选择后还是展示刷新 -->
          {{ item.name === 'off' ? `${$t('button-关闭')}（off）` : item.name }}
        </li>
      </ul>
    </template>
  </bk-dropdown-menu>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Vue, Watch } from 'vue-property-decorator';

import type { IOption } from '../../pages/performance/performance-type';

@Component({ name: 'dropdown-menu' })
export default class DropDownMenu extends Vue {
  @Model('change', { default: '' }) readonly value: number | string;
  @Prop({ default: () => [], type: Array }) readonly list: IOption[];
  @Prop({ default: '' }) readonly icon: string;
  @Prop({ default: true }) readonly showName: boolean;
  @Prop({ default: false }) readonly textActive: boolean;
  @Prop({ default: '' }) readonly iconTitle: string;
  @Prop({ default: false }) readonly readonly: boolean;
  @Prop({ default: false }) readonly isRefreshInterval: boolean;

  isDropdownShow = false;
  active: number | string = '';

  get currentActive() {
    if (this.list.length && this.active) {
      return this.list.find(item => item.id.toString() === this.active.toString()) || this.list[0];
    }
    return { id: 'unknown', name: this.$t('选择') };
  }

  @Watch('value', { immediate: true })
  handleValueChange(v) {
    // this.handleChangeActive(v)
    this.active = v;
  }
  handleTirrger(e) {
    if (this.readonly) {
      e.preventDefault();
      e.stopPropagation();
    }
  }
  dropdownShow() {
    this.isDropdownShow = true;
  }

  dropdownHide() {
    this.isDropdownShow = false;
  }

  @Emit('change')
  handleChangeActive(id: number | string) {
    this.active = id;
    return this.active;
  }
}
</script>
<style lang="scss" scoped>
@import '../../theme';

@mixin border-left($top: 4px) {
  &::after {
    position: absolute;
    top: 50%;
    right: -9px;
    display: flex;
    width: 1px;
    height: 14px;
    content: '';
    background-color: #dcdee5;
    transform: translateY(-50%);
  }
}

/* stylelint-disable declaration-no-important */
.dropdown-menu {
  width: inherit !important;
  height: auto !important;

  :deep(.bk-dropdown-content) {
    top: 8px !important;
  }

  &.bk-dropdown-menu.disabled,
  .bk-dropdown-menu.disabled * {
    color: #63656e;
    cursor: inherit;
    background-color: rgba(0, 0, 0, 0) !important;
    border-color: none !important;
  }
}

.dropdown-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 24px;
  padding-left: 6px;
  cursor: pointer;

  &.refresh-trigger {
    cursor: default;
  }

  .trigger-name {
    position: relative;
    display: flex;
    align-items: center;
    height: 24px;
    padding: 0 4px 0 5px;
    margin-right: 8px;

    &.refresh-name {
      @include border-left;

      &.active,
      &:hover {
        color: #3a84ff;
        cursor: pointer;
        background-color: #eaf3ff;
        border-radius: 2px;
      }
    }

    i {
      height: 14px;
      font-size: 14px;
    }

    .icon-title {
      margin: 0 8px 0 4px;
    }

    .text-active {
      color: #3a84ff;
    }
  }

  .icon-mc-alarm-recovered {
    margin-left: 8px;

    @include new-tool-icon;
  }

  .icon-angle-down {
    font-size: 20px;
  }
}

.dropdown-list-item {
  padding: 0 15px;
  line-height: 32px;
  white-space: nowrap;
  cursor: pointer;

  &.active {
    color: #3a84ff;
    background: #f5f6fa;
  }

  &:hover {
    color: #3a84ff;
    cursor: pointer;
    background-color: #eaf3ff;
  }
}
</style>
