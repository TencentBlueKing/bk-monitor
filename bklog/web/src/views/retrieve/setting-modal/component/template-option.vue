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
      @mouseenter="isHoverItem = true"
      @mouseleave="isHoverItem = false"
    >
      <span
        class="panel-name"
        :title="configItem.name"
      >
        {{ configItem.name }}
      </span>
      <div
        class="panel-operate"
        v-if="isShowEditIcon"
        @click="e => e.stopPropagation()"
      >
        <i
          class="bk-icon edit-icon icon-edit-line"
          @click="emitOperate('edit')"
        ></i>
        <i
          v-if="isShowDeleteIcon"
          class="bk-icon edit-icon icon-delete"
          @click="handleDelete"
        ></i>
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
        :placeholder="$t('请输入模板名')"
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
import { deepClone } from '@/components/monitor-echarts/utils';

export default {
  props: {
    configItem: {
      type: Object,
      require: true,
    },
    templateList: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      isHoverItem: false,
      nameStr: '', // 编辑
      isInputError: false, // 名称是否非法
      tippyOptions: {
        placement: 'bottom',
        trigger: 'click',
        theme: 'light',
        interactive: true,
      },
    };
  },
  computed: {
    isShowEditIcon() {
      // 是否展示编辑或删除icon
      return this.isHoverItem;
    },
    isShowDeleteIcon() {
      return this.templateList.length !== 1;
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
      const submitData = deepClone(this.configItem);
      submitData.editStr = this.nameStr;
      this.$emit('operate-change', type, submitData);
    },
    handleDelete() {
      if (!this.configItem.related_index_set_list.length) {
        this.emitOperate('delete');
        return;
      }
      const h = this.$createElement;
      const relatedList = this.configItem.related_index_set_list.map(item => item.index_set_name);
      const vNodes = relatedList.map(text =>
        h(
          'div',
          {
            style: {
              backgroundColor: 'rgba(151, 155, 165, .1)',
              borderColor: 'rgba(220, 222, 229, .6)',
              color: '#63656e',
              display: 'inline-block',
              fontSize: '12px',
              padding: '0 10px',
              marginBottom: '4px',
              borderRadius: '2px',
            },
          },
          text
        )
      );
      this.$bkInfo({
        title: this.$t(`当前模板在下列索引集中占用，取消占用后才能删除模板：{n}`, { n: this.configItem.name }),
        type: 'warning',
        subHeader: h(
          'div',
          {
            style: {
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              flexWrap: 'wrap',
            },
          },
          vNodes
        ),
      });
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

    .config-input {
      width: 120px;
    }

    .panel-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .panel-operate {
      flex-shrink: 0;
      margin-left: 6px;
      font-size: 16px;
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
