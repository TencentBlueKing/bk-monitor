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
    <div
      class="config-tab-item"
      v-show="!configItem.isShowEdit"
      @click="emitOperate('click')"
    >
      <span
        ref="panelNameRef"
        class="panel-name"
        :title="configItem.name"
        >{{ configItem.name }}</span
      >
      <div
        v-if="hasMoreIcon"
        class="panel-operate"
        @click="e => e.stopPropagation()"
      >
        <SettingMoreMenu @menu-click="handleMenuClick" />
      </div>
    </div>
    <div
      class="config-tab-item"
      v-show="configItem.isShowEdit"
      @click="e => e.stopPropagation()"
    >
      <bk-input
        ref="inputRef"
        v-model="nameStr"
        :class="['config-input', { 'input-error': isInputError }]"
        :maxlength="10"
        :placeholder="$t('请输入配置名')"
        size="small"
        @blur="handleUpdateName"
        @enter="handleUpdateName"
      ></bk-input>
    </div>
    <div style="display: none">
      <div
        ref="deleteTipRef"
        class="delete-tip-container bklog-v3-popover-tag"
      >
        <span class="delete-tip-description">{{ $t('确定要删除当前字段配置') }}?</span>
        <div class="delete-tip-operation">
          <bk-button
            text
            @click="handleDeleteVerify"
            >{{ $t('确定') }}</bk-button
          >
          <bk-button
            theme="danger"
            text
            @click="handleDeleteTipPopoverHide"
            >{{ $t('取消') }}</bk-button
          >
        </div>
      </div>
    </div>
  </div>
</template>

<script>
  import { debounce } from 'lodash-es';

  import SettingMoreMenu from './setting-more-menu';

  export default {
    components: {
      SettingMoreMenu,
    },
    props: {
      configItem: {
        type: Object,
        require: true,
      },
      /** 是否渲染 更多icon */
      hasMoreIcon: {
        type: Boolean,
        default: true,
      },
    },
    data() {
      return {
        isClickDelete: false, // 是否点击删除配置
        nameStr: '', // 编辑
        isInputError: false, // 名称是否非法
        deleteTipInstance: null,
      };
    },

    watch: {
      nameStr() {
        this.isInputError = false;
      },
    },
    methods: {
      /** 用户配置操作 */
      async emitOperate(type) {
        // 进入编辑状态
        if (type === 'edit') {
          this.nameStr = this.configItem.name;
        }
        const submitData = structuredClone(this.configItem);
        submitData.editStr = this.nameStr;
        this.$emit('operateChange', type, submitData);
        // 进入编辑态时 focus 聚焦到input框
        this.$nextTick(() => {
          type === 'edit' && this.$refs.inputRef?.$el?.querySelector('.bk-form-input')?.focus?.();
        });
      },

      /**
       * @description input 失焦/enter 后更新字段名称回调方法
       *
       */
      handleUpdateName: debounce(function () {
        let execOperate = 'update';
        // 更新前判断名称是否合法
        if (!this.nameStr) {
          this.isInputError = true;
          return;
        }
        // 如果名称未修改则不请求接口直接切换查看状态
        if (this.nameStr === this.configItem.name) {
          execOperate = 'cancel';
        }

        this.emitOperate(execOperate);
      }, 300),

      /**
       * @description 更多 下拉菜单 点击事件后回调
       * @param type
       *
       */
      handleMenuClick(type) {
        if (type !== 'delete') {
          this.emitOperate(type);
          return;
        }
        this.handleDeleteTipPopoverShow();
      },

      /**
       * @description 确认删除回调
       *
       */
      handleDeleteVerify() {
        this.handleDeleteTipPopoverHide();
        this.emitOperate('delete');
      },

      /**
       * @description 打开 删除确认提示 popover
       *
       */
      async handleDeleteTipPopoverShow() {
        if (this.deleteTipInstance) {
          this.handleDeleteTipPopoverHide();
        }
        if (!this.$refs?.panelNameRef || !this.$refs?.deleteTipRef) {
          return;
        }

        this.deleteTipInstance = this.$bkPopover(this.$refs?.panelNameRef, {
          content: this.$refs.deleteTipRef,
          trigger: 'click',
          animateFill: false,
          placement: 'bottom-start',
          theme: 'light field-setting-item-delete-tips',
          arrow: true,
          interactive: true,
          boundary: 'viewport',
          distance: 0,
          onHidden: () => {
            this.deleteTipInstance?.destroy?.();
            this.deleteTipInstance = null;
          },
        });
        await this.$nextTick();
        this.deleteTipInstance?.show();
      },

      /**
       * @description 关闭 删除确认提示 popover
       *
       */
      handleDeleteTipPopoverHide() {
        this.deleteTipInstance?.hide?.();
        this.deleteTipInstance?.destroy?.();
        this.deleteTipInstance = null;
      },
    },
  };
</script>

<style lang="scss" scoped>
  .config-tab-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    height: 36px;
    padding: 0 4px;

    &:hover {
      .panel-operate {
        :deep(.field-setting-more) {
          &.field-setting-more {
            .popover-trigger {
              display: flex;
            }
          }
        }
      }
    }

    /* stylelint-disable-next-line no-descending-specificity */
    .panel-operate {
      flex-shrink: 0;

      :deep(.field-setting-more) {
        /* stylelint-disable-next-line no-descending-specificity */
        &.field-setting-more {
          /* stylelint-disable-next-line no-descending-specificity */
          .popover-trigger {
            display: none;

            &.is-active {
              display: flex;
            }
          }
        }
      }
    }

    .config-input {
      display: flex;
      align-items: center;
      width: 100%;
      height: 100%;

      // :deep(.bk-form-input) {
      //   transform: translateY(-2px);
      // }
    }

    .panel-name {
      flex-basis: auto;
      min-width: 0;
      padding-left: 8px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
</style>
<style lang="scss">
  .field-setting-item-delete-tips-theme {
    .delete-tip-container {
      padding: 8px 14px;
      font-size: 12px;

      .delete-tip-operation {
        margin-top: 6px;
        text-align: right;

        .bk-button-text {
          font-size: 12px;

          &:first-child {
            margin-right: 4px;
          }
        }
      }
    }
  }
</style>
