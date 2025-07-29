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
  <div
    v-show="isNaN(preWidth) || preWidth > 0"
    class="selector-preview"
    :style="{ width: isNaN(preWidth) ? preWidth : `${preWidth}px` }"
  >
    <div class="selector-preview-title">
      <slot name="title">
        {{ $t('结果预览') }}
      </slot>
    </div>
    <div class="selector-preview-content">
      <bk-collapse v-model="activeName">
        <bk-collapse-item
          v-for="item in data"
          v-show="item.data && item.data.length"
          :key="item.id"
          :name="item.id"
          hide-arrow
        >
          <template #default>
            <div class="collapse-title">
              <span class="collapse-title-left">
                <i :class="['bk-icon icon-angle-right', { expand: activeName.includes(item.id) }]" />
                <slot
                  name="collapse-title"
                  v-bind="{ item }"
                >
                  <i18n path="已选{0}个{1}">
                    <span class="num">{{ item.data.length }}</span>
                    <span>{{ item.name }}</span>
                  </i18n>
                </slot>
              </span>
              <span
                class="collapse-title-right"
                @click.stop="handleShowMenu($event, item)"
              >
                <i class="bk-icon icon-more" />
              </span>
            </div>
          </template>
          <template #content>
            <slot
              name="collapse-content"
              v-bind="{ item }"
            >
              <ul class="collapse-content">
                <li
                  v-for="(child, index) in item.data"
                  :key="index"
                  class="collapse-content-item"
                  @mouseenter="hoverChild = child"
                  @mouseleave="hoverChild = null"
                >
                  <span
                    class="left"
                    :title="child[item.dataNameKey] || child.name || '--'"
                  >
                    {{ child[item.dataNameKey] || child.name || '--' }}
                  </span>
                  <span
                    v-show="hoverChild === child"
                    class="right"
                    @click="removeNode(child, item)"
                  >
                    <i class="bk-icon icon-close-line" />
                  </span>
                </li>
              </ul>
            </slot>
          </template>
        </bk-collapse-item>
      </bk-collapse>
    </div>
    <div
      class="drag"
      @mousedown="handleMouseDown"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue, Watch } from 'vue-property-decorator';

import { Debounce } from '../common/util';
import Menu from '../components/menu.vue';

import type { IMenu, IPerateFunc, IPreviewData } from '../types/selector-type';

// 预览区域
@Component({ name: 'selector-preview' })
export default class SelectorPreview extends Vue {
  @Prop({ default: 280, type: [Number, String] }) private readonly width!: number | string;
  @Prop({ default: () => [100, 600], type: Array }) private readonly range!: number[];
  @Prop({ default: () => [], type: Array }) private readonly data!: any[];
  @Prop({ default: () => [], type: [Array, Function] }) private readonly operateList!: IMenu[] | IPerateFunc;
  @Prop({ default: () => [], type: Array }) private readonly defaultActiveName!: string[];

  private preWidth: number | string = 280;
  private activeName: string[] = [];
  private hoverChild = null;
  private menuInstance = null;
  private popoverInstance: any = null;
  private previewItem: IPreviewData = null;

  created() {
    this.preWidth = this.width;
    this.activeName = this.defaultActiveName;
    this.menuInstance = new Menu().$mount();
  }

  @Watch('width')
  private handleChange(width: number) {
    this.preWidth = width;
  }

  private beforeDestroy() {
    if (this.menuInstance) {
      this.menuInstance.$off('click', this.handleMenuClick);
      this.menuInstance.$destroy();
    }
  }

  @Debounce(300)
  @Emit('update:width')
  private handleWidthChange() {
    return this.preWidth;
  }

  @Emit('menu-click')
  private handleMenuItemClick(menu: IMenu, item: IPreviewData) {
    return {
      menu,
      item,
    };
  }

  @Emit('remove-node')
  private removeNode(child: any, item: IPreviewData) {
    const index = item.data.indexOf(child);
    this.hoverChild = index > -1 && item.data[index + 1] ? item.data[index + 1] : null;
    return {
      child,
      item,
    };
  }

  private handleMenuClick(menu: IMenu) {
    this.popoverInstance?.hide();
    this.handleMenuItemClick(menu, this.previewItem);
  }

  private async handleShowMenu(event: Event, item: IPreviewData) {
    if (!event.target) return;

    const list = typeof this.operateList === 'function' ? await this.operateList(item) : this.operateList;

    if (!list?.length) return;

    this.menuInstance.$props.list = list;

    this.previewItem = item;
    this.menuInstance.$off('click', this.handleMenuClick);
    this.menuInstance.$on('click', this.handleMenuClick);

    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.menuInstance.$el,
      trigger: 'manual',
      arrow: false,
      theme: 'light ip-selector',
      maxWidth: 280,
      offset: '0, 5',
      sticky: true,
      duration: [275, 0],
      interactive: true,
      boundary: 'window',
      placement: 'bottom',
      onHidden: () => {
        this.popoverInstance?.destroy();
        this.popoverInstance = null;
      },
    });
    this.popoverInstance.show();
  }

  private handleMouseDown(e: MouseEvent) {
    const node = e.target as HTMLElement;
    const parentNode = node.parentNode as HTMLElement;

    if (!parentNode) return;

    const nodeRect = node.getBoundingClientRect();
    const rect = parentNode.getBoundingClientRect();
    document.onselectstart = function () {
      return false;
    };
    document.ondragstart = function () {
      return false;
    };
    const handleMouseMove = (event: MouseEvent) => {
      const [min, max] = this.range;
      const newWidth = rect.right - event.clientX + nodeRect.width;
      if (newWidth < min) {
        this.preWidth = 0;
      } else {
        this.preWidth = Math.min(newWidth, max);
      }
      this.handleWidthChange();
    };
    const handleMouseUp = () => {
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.onselectstart = null;
      document.ondragstart = null;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }
}
</script>
<style>
.ip-selector-theme {
  /* stylelint-disable-next-line declaration-no-important */
  padding: 0 !important;
}
</style>
<style lang="scss">
.selector-preview {
  position: relative;
  height: 100%;
  background: #f5f6fa;
  border: 1px solid #dcdee5;

  &-title {
    padding: 10px 24px;
    font-size: 14px;
    line-height: 22px;
    color: #313238;
  }

  &-content {
    height: calc(100% - 42px);
    overflow: auto;

    .collapse-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px 0 18px;

      &-left {
        display: flex;
        align-items: center;
        font-size: 12px;

        .num {
          padding: 0 2px;
          font-weight: 700;
          color: #3a84ff;
        }
      }

      &-right {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 2px;

        &:hover {
          color: #3a84ff;
          background: #e1ecff;
        }

        i {
          font-size: 18px;
          outline: 0;
        }
      }
    }

    .collapse-content {
      padding: 0 14px;
      margin-top: 6px;

      &-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        height: 32px;
        padding: 0 12px;
        margin-bottom: 2px;
        line-height: 32px;
        background: #fff;
        border-radius: 2px;
        box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, 0.06);

        .left {
          overflow: hidden;
          text-overflow: ellipsis;
          word-break: break-all;
          white-space: nowrap;
        }

        .right {
          color: #3a84ff;
          cursor: pointer;

          i {
            font-weight: 700;
          }
        }
      }
    }

    .icon-angle-right {
      font-size: 24px;
      transition: transform 0.2s ease-in-out;

      &.expand {
        transform: rotate(90deg);
      }
    }
  }
}

.drag {
  position: absolute;
  top: calc(50% - 10px);
  left: 0px;
  display: flex;
  align-items: center;
  justify-items: center;
  width: 6px;
  height: 20px;
  outline: 0;

  &::after {
    position: absolute;
    left: 2px;
    width: 0;
    height: 18px;
    content: ' ';
    border-left: 2px dotted #c4c6cc;
  }

  &:hover {
    cursor: col-resize;
  }
}
</style>
<style lang="scss">
.bk-collapse-item {
  margin-bottom: 10px;

  .bk-collapse-item-header {
    height: 24px;
    padding: 0;
    line-height: 24px;

    &:hover {
      color: #63656e;
    }
  }
}
</style>
