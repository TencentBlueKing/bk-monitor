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
  <span
    class=""
    @click="handleShowFilterList($event)"
  >
    <i :class="['ml5 icon-monitor icon-filter-fill', { active: active }]" />
  </span>
</template>
<script lang="ts">
import i18n from '../../i18n/i18n';

import { Component, Emit, Prop, Vue, Watch } from 'vue-property-decorator';

import LabelMenu from './label-menu.vue';

import type MonitorVue from '../../types/index';

interface IOption {
  checked: boolean;
  id: string;
  name: string;
}

@Component({ name: 'filter-funnel' })
export default class FilterFunnel extends Vue<MonitorVue> {
  @Prop({ default: () => [] }) readonly data: IOption[];

  private labelMenuInstance: LabelMenu = null;
  private instance: any = null;
  private list: IOption[] = [];

  get active() {
    return this.list.some(item => item.checked);
  }

  @Watch('data', { deep: true, immediate: true })
  handleDataChange() {
    this.handleResetList();
  }

  public handleShowFilterList(e: Event) {
    if (!this.labelMenuInstance) {
      this.labelMenuInstance = new LabelMenu({
        i18n,
      }).$mount();
      this.labelMenuInstance.list = this.list;
      this.labelMenuInstance.$on('confirm', () => {
        this.handleConfirm();
      });
      this.labelMenuInstance.$on('clear', () => {
        this.handleClear();
      });
    }
    if (!this.instance) {
      this.instance = this.$bkPopover(e.target, {
        content: this.labelMenuInstance.$el,
        trigger: 'manual',
        arrow: false,
        theme: 'light common-monitor table-filter',
        maxWidth: 280,
        offset: '0, 5',
        sticky: true,
        duration: [275, 0],
        interactive: true,
        onHidden: () => {
          this.handleResetList();
        },
      });
    }
    this.instance?.show(100);
  }

  @Emit('clear')
  public handleClear(): IOption[] {
    this.instance?.hide();
    return JSON.parse(JSON.stringify(this.list));
  }

  @Emit('confirm')
  public handleConfirm(): IOption[] {
    this.instance?.hide();
    return JSON.parse(JSON.stringify(this.list));
  }

  public handleResetList() {
    this.list = JSON.parse(JSON.stringify(this.data));
    this.labelMenuInstance && (this.labelMenuInstance.list = this.list);
  }
}
</script>
<style lang="scss" scoped>
.icon-filter-fill {
  color: #c0c4cc;
  cursor: pointer;

  &.active {
    color: #3a84ff;
  }
}
</style>
