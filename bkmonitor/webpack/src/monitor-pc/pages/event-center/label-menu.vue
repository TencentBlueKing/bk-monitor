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
  <div class="label-menu-wrapper">
    <ul class="label-menu-list">
      <li
        v-for="(item, index) in list"
        :key="index"
        class="item"
        @click="handleCheck(item)"
      >
        <bk-checkbox :value="item.checked" />
        <span class="name">{{ item.name }}</span>
      </li>
    </ul>
    <div class="footer">
      <div class="btn-group">
        <span
          class="monitor-btn"
          @click="handleConfirm"
        >
          {{ $t('确定') }}
        </span>
        <span
          class="monitor-btn"
          @click="handleClear"
        >
          {{ $t('清空') }}
        </span>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Vue } from 'vue-property-decorator';

interface IOption {
  checked: boolean;
  id: string;
  name: string;
}

@Component({ name: 'label-menu' })
export default class LabelMenu extends Vue {
  public list: IOption[] = [];

  @Emit('confirm')
  public handleConfirm() {
    return this.list;
  }

  @Emit('clear')
  public handleClear() {
    this.list.forEach(item => {
      item.checked = false;
    });
    return this.list;
  }

  public handleCheck(item: IOption) {
    item.checked = !item.checked;
  }
}
</script>
<style lang="scss" scoped>
.label-menu-wrapper {
  .label-menu-list {
    display: flex;
    flex-direction: column;
    padding: 6px 0;
    background-color: #fff;
    border-radius: 2px;

    .item {
      display: flex;
      align-items: center;
      height: 32px;
      padding: 0 10px;
      color: #63656e;
      cursor: pointer;

      .name {
        margin-left: 6px;
      }

      &:hover {
        color: #3a84ff;
        background: #e1ecff;
      }
    }
  }

  .footer {
    display: flex;
    justify-content: center;
    height: 32px;
    padding: 0 10px;
    background-color: #fff;
    border-top: solid 2px #f0f1f5;

    .btn-group {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 70px;
      height: 100%;

      .monitor-btn {
        color: #3a84ff;
        cursor: pointer;

        &:hover {
          color: #699df4;
        }
      }
    }
  }
}
</style>
