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
        class="panel-name"
        :title="configItem.name"
        >{{ configItem.name }}</span
      >
      <div
        v-if="hasMoreIcon"
        class="panel-operate"
        @click="e => e.stopPropagation()"
      >
        <SettingMoreMenu @menuClick="emitOperate" />
        <!-- <i
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
        </bk-popover> -->
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
        size="small"
        :placeholder="$t('请输入配置名')"
        @blur="emitOperate('update')"
      ></bk-input>
    </div>
  </div>
</template>

<script>
  import { deepClone } from '@/components/monitor-echarts/utils';
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
    },
    data() {
      return {
        isClickDelete: false, // 是否点击删除配置
        nameStr: '', // 编辑
        isInputError: false, // 名称是否非法
        tippyOptions: {
          placement: 'bottom-end',
          trigger: 'click',
          theme: 'light',
          arrow: false,
          distance: -2,
          offset: '8 0',
        },
      };
    },
    computed: {
      hasMoreIcon() {
        // 是否展示编辑或删除icon
        return this.configItem.index !== 0;
      },
    },
    watch: {
      nameStr() {
        this.isInputError = false;
      },
    },
    methods: {
      /** 用户配置操作 */
      async emitOperate(type) {
        let finalType = type;
        // 进入编辑状态
        if (finalType === 'edit') {
          this.nameStr = this.configItem.name;
        }
        // 更新字段名称
        if (finalType === 'update') {
          // 更新前判断名称是否合法
          if (!this.nameStr) {
            this.isInputError = true;
            return;
          }
          // 如果名称未修改则不请求接口直接切换查看状态
          if (this.nameStr === this.configItem.name) {
            finalType = 'cancel';
          }
        }
        const submitData = deepClone(this.configItem);
        submitData.editStr = this.nameStr;
        this.$emit('operateChange', finalType, submitData);
        this.$nextTick(() => {
          type === 'edit' && this.$refs.inputRef?.$el?.querySelector('.bk-form-input')?.focus?.();
        });
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
