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
  <ul class="chart-menu">
    <template v-for="item in menuList">
      <li
        v-if="list.includes(item.id)"
        :key="item.id"
        class="chart-menu-item"
        @mousedown="handleMenuClick(item)"
      >
        <i
          class="menu-icon icon-monitor"
          :class="'icon-' + (!item.checked ? item.icon : item.nextIcon || item.icon)"
        />
        {{ !item.checked ? item.name : item.nextName || item.name }}
        <i
          v-if="item.hasLink"
          class="icon-monitor icon-mc-link link-icon"
        />
      </li>
    </template>
  </ul>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

interface menuItem {
  checked: boolean;
  hasLink?: boolean;
  icon: string;
  id: string;
  name: string;
  nextIcon?: string;
  nextName?: string;
}
@Component({
  name: 'chart-menu',
})
export default class ChartMenu extends Vue {
  @Prop({ default: () => [] }) list: string[];
  menuList: menuItem[] = [];
  created() {
    this.menuList = [
      {
        name: this.$t('保存到仪表盘').toString(),
        checked: false,
        id: 'save',
        icon: 'mc-mark',
      },
      {
        name: this.$t('截图到本地').toString(),
        checked: false,
        id: 'screenshot',
        icon: 'mc-camera',
      },
      {
        name: this.$t('查看大图').toString(),
        checked: false,
        id: 'fullscreen',
        icon: 'fullscreen',
      },
      {
        name: this.$t('检索').toString(),
        checked: false,
        id: 'explore',
        icon: 'mc-retrieval',
        hasLink: true,
      },
      {
        name: this.$t('添加策略').toString(),
        checked: false,
        id: 'strategy',
        icon: 'mc-strategy',
        hasLink: true,
      },
      {
        name: this.$t('相关告警').toString(),
        checked: false,
        id: 'relate-alert',
        icon: 'mc-menu-alert',
        hasLink: true,
      },
      {
        name: this.$t('Y轴固定最小值为0').toString(),
        checked: false,
        id: 'set',
        nextName: this.$t('Y轴自适应').toString(),
        icon: 'mc-yaxis',
        nextIcon: 'mc-yaxis-scale',
      },
      {
        name: this.$t('面积图').toString(),
        checked: false,
        id: 'area',
        nextName: this.$t('线性图').toString(),
        icon: 'mc-area',
        nextIcon: 'mc-line',
      },
    ];
  }
  @Emit('menu-click')
  handleMenuClick(item: menuItem) {
    item.checked = !item.checked;
    return item;
  }
}
</script>
<style lang="scss" scoped>
.chart-menu {
  position: absolute;
  z-index: 999;
  display: flex;
  flex-direction: column;
  width: 182px;
  padding: 6px 0;
  font-size: 12px;
  background: #fff;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  box-shadow: 0px 3px 6px 0px rgba(0, 0, 0, 0.15);

  &-item {
    display: flex;
    flex: 0 0 32px;
    align-items: center;
    width: 100%;
    padding-left: 12px;
    font-weight: normal;
    color: #63656e;

    .menu-icon,
    %menu-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 12px;
      height: 12px;
      margin-right: 12px;
      font-size: 14px;
      color: #979ba5;
    }

    &:hover {
      color: #3a84ff;
      cursor: pointer;
      background: #f5f6fa;

      .menu-icon {
        color: #3a84ff;
      }
    }

    .link-icon {
      margin-left: auto;
      color: #979ba5;

      @extend %menu-icon;

      &:hover {
        color: #3a84ff;
      }
    }
  }
}
</style>
