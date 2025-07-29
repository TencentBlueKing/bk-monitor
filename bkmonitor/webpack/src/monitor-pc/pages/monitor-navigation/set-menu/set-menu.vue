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
  <div>
    <span
      ref="menuIcon"
      v-authority="{ active: !hasAuth }"
      class="mneu-wrap"
      @click="handleClick"
    >
      <slot> New <i class="icon-monitor icon-mc-add mneu-wrap-icon" /> </slot>
    </span>
    <div v-show="false">
      <ul
        ref="menuList"
        class="menu-list"
      >
        <li
          v-for="item in menuList"
          :key="item.id"
          class="menu-list-item"
          @click="$emit('item-click', item)"
        >
          {{ item.name }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

@Component
export default class SetMenu extends Vue {
  @Ref('menuList') menuListRef: HTMLUListElement;
  @Ref('menuIcon') menuIconRef: HTMLUListElement;
  @Prop({ required: true }) menuList: { id: string; name: string }[];
  @Prop({ default: true }) hasAuth: boolean;
  instance: any = null;
  @Watch('hasAuth')
  onHasAuthChange() {
    this.handlePopover();
  }
  mounted() {
    this.handlePopover();
  }
  handlePopover() {
    if (!this.instance && this.hasAuth) {
      this.instance = this.$bkPopover(this.menuIconRef, {
        content: this.menuListRef,
        arrow: false,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light common-monitor',
        maxWidth: 520,
        duration: [275, 0],
        offset: '10, 2',
      });
    } else if (this.instance) {
      this.instance.hide();
      this.instance.destroy();
      this.instance = null;
    }
  }
  handleClick() {
    this.$emit('click');
  }
}
</script>
<style lang="scss" scoped>
.mneu-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 26px;
  padding: 0 12px;
  margin-left: 15px;
  font-size: 12px;
  color: #fff;
  background: #3a84ff;
  border-color: #3a84ff;
  border-radius: 2px;

  &-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 16px;
    height: 26px;
    font-size: 16px;
  }

  &:hover {
    cursor: pointer;
    background-color: #699df4;
    opacity: 1;
  }
}

.menu-list {
  display: flex;
  flex-direction: column;
  padding: 6px 0;
  font-size: 12px;
  background-color: white;

  &-item {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    line-height: 32px;
    color: #63656e;

    &:hover {
      color: #3a84ff;
      cursor: pointer;
      background-color: #eaf3ff;
    }
  }
}
</style>
