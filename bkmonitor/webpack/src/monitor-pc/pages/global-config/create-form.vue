<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
  <div class="create-form">
    <bk-form
      ref="createForm"
      :model="model"
      :rules="rules"
      v-bind="formProps"
    >
      <bk-form-item
        v-for="(item, index) in formList"
        :key="index"
        class="create-form-item"
        v-bind="item.formItemProps"
        :icon-offset="item.type === 'input' && item.formChildProps.type === 'number' ? 358 : 8"
      >
        <component
          :is="'bk-' + item.type"
          v-bind="item.formChildProps"
          v-model="model[item.formItemProps.property]"
          :style="{ width: item.type === 'input' && item.formChildProps.type === 'number' ? '120px' : '' }"
        >
          <template v-if="item.type === 'select'">
            <bk-option
              v-for="option in item.formChildProps.options"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            />
          </template>
          <template v-else-if="item.type === 'checkbox-group'">
            <bk-checkbox
              v-for="option in item.formChildProps.options"
              :key="option.id"
              :value="option.id"
            >
              {{ option.name }}
            </bk-checkbox>
          </template>
          <template v-else-if="item.type === 'radio-group'">
            <bk-radio
              v-for="option in item.formChildProps.options"
              :key="option.id"
              :value="option.id"
            >
              {{ option.name }}
            </bk-radio>
          </template>
        </component>
        <span
          v-if="item.type === 'tag-input' && model[item.formItemProps.property]?.length"
          v-bk-tooltips="{ content: $t('复制'), placements: ['top'] }"
          class="icon-monitor icon-mc-copy tag-input-copy-btn"
          @click="copyTagInputValue(model[item.formItemProps.property])"
        />
        <template v-if="item.formItemProps.help_text">
          <div class="form-desc">
            {{ item.formItemProps.help_text }}
          </div>
        </template>
      </bk-form-item>
      <bk-form-item>
        <bk-button
          v-authority="{ active: !authority.MANAGE_GLOBAL_AUTH }"
          class="footer-btn"
          theme="primary"
          :loading="isChecking"
          @click="
            authority.MANAGE_GLOBAL_AUTH ? handleConfirm() : handleShowAuthorityDetail(authorityMap.MANAGE_GLOBAL_AUTH)
          "
        >
          {{ $t('提交') }}
        </bk-button>
        <bk-button
          theme="default"
          @click="handleReset"
        >
          {{ $t('重置') }}
        </bk-button>
      </bk-form-item>
    </bk-form>
  </div>
</template>
<script>
import { copyText } from 'monitor-common/utils/utils';
export default {
  name: 'CreateForm',
  inject: ['authority', 'handleShowAuthorityDetail', 'authorityMap'],
  props: {
    // 验证信息
    rules: {
      type: Object,
      default() {
        return {};
      },
    },
    // form model数据集
    model: {
      type: Object,
      required: true,
    },
    // form配置列表
    formList: {
      type: Array,
      required: true,
    },
    validate: Function,
    // form属性
    formProps: {
      type: Object,
      default() {
        return {
          'label-width': 200,
        };
      },
    },
  },
  data() {
    return {
      isChecking: false,
    };
  },
  methods: {
    // 点击提交触发
    handleConfirm() {
      this.$emit('save', this.$refs.createForm.validate);
    },
    // 点击重置
    handleReset() {
      this.$emit('reset', this.model);
    },
    // 复制标签输入框的值
    copyTagInputValue(values) {
      const text = values
        .map(v => {
          if (typeof v === 'object') {
            return JSON.stringify(v);
          }
          return v;
        })
        .join(',');
      copyText(text, msg => {
        this.$bkMessage({
          message: msg,
          theme: 'error',
        });
        return;
      });
      this.$bkMessage({
        message: this.$t('复制成功'),
        theme: 'success',
      });
    },
  },
};
</script>
<style lang="scss" scoped>
.create-form {
  max-width: 656px;

  &-item {
    :deep(.bk-select) {
      background-color: #fff;
    }

    :deep(.bk-form-radio) {
      margin-right: 30px;

      .bk-checkbox {
        background-color: #fff;
      }
    }

    :deep(.bk-form-checkbox) {
      margin-right: 30px;
    }

    :deep(.bk-label) {
      min-width: 120px;

      span {
        display: inline-block;
        line-height: 20px;
      }
    }

    :deep(.bk-tag-selector) {
      .bk-select-dropdown {
        min-height: 27px;
      }
    }

    .form-desc {
      margin-top: 4px;
      font-size: 12px;
      line-height: 16px;
      color: #979ba5;
    }

    .tag-input-copy-btn {
      position: absolute;
      top: 0;
      right: -32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      cursor: pointer;
    }
  }

  .footer-btn {
    margin-right: 10px;
  }

  :deep(.bk-form-control) {
    line-height: 30px;
  }
}
</style>
