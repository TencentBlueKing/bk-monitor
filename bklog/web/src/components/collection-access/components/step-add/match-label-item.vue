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
  <div class="match-container justify-sb">
    <template>
      <div class="customize-box" v-if="isEdit || onlyShowSelectEdit">
        <div class="customize-left justify-sb">
          <bk-form
            ref="keyRef"
            ext-cls="fill-key"
            :model="verifyData"
            :rules="rules"
            :label-width="0">
            <bk-form-item property="matchKey">
              <bk-input v-model="verifyData.matchKey" clearable></bk-input>
            </bk-form-item>
          </bk-form>
          <bk-select
            ext-cls="fill-operate"
            :clearable="false"
            :popover-min-width="116"
            v-model="matchOperator"
            @selected="() => handleOperateChange(false)">
            <bk-option
              v-for="item of expressOperatorList"
              :key="item.id"
              :name="item.name"
              :id="item.id">
            </bk-option>
          </bk-select>
        </div>
        <div class="customize-right justify-sb">
          <bk-input
            v-show="!expressInputIsDisabled && !isHaveCompared"
            v-model.trim="matchValue"
            clearable
            :ext-cls="`fill-value ${isValueError && 'input-error'}`">
          </bk-input>
          <bk-tag-input
            v-show="isHaveCompared"
            v-model="matchValueArr"
            allow-create
            free-paste
            has-delete-icon
            :ext-cls="`fill-value ${isValueError && 'tag-input-error'}`"
            @blur="handleValueBlur">
          </bk-tag-input>
          <div class="add-operate flex-ac">
            <span class="bk-icon icon-check-line" @click="handleAddMatch"></span>
            <span class="bk-icon icon-close-line-2" @click="handleCancelMatch"></span>
          </div>
        </div>
      </div>
    </template>
    <template v-if="!onlyShowSelectEdit">
      <div
        class="specify-main match-container justify-sb"
        v-show="!isEdit">
        <div :class="['specify-box', { 'is-edit': showEdit }]">
          <div class="specify-container">
            <span class="title-overflow" v-bk-overflow-tips>{{matchItem.key}}</span>
          </div>
          <div class="specify-container">
            <bk-select
              v-if="!isDialogItem"
              v-model="matchOperator"
              ext-cls="select-operator"
              :clearable="false"
              :popover-min-width="116"
              @selected="() => handleOperateChange(true)">
              <bk-option
                v-for="item of expressOperatorList"
                :key="item.id"
                :name="item.name"
                :id="item.id"
                :disabled="checkOperatorDisabled(item.id)">
              </bk-option>
            </bk-select>
            <div v-else class="operator">{{matchItem.operator}}</div>
            <span class="title-overflow" v-bk-overflow-tips>{{matchItem.value || '-'}}</span>
          </div>
        </div>
        <div class="edit flex-ac" v-if="showEdit">
          <span class="bk-icon icon-edit-line" @click="handleEditItem"></span>
          <span class="bk-icon icon-close-line-2" @click="handleDeleteItem"></span>
        </div>
      </div>
    </template>
  </div>
</template>
<script>

export default {
  props: {
    matchItem: {
      type: Object,
      require: true,
    },
    onlyShowSelectEdit: {
      type: Boolean,
      default: false,
    },
    showEdit: {
      type: Boolean,
      default: false,
    },
    submitEdit: {
      type: Function,
    },
    activeLabelEditID: {
      type: String,
      default: '',
    },
    labelSelector: {
      type: Array,
      require: true,
    },
    isDialogItem: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      verifyData: {
        matchKey: '',
      },
      rules: {
        matchKey: [
          {
            validator: this.checkName,
            message: this.$t('标签名称不符合正则{n}', { n: '([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9]' }),
            trigger: 'blur',
          },
          {
            required: true,
            message: this.$t('必填项'),
            trigger: 'blur',
          },
        ],
      },
      matchValue: '', // 自定义匹配值
      matchValueArr: [],
      matchOperator: 'In', // 自定义匹配操作
      catchOperator: 'In',
      expressOperatorList: [
        { // 表达式操作选项
          id: '=',
          name: '=',
        },
        {
          id: 'In',
          name: 'In',
        },
        {
          id: 'NotIn',
          name: 'NotIn',
        },
        {
          id: 'Exists',
          name: 'Exists',
        },
        {
          id: 'DoesNotExist',
          name: 'DoesNotExist',
        },
      ],
      isValueError: false,
      matchExpressOption: [],
      isEdit: false, // select编辑
    };
  },
  computed: {
    expressInputIsDisabled() {
      return ['Exists', 'DoesNotExist'].includes(this.matchOperator);
    },
    isHaveCompared() {
      return ['In', 'NotIn'].includes(this.matchOperator);
    },
    labelKeyStrList() {
      return this.labelSelector.filter(item => this.matchItem.key !== item.key).map(item => item.key);
    },
    validateFrontCheck() {
      if (!this.expressInputIsDisabled) {
        const matchValueError = this.isHaveCompared ? !this.matchValueArr.length : !this.matchValue;
        // key value 不能为空
        if (matchValueError) {
          matchValueError && (this.isValueError = true);
          return false;
        }
      };
      return true;
    },
  },
  watch: {
    matchValue() {
      return this.isValueError = false;
    },
    'matchValueArr.length': {
      handler() {
        return this.isValueError = false;
      },
    },
    activeLabelEditID(val) {
      if (val !== this.matchItem?.id) this.isEdit = false;
    },
    matchItem: {
      immediate: true,
      handler(val) {
        if (val.operator) {
          this.matchOperator = val.operator || 'In';
        }
      },
    },
  },
  created() {},
  methods: {
    handleAddMatch() {
      this.$refs.keyRef.validate().then(() => {
        if (!this.validateFrontCheck) return;

        let goodJob = true;

        if (typeof this.submitEdit === 'function') {
          const value = this.expressInputIsDisabled ? '' : (this.isHaveCompared ? this.matchValueArr.join(',') : this.matchValue);
          goodJob = this.submitEdit({
            key: this.verifyData.matchKey,
            operator: this.matchOperator,
            value,
          });
          if (typeof goodJob.then === 'function') {
            return goodJob.then(() => {
              this.resetStatus();
            });
          }
        }

        if (goodJob) {
          this.resetStatus();
        }
      });
    },
    handleCancelMatch() {
      if (!this.onlyShowSelectEdit) this.matchOperator = this.catchOperator;
      this.$emit('cancelEdit');
      this.isEdit = false;
    },
    handleEditItem() {
      const { key, operator, value } = this.matchItem;

      this.matchOperator = operator;
      this.catchOperator = operator;
      this.verifyData.matchKey = key;
      if (this.isHaveCompared) {
        const splitValue = value.split(',');
        this.matchValueArr = splitValue.length ? splitValue : [];
      } else {
        this.matchValue = value;
      };
      this.isEdit = true;
    },
    handleDeleteItem() {
      this.$emit('deleteItem');
    },
    handleValueBlur(input, list) {
      if (!input) return;
      this.matchValueArr = !list.length ? [input] : [...new Set([...this.matchValueArr, input])];
    },
    checkName() {
      if (this.verifyData.matchKey === '') return true;
      // eslint-disable-next-line no-useless-escape
      return /^([A-Za-z0-9][-A-Za-z0-9_.\/]*)?[A-Za-z0-9]$/.test(this.verifyData.matchKey);
    },
    resetStatus() {
      this.isEdit = false;
      this.isValueError = false;
      this.matchValue = '';
      this.verifyData.matchKey = '';
      this.matchValueArr = [];
    },
    checkOperatorDisabled(id) {
      return !this.matchItem.value && ['=', 'In', 'NotIn'].includes(id);
    },
    handleOperateChange(isExternal = false) {
      if (isExternal) {
        const { key, value } = this.matchItem;
        if (this.isHaveCompared) {
          const splitValue = value.split(',');
          this.matchValueArr = !!splitValue[0] ? splitValue : [];
        } else {
          this.matchValue = value;
        };
        this.submitEdit({
          key,
          operator: this.matchOperator,
          value: this.expressInputIsDisabled ? '' : value,
          isExternal: true,
        });
      } else {
        if (this.isHaveCompared) {
          if (!this.matchValueArr.length && !!this.matchValue) {
            const splitValue = this.matchValue.split(',');
            this.matchValueArr = !!splitValue ? splitValue : [];
          }
        } else {
          if (!!this.matchValueArr.length && !this.matchValue) {
            this.matchValue = this.matchValueArr[0];
          }
        }
      }
    },
  },
};
</script>
<style lang="scss" scoped>
@import '@/scss/mixins/flex.scss';

.match-container {
  width: 100%;

  .is-disabled {
    opacity: .6;
    cursor: no-drop;

    .operator,
    .select-operator {
      /* stylelint-disable-next-line declaration-no-important */
      color: #979ba5 !important;
    }
  }
}

.specify-main:hover .edit {
  visibility: visible;
}

.customize-box {
  padding: 4px 0;
  width: 100%;
  display: flex;
  align-items: center;

  .customize-left {
    width: 53%;
    flex-shrink: 0;
  }

  .customize-right {
    width: calc(47% - 60px);
    flex-shrink: 0;
  }

  .fill-key {
    width: 100%;
    position: relative;
    z-index: 999;
    margin-right: -1px;

    :deep(.bk-form-input) {
      border-top-right-radius: 0;
      border-bottom-right-radius: 0;
    }
  }

  .fill-operate {
    border-radius: 0;
    margin-right: -1px;
    min-width: 100px;

    &.is-focus {
      z-index: 999;
    }
  }

  .fill-value {
    width: 100%;
    flex-shrink: 0;

    .input {
      max-width: none;
    }

    :deep(.bk-form-input) {
      border-top-left-radius: 0;
      border-bottom-left-radius: 0;
    }
  }

  .add-operate {
    font-size: 18px;

    .bk-icon {
      cursor: pointer;
    }

    .icon-check-line {
      color: #2dcb56;
      margin: 0 7px;
    }

    .icon-close-line-2 {
      color: #c4c6cc;
      margin-right: 8px;
    }
  }
}

.flex-ac {
  @include flex-align();
}

.justify-sb {
  align-items: center;

  @include flex-justify(space-between);
}

:deep(.input-error .bk-form-input) {
  border-color: #ff5656;
}

:deep(.tag-input-error .bk-tag-input) {
  border-color: #ff5656;
}

.specify-box {
  width: 100%;
  display: flex;
  flex-flow: wrap;
  padding: 2px 8px;
  background: #f5f7fa;
  border-radius: 2px;
  font-size: 12px;

  .specify-container {
    width: 50%;
    padding: 0 6px;
    line-height: 30px;
    overflow: hidden;
    display: flex;
    justify-content: start;
    align-items: center;

    .operator,
    %operator {
      margin-right: 10px;
      padding: 0 6px;
      height: 24px;
      line-height: 24px;
      text-align: center;
      font-weight: 700;
      color: #ff9c01;
      background: #fff;
      border-radius: 2px;
    }

    .select-operator {
      padding: 0;
      height: 24px;
      line-height: 24px;
      border: none;

      @extend %operator;

      :deep(.bk-select-angle) {
        display: none;
      }

      :deep(.bk-select-name) {
        padding: 0 6px;
      }
    }
  }
}

.is-edit {
  width: calc( 100% - 60px );
}

.edit {
  visibility: hidden;
  color: #979ba5;
  font-size: 18px;

  .bk-icon {
    cursor: pointer;
  }

  .icon-edit-line {
    font-size: 16px;
    margin: 0 8px;
  }

  .icon-close-line-2 {
    margin-right: 8px;
  }
}
</style>
