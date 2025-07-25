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
  <section
    class="ip-selector"
    :style="{ height: typeof height === 'number' ? `${height}px` : height }"
  >
    <selector-tab
      ref="tab"
      class="ip-selector-left"
      :panels="panels"
      :active="panelActive"
      :tab-visible="tabVisible"
      @tab-change="handleTabChange"
    >
      <selector-content
        ref="content"
        :active="panelActive"
        :panels="panels"
        :tree-height="treeHeight"
        v-bind="$attrs"
        v-on="contentEvents"
      />
    </selector-tab>
    <div
      v-if="width === 0"
      class="preview-toggle"
    >
      <div
        v-bk-tooltips="{
          content: $t('点击展开'),
          showOnInit: true,
          placements: ['left'],
          delay: 300,
          boundary: 'window',
        }"
        class="open-preview"
        @click.stop="handleResetWidth"
      >
        <i class="bk-icon icon-angle-left" />
      </div>
    </div>
    <selector-preview
      v-else
      ref="preview"
      class="ip-selector-right"
      :width.sync="width"
      :range="previewRange"
      :data="previewData"
      :operate-list="previewOperateList"
      :default-active-name="defaultActiveName"
      @menu-click="handlePreviewMenuClick"
      @remove-node="handleRemoveNode"
    />
  </section>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import SelectorContent from './selector/selector-content.vue';
import SelectorPreview from './selector/selector-preview.vue';
import SelectorTab from './selector/selector-tab.vue';

import type { IEventsMap, IMenu, IPanel, IPerateFunc, IPreviewData } from './types/selector-type';

@Component({
  name: 'ip-selector',
  inheritAttrs: false,
  components: {
    SelectorTab,
    SelectorContent,
    SelectorPreview,
  },
})
export default class IpSelector extends Vue {
  @Prop({ default: '', type: String }) private readonly active!: string;
  @Prop({ default: () => [], type: Array, required: true }) private readonly panels!: IPanel[];
  @Prop({ default: true, type: Boolean }) private readonly tabVisible!: boolean;

  @Prop({ default: 280, type: [Number, String] }) private readonly previewWidth!: number | string;
  @Prop({ default: 300, type: [Number, String] }) private readonly treeHeight: number | string;
  @Prop({ default: () => [150, 600], type: Array }) private readonly previewRange!: number[];
  @Prop({ default: () => [], type: Array }) private readonly previewData!: IPreviewData[];
  @Prop({ default: () => [], type: [Array, Function] }) private readonly previewOperateList!: IMenu[] | IPerateFunc;
  @Prop({ default: '', type: [Number, String] }) private readonly height!: number | string;
  @Prop({ default: () => [], type: Array }) private readonly defaultActiveName!: string[];

  @Ref('tab') private readonly tabRef!: SelectorTab;
  @Ref('preview') private readonly previewRef!: SelectorPreview;

  private panelActive = null; // 当前active的tab项
  private width: number | string = 0; // 预览区域宽度
  private excludeEvents = ['tab-change', 'menu-click', 'remove-node']; // 不能丢到layout组件的事件

  private get contentEvents() {
    return Object.keys(this.$listeners).reduce<IEventsMap>((pre, key) => {
      if (this.excludeEvents.includes(key)) return pre;
      pre[key] = (...args: any[]) => {
        this.$emit(key, ...args);
      };
      return pre;
    }, {});
  }

  @Watch('active')
  private handleActiveChange() {
    this.panelActive = this.active;
  }

  private created() {
    this.panelActive = this.active;
    this.width = this.previewWidth;

    if (!this.panelActive) {
      const [firstPanel] = this.panels;
      this.panelActive = firstPanel?.name ? firstPanel.name : '';
      this.$emit('update:active', this.panelActive);
    }
  }

  // 展开预览面板
  private handleResetWidth() {
    this.width = this.previewWidth;
  }
  // tab切换
  @Emit('tab-change')
  @Emit('update:active')
  private handleTabChange(active: string) {
    this.panelActive = active;
    return active;
  }
  // 预览面板操作(移除IP、复制IP等操作)
  @Emit('menu-click')
  private handlePreviewMenuClick({ menu, item }: { item: IPreviewData; menu: IMenu }) {
    return {
      menu,
      item,
    };
  }
  // 移除预览面板节点
  @Emit('remove-node')
  private handleRemoveNode({ child, item }: { child: any; item: IPreviewData }) {
    return {
      child,
      item,
    };
  }

  public handleGetDefaultSelections() {
    try {
      (this.$refs.content as any).handleGetDefaultSelections();
    } catch (err) {
      console.log(err);
    }
  }
}
</script>
<style lang="scss" scoped>
@import './style/selector.css';

.ip-selector {
  display: flex;
  width: 100%;
  height: 100%;

  &-left {
    flex: 1;
    width: 0;
  }

  &-right {
    position: relative;
    margin-left: -1px;
  }
}

.preview-toggle {
  position: relative;
  margin-left: -1px;
}

.open-preview {
  position: absolute;
  top: calc(50% - 50px);
  left: -10px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 10px;
  height: 100px;
  cursor: pointer;
  background-color: #f0f1f5;
  border: 1px solid #dcdee5;
  border-right: 0;
  border-radius: 4px 0px 0px 4px;
  outline: 0;
}

.icon-angle-left {
  display: inline-block;
  width: 16px;
  height: 16px;
  font-size: 16px;
  color: #979ba5;
}
</style>
