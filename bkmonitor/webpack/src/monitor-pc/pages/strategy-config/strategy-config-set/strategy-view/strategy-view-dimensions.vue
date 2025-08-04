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
  <div class="dimensions-panel">
    <div
      v-for="item in dimensionData.filter(item => !!item.name)"
      :key="item.id"
      class="dimensions-panel-item"
    >
      <div
        v-bk-tooltips="{ content: item.id, allowHTML: false }"
        class="item-title"
      >
        {{ item.name }}
      </div>
      <div class="item-content">
        <bk-input
          v-model.trim="dimensionValues[item.id]"
          class="item-content-select"
          size="small"
          @click.native="handleShowMenu($event, item)"
          @change="handleSelectChange"
          @input="(v, event) => handleInputChange(v, item, event)"
          @keyup="(v, event) => handlekeyup(v, item, event)"
        />
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

import { Debounce } from '../../../../components/ip-selector/common/util';
import SelectMenu, { type IMenu } from './select-menu.vue';

interface IDimensionOption {
  id: string;
  list: IMenu[];
  name: string;
  show: boolean;
}

@Component({ name: 'strategy-view-dimensions' })
export default class DimensionsPanel extends Vue {
  // 维度列表
  @Prop({ default: () => [], type: Array }) private readonly dimensionData!: IDimensionOption[];
  // 当前可选项值
  @Prop({ default: () => ({}), type: Object }) private readonly currentDimensionMap: object;
  @Prop({ default: () => ({}), type: Object }) private readonly value: object;

  private currentItem: IDimensionOption = null;
  private dimensionValues = {};
  private menuInstance: SelectMenu = new SelectMenu().$mount();
  private popoverInstance = null;

  created() {
    this.menuInstance.$on('click', this.handleMenuClick);
    this.menuInstance.$on('extension-click', this.handleExtensionClick);
    this.menuInstance.popoverWidth = 146;
    this.dimensionValues = this.value;
  }

  beforeDestroy() {
    this.menuInstance.$off('click', this.handleMenuClick);
    this.menuInstance.$off('extension-click', this.handleExtensionClick);
  }

  @Debounce(300)
  @Emit('change')
  private handleSelectChange() {
    return JSON.parse(JSON.stringify(this.dimensionValues));
  }

  private handleMenuClick(menu: IMenu) {
    if (!this.currentItem) return;

    this.$set(this.dimensionValues, this.currentItem.id, menu.id);
    this.handlePopHidden();
    this.handleSelectChange();
  }

  private handleExtensionClick() {
    if (!this.currentItem) return;

    this.menuInstance.$props.list = this.currentItem.list;
    // this.menuInstance.$props.showExtension = false;
  }

  private handleShowPop(event?) {
    if (!event?.target) {
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.menuInstance.$el,
      trigger: 'manual',
      arrow: false,
      theme: 'light common-monitor',
      maxWidth: 280,
      sticky: true,
      duration: [275, 0],
      offset: '0, -8',
      interactive: true,
      onHidden: () => {
        this.handlePopHidden();
        this.currentItem = null;
      },
    });
    this.popoverInstance?.show?.();
  }
  private handlePopHidden() {
    this.popoverInstance?.hide?.(0);
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  // @Debounce(300)
  private handleShowMenu(event: Event, item: IDimensionOption) {
    if (!item.list || item.list.length === 0) return;

    this.currentItem = item;
    const value = String(this.dimensionValues[item.id] || '');
    let filterList = [];
    if (item.list.some(item => item.id === value || item.name === value)) {
      filterList = item.list;
    } else {
      filterList = item.list.filter(l => l.id.toString().indexOf(value) > -1 || l.name.toString().indexOf(value) > -1);
    }
    this.menuInstance.$props.list = value ? filterList : item.list;
    this.handleShowPop(event);
  }
  @Debounce(300)
  private handleInputChange(value: string, item, event?) {
    const filterList = item.list.filter(
      l => l.id.toString().indexOf(value) > -1 || l.name.toString().indexOf(value) > -1
    );
    this.menuInstance.$props.list = filterList;
    this.currentItem = item;
    if (filterList.length) {
      if (this.popoverInstance) {
        this.popoverInstance?.show?.();
      } else {
        this.handleShowPop(event);
      }
    } else {
      this.handlePopHidden();
    }
  }

  private handlekeyup(value: string, item, event) {
    if (event.code === 'Backspace') {
      this.handleInputChange(value, item, event);
    }
  }
}
</script>
<style lang="scss" scoped>
.dimensions-panel {
  display: flex;
  flex-wrap: wrap;
  padding: 0 14px;

  &-item {
    display: flex;
    align-items: center;
    height: 24px;
    margin-right: 5px;
    line-height: 24px;

    &:not(:last-child) {
      margin-bottom: 10px;
    }

    .item-title {
      padding: 0 10px;
      cursor: pointer;
      background: #f0f1f5;
      border: 1px solid #c4c6cc;
      border-radius: 2px 0px 0px 2px;
    }

    .item-content-select {
      min-width: 100px;
      margin-left: -1px;
    }
  }
}
</style>
