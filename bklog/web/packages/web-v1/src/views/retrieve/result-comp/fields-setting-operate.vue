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
      @mouseenter="isHoverItem = true"
      @mouseleave="isHoverItem = false"
    >
      <span
        class="panel-name"
        :title="configItem.name"
        >{{ configItem.name }}</span
      >
      <div
        class="panel-operate"
        v-show="isShowEditIcon || isClickDelete"
        @click="e => e.stopPropagation()"
      >
        <i
          class="bk-icon edit-icon icon-edit-line"
          @click="emitOperate('edit')"
        ></i>
        <bk-popover
          ref="deletePopoverRef"
          ext-cls="config-tab-item"
          :on-hide="popoverHidden"
          :tippy-options="tippyOptions"
        >
          <i
            class="bk-icon edit-icon icon-delete"
            @click="handleClickDeleteConfigIcon"
          ></i>
          <template #content>
            <div>
              <div class="popover-slot">
                <span>{{ $t('确定要删除当前字段配置') }}?</span>
                <div class="popover-btn">
                  <bk-button
                    text
                    @click="emitOperate('delete')"
                    >{{ $t('确定') }}</bk-button
                  >
                  <bk-button
                    theme="danger"
                    text
                    @click="handleCancelDelete"
                    >{{ $t('取消') }}</bk-button
                  >
                </div>
              </div>
            </div>
          </template>
        </bk-popover>
      </div>
    </div>
    <div
      class="config-tab-item"
      v-show="configItem.isShowEdit"
      @click="e => e.stopPropagation()"
    >
      <bk-input
        v-model="nameStr"
        :class="['config-input', { 'input-error': isInputError }]"
        :maxlength="10"
        :placeholder="$t('请输入配置名')"
      ></bk-input>
      <div class="panel-operate">
        <i
          class="bk-icon icon-check-line"
          @click="emitOperate('update')"
        ></i>
        <i
          class="bk-icon icon-close-line-2"
          @click="emitOperate('cancel')"
        ></i>
      </div>
    </div>
  </div>
</template>

<script>

  export default {
    props: {
      configItem: {
        type: Object,
        require: true,
      },
    },
    data() {
      return {
        isHoverItem: false,
        isClickDelete: false, // 是否点击删除配置
        nameStr: '', // 编辑
        isInputError: false, // 名称是否非法
        tippyOptions: {
          placement: 'bottom',
          trigger: 'click',
          theme: 'light',
        },
      };
    },
    computed: {
      isShowEditIcon() {
        // 是否展示编辑或删除icon
        return this.isHoverItem && this.configItem.index !== 0;
      },
    },
    watch: {
      nameStr() {
        this.isInputError = false;
      },
    },
    methods: {
      /** 用户配置操作 */
      emitOperate(type) {
        // 赋值名称
        if (type === 'edit') this.nameStr = this.configItem.name;
        // 更新前判断名称是否合法
        if (type === 'update' && !this.nameStr) {
          this.isInputError = true;
          return;
        }
        const submitData = structuredClone(this.configItem);
        submitData.editStr = this.nameStr;
        this.$emit('operateChange', type, submitData);
      },
      popoverHidden() {
        this.$emit('setPopperInstance', true);
        setTimeout(() => {
          this.isClickDelete = false;
        }, 300);
      },
      handleCancelDelete() {
        this.$refs.deletePopoverRef.hideHandler();
      },
      handleClickDeleteConfigIcon() {
        this.isClickDelete = true;
        this.$emit('setPopperInstance', false);
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
    height: 40px;
    padding: 0 12px 0 4px;

    .config-input {
      width: 100px;

      :deep(.bk-form-input) {
        transform: translateY(-2px);
      }
    }

    .panel-name {
      max-width: 100px;
      padding-left: 20px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .panel-operate {
      margin-left: 10px;
      font-size: 14px;
      color: #979ba5;
      cursor: pointer;

      .edit-icon:hover {
        color: #3a84ff;
      }

      .icon-check-line {
        color: #3a84ff;
      }

      .icon-close-line-2 {
        color: #d7473f;
      }
    }

    .input-error {
      :deep(.bk-form-input) {
        border: 1px solid #d7473f;
      }
    }

    .popover-slot {
      padding: 8px 8px 4px;

      .popover-btn {
        margin-top: 6px;
        text-align: right;

        > :first-child {
          margin-right: 4px;
        }

        .bk-button-text {
          font-size: 12px;
        }
      }
    }
  }
</style>
