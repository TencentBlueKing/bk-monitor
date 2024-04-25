<!--
  - Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
  - Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
  - BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
  -
  - License for BK-LOG 蓝鲸日志平台:
  - -------------------------------------------------------------------
  -
  - Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  - documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  - the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
  - and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  - The above copyright notice and this permission notice shall be included in all copies or substantial
  - portions of the Software.
  -
  - THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
  - LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
  - NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
  - WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  - SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
  -->

<template>
  <div class="filter-popover-content">
    <div class="title">{{ $t('是否可聚合') }}</div>
    <bk-radio-group
      v-model="polymerizable"
      class="king-radio-group"
    >
      <bk-radio value="0">{{ $t('不限') }}</bk-radio>
      <bk-radio value="1">{{ $t('是') }}</bk-radio>
      <bk-radio value="2">{{ $t('否') }}</bk-radio>
    </bk-radio-group>
    <div class="title">{{ $t('字段类型') }}</div>
    <div class="bk-button-group">
      <bk-button
        v-for="item in showFieldTypeList"
        :key="item"
        :class="fieldType === item ? 'is-selected' : ''"
        size="small"
        @click="fieldType = item"
      >
        <div class="custom-button">
          <span
            class="field-filter-option-icon"
            :class="item === 'any' ? '' : fieldTypeMap[item].icon"
          >
          </span>
          <span class="bk-option-name">{{ fieldTypeMap[item].name }}</span>
        </div>
      </bk-button>
    </div>
    <div class="button-container">
      <bk-button
        class="king-button mr10"
        size="small"
        theme="primary"
        @click="handleConfirm"
      >
        {{ $t('确定') }}
      </bk-button>
      <bk-button
        class="king-button"
        size="small"
        @click="handleCancel"
      >
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script>
let polymerizableCache;
let fieldTypeCache;

export default {
  props: {
    value: {
      // 浮层的显示状态
      type: Boolean,
      default: false
    }
  },
  data() {
    return {
      polymerizable: '0', // 可聚合 0 不限 1 聚合 2 不可聚合
      fieldType: 'any',
      fieldTypeList: ['any', 'number', 'keyword', 'text', 'date', '__virtual__'],
      fieldTypeMap: {
        any: {
          name: this.$t('不限'),
          icon: 'bk-icon icon-check-line'
        },
        number: {
          name: this.$t('数字'),
          icon: 'log-icon icon-number'
        },
        keyword: {
          name: this.$t('字符串'),
          icon: 'log-icon icon-string'
        },
        text: {
          name: this.$t('文本'),
          icon: 'log-icon icon-text'
        },
        date: {
          name: this.$t('时间'),
          icon: 'bk-icon icon-clock'
        },
        date_nanos: {
          name: this.$t('时间'),
          icon: 'bk-icon icon-clock'
        },
        __virtual__: {
          name: this.$t('虚拟字段'),
          icon: 'log-icon icon-ext'
        }
      }
    };
  },
  computed: {
    showFieldTypeList() {
      if (this.polymerizable === '1') return this.fieldTypeList.filter(item => item !== 'date');
      return this.fieldTypeList;
    }
  },
  watch: {
    '$route.params.indexId'() {
      // 切换索引集重置状态
      this.polymerizable = '0';
      this.fieldType = 'any';
    },
    value(val) {
      if (val) {
        polymerizableCache = this.polymerizable;
        fieldTypeCache = this.fieldType;
      } else {
        this.polymerizable = polymerizableCache;
        this.fieldType = fieldTypeCache;
      }
    }
  },
  methods: {
    handleConfirm() {
      polymerizableCache = this.polymerizable;
      fieldTypeCache = this.fieldType;
      this.$emit('confirm', {
        polymerizable: this.polymerizable,
        fieldType: this.fieldType
      });
      this.$emit('closePopover');
    },
    handleCancel() {
      this.$emit('closePopover');
    }
  }
};
</script>

<style lang="scss" scoped>
.filter-popover-content {
  padding: 8px 2px;

  .title {
    margin-bottom: 10px;
    font-size: 12px;
    line-height: 16px;
  }

  .king-radio-group {
    justify-content: space-between;
    margin-bottom: 22px;

    .bk-form-radio {
      margin-right: 24px;
      font-size: 12px;
    }
  }

  .bk-button-group {
    .bk-button {
      padding: 0 8px;
    }

    .custom-button {
      .bk-icon,
      .log-icon {
        margin-left: 0;
        font-size: 12px;
      }

      .icon-clock {
        position: relative;
        top: -1px;
      }

      .icon-ext {
        position: relative;
        top: -1px;
        margin-right: 4px;
      }
    }
  }

  .button-container {
    display: flex;
    justify-content: flex-end;
    margin-top: 24px;
  }

  :deep(.bk-select-prefix-icon) {
    font-size: 12px;
    color: #979ba5;
  }
}

.option-container {
  display: flex;
  align-items: center;

  &:hover .field-filter-option-icon {
    color: #3a84ff;
  }
}
</style>

<style lang="scss">
.bk-option {
  .field-filter-option-icon {
    width: 12px;
    margin-right: 8px;
    font-size: 12px;
    color: #979ba5;
  }

  &.is-selected .field-filter-option-icon {
    color: #3a84ff;
  }
}

.icon-ext {
  display: inline-block;
  width: 13px;
  font-size: 12px;
  transform: translateX(-1px) scale(0.8);
}
</style>
