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
  <div class="selector-tab">
    <div
      v-show="tabVisible && panels.length"
      ref="tabwrapper"
      v-resize="handleResize"
      class="selector-tab-header"
    >
      <ul
        ref="tabcontent"
        class="selector-tab-horizontal"
      >
        <li
          v-for="item in panels"
          v-show="!item.hidden && !hiddenPanels.some(data => data.name === item.name)"
          :key="item.name"
          ref="tabItem"
          v-bk-tooltips.top="{
            disabled: !item.disabled || !item.tips,
            content: item.tips,
            delay: [300, 0],
          }"
          :class="['tab-item', { active: active === item.name }, { disabled: item.disabled }]"
          :data-name="item.name"
          @click="!item.disabled && handleTabChange(item)"
        >
          <slot
            name="label"
            v-bind="{ item }"
          >
            {{ item.label }}
          </slot>
        </li>
        <li
          v-show="showArrow"
          @click="handleShowList"
        >
          <span class="selector-tab-all">
            <i class="bk-icon icon-angle-double-right" />
          </span>
        </li>
      </ul>
    </div>
    <div
      class="selector-tab-content"
      :style="{ 'border-top': tabVisible && panels.length ? `none` : '' }"
    >
      <slot />
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Ref, Vue } from 'vue-property-decorator';

import { resize } from '../common/observer-directive';
import { Debounce, hasOwnProperty } from '../common/util';
import Menu from '../components/menu.vue';

import type { IPanel } from '../types/selector-type';

@Component({
  name: 'selector-tab',
  directives: {
    resize,
  },
})
export default class SelectorTab extends Vue {
  @Model('tab-change', { default: '', type: String }) private readonly active!: string;
  @Prop({
    default: () => [],
    type: Array,
    validator: (v: IPanel[]) => {
      const item = v.find((item: IPanel) => !hasOwnProperty(item, ['name', 'label']));
      item && console.warn(item, '缺少必要属性');
      return !item;
    },
  })
  private readonly panels!: IPanel[];
  @Prop({ default: true, type: Boolean }) private readonly tabVisible!: boolean;

  @Ref('tabwrapper') private readonly tabwrapper!: HTMLElement;
  @Ref('tabcontent') private readonly tabcontent!: HTMLElement;
  @Ref('tabItem') private readonly tabItemRef!: HTMLElement[];

  private hiddenPanels: { name: string; width: number }[] = [];
  private popoverInstance: any = null;
  private menuInstance: Menu | null = null;

  private get showArrow() {
    return this.hiddenPanels.length !== 0;
  }

  private beforeDestroy() {
    if (this.menuInstance) {
      this.menuInstance.$off('click', this.handleMenuClick);
      this.menuInstance.$destroy();
    }
  }

  private handleMenuClick(menu: IPanel) {
    this.handleTabChange(menu);
    this.popoverInstance?.hide();
  }

  private handleShowList(event: Event) {
    if (!event.target) return;

    if (!this.menuInstance) {
      this.menuInstance = new Menu().$mount();
      this.menuInstance.$props.list = this.panels;

      this.menuInstance.$off('click', this.handleMenuClick);
      this.menuInstance.$on('click', this.handleMenuClick);
    }

    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(event.target, {
        content: this.menuInstance.$el,
        trigger: 'manual',
        arrow: false,
        theme: 'light ip-selector',
        maxWidth: 280,
        offset: '0, 0',
        sticky: true,
        duration: [275, 0],
        interactive: true,
        boundary: 'window',
        placement: 'bottom',
      });
    }
    this.popoverInstance.show();
  }

  @Emit('tab-change')
  private handleTabChange(panel: IPanel) {
    return panel.name;
  }

  @Debounce(400)
  private handleResize() {
    if (!this.tabwrapper || !this.tabcontent) return;

    const { right: wrapperRight } = this.tabwrapper.getBoundingClientRect();

    this.tabItemRef?.forEach(node => {
      const { right: nodeRight, width: nodeWidth } = (node as HTMLElement).getBoundingClientRect();
      const nameData = (node as HTMLElement).dataset.name;
      const index = this.hiddenPanels.findIndex(item => item.name === nameData);
      // 32: 折叠按钮宽度
      if (nodeRight + 32 > wrapperRight) {
        index === -1 &&
          nameData &&
          this.hiddenPanels.push({
            name: nameData,
            width: nodeWidth,
          });
      }
    });

    this.$nextTick(() => {
      const wrapperWidth = this.tabwrapper.clientWidth;
      let contentWidth = this.tabcontent.clientWidth;
      // 按顺序显示panel
      this.panels.forEach(item => {
        const index = this.hiddenPanels.findIndex(data => data.name === item.name);
        if (index > -1 && contentWidth + this.hiddenPanels[index].width < wrapperWidth) {
          contentWidth += this.hiddenPanels[index].width;
          this.hiddenPanels.splice(index, 1);
        }
      });
    });
  }
}
</script>
<style lang="scss" scoped>
.selector-tab {
  display: flex;
  flex-direction: column;

  &-header {
    display: flex;
    align-items: center;
    background: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  &-content {
    flex: 1;
    height: 0;
    border: 1px solid #dcdee5;
  }
}

.selector-tab-horizontal {
  display: flex;
  flex-shrink: 0;
  margin-bottom: -1px;
}

.tab-item {
  display: flex;
  align-items: center;
  height: 42px;
  padding: 0 24px;
  font-size: 14px;
  color: #63656e;
  cursor: pointer;
  border-right: 1px solid #dcdee5;
  border-bottom: 1px solid #dcdee5;
  outline: 0;

  &.disabled {
    color: #c4c6cc;
    cursor: not-allowed;
  }

  &.visibility {
    visibility: hidden;
  }
}

.tab-item.active {
  color: #313238;
  background: #fff;
  border-bottom: 0;
}

.selector-tab-all {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 42px;
  font-size: 20px;
  line-height: 42px;
  cursor: pointer;

  i {
    outline: 0;
  }
}
</style>
