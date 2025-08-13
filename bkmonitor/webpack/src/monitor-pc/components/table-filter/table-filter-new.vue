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
  <span :class="['table-filter-wrap', { 'is-active': value.length }]">
    <bk-popover
      ref="selectDropdown"
      ext-cls="menu-list-wrapper"
      trigger="click"
      placement="bottom-start"
      theme="light menu-list-wrapper"
      animation="slide-toggle"
      :transfer="false"
      :arrow="false"
      :tippy-options="tippyOptions"
      :offset="-1"
      :distance="5"
    >
      <span
        ref="target"
        class="table-title-wrap"
        @click="handleShowDropMenu"
      >
        <span class="columns-title">{{ title }}</span>
        <i class="icon-monitor icon-filter-fill" />
      </span>
      <span
        ref="menuList"
        slot="content"
        class="menu-list-wrap"
      >
        <ul class="menu-list">
          <li
            v-for="(item, index) in localList"
            :key="index"
            class="list-item"
            @click="item.checked = !item.checked"
          >
            <span @click.stop>
              <bk-checkbox
                v-model="item.checked"
                :true-value="true"
                :false-value="false"
              />
            </span>
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
              @click="handleCancel"
            >
              {{ $t('重置') }}
            </span>
          </div>
        </div>
      </span>
    </bk-popover>
  </span>
</template>
<script lang="ts">
import { Component, Emit, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { deepClone } from 'monitor-common/utils/utils';

export interface IListItem {
  checked: boolean;
  id: number | string;
  name: number | string;
}

@Component({ name: 'table-filter' })
export default class TableFilter extends Vue {
  @Prop({ default: '', type: String }) readonly title: string;
  @Prop({ default: () => [], type: Array }) readonly value: any;

  @Prop({ default: () => [], type: Array }) readonly list: IListItem[];

  @Prop({ default: () => ({}), type: Object }) readonly tippyOptions: any;

  @Ref('target') readonly targetRef: HTMLElement;
  @Ref('menuList') readonly menuListRef: HTMLElement;

  private localValue: any = [];

  private localList: any = [];

  @Watch('value', { immediate: true, deep: true })
  @Watch('list', { deep: true })
  handleLocalListChange() {
    this.localList = this.list.map(item => {
      const temp = deepClone(item);
      temp.checked = this.value.includes(temp.id);
      return temp;
    });
  }

  @Emit('change')
  emitValueChange(v?) {
    return v || this.localList.filter(item => item.checked).map(item => item.id);
  }

  private handleShowDropMenu() {
    this.handleLocalListChange();
  }

  private handleConfirm() {
    this.emitValueChange();
    this.close();
  }

  private handleCancel() {
    this.emitValueChange([]);
    this.close();
  }

  private getPopoverInstance() {
    return this.$refs.selectDropdown.instance;
  }
  private show() {
    const popover = this.getPopoverInstance();
    popover.show();
  }
  private close() {
    const popover = this.getPopoverInstance();
    popover.hide();
  }
}
</script>

<style lang="scss" scoped>
.table-filter-wrap {
  .table-title-wrap {
    cursor: pointer;
  }
}

.is-active {
  .table-title-wrap {
    .icon-filter-fill {
      color: #699df4;
    }
  }
}
</style>

<style lang="scss">
.menu-list-wrapper-theme {
  width: 100%;

  /* stylelint-disable-next-line declaration-no-important */
  padding: 0 !important;
  border-radius: 0;
  box-shadow: 0 0 6px rgba(204, 204, 204, 0.3);

  .menu-list-wrap {
    display: inline-block;
    min-width: 100px;
    background-color: #fff;

    .menu-list {
      display: flex;
      flex-direction: column;
      max-height: 250px;
      padding: 6px 0;
      overflow-y: auto;
      border-radius: 2px;

      .list-item {
        display: flex;
        flex-shrink: 0;
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
      height: 29px;
      border-top: solid 1px #f0f1f5;

      .btn-group {
        display: flex;
        align-items: center;
        justify-content: space-between;
        // width: 70px;
        height: 100%;
        padding: 0 10px;

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
}
</style>
