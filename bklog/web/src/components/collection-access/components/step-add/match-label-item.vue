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
  <div class="match-container justify-sb">
    <template>
      <div
        v-if="isEdit || onlyShowSelectEdit"
        class="customize-box"
      >
        <div class="customize-left justify-sb">
          <bk-form
            ref="keyRef"
            ext-cls="fill-key"
            :label-width="0"
            :model="verifyData"
            :rules="rules"
          >
            <bk-form-item property="matchKey">
              <bk-input
                v-model="verifyData.matchKey"
                clearable
              ></bk-input>
            </bk-form-item>
          </bk-form>
          <bk-select
            ext-cls="fill-operate"
            v-model="matchOperator"
            :clearable="false"
            :popover-min-width="116"
            @selected="() => handleOperateChange(false)"
          >
            <bk-option
              v-for="item of expressOperatorList"
              :id="item.id"
              :key="item.id"
              :name="item.name"
            >
            </bk-option>
          </bk-select>
        </div>
        <div class="customize-right justify-sb">
          <bk-input
            v-model.trim="matchValue"
            v-show="!expressInputIsDisabled && !isHaveCompared"
            :ext-cls="`fill-value ${isValueError && 'input-error'}`"
            clearable
          >
          </bk-input>
          <bk-tag-input
            v-model="matchValueArr"
            v-show="isHaveCompared"
            :ext-cls="`fill-value ${isValueError && 'tag-input-error'}`"
            allow-create
            free-paste
            has-delete-icon
            @blur="handleValueBlur"
          >
          </bk-tag-input>
          <div class="add-operate flex-ac">
            <span
              class="bk-icon icon-check-line"
              @click="handleAddMatch"
            ></span>
            <span
              class="bk-icon icon-close-line-2"
              @click="handleCancelMatch"
            ></span>
          </div>
        </div>
      </div>
    </template>
    <template v-if="!onlyShowSelectEdit">
      <div
        class="specify-main match-container justify-sb"
        v-show="!isEdit"
      >
        <div :class="['specify-box', { 'is-edit': showEdit }]">
          <div class="specify-container">
            <span
              class="title-overflow"
              v-bk-overflow-tips
              >{{ matchItem.key }}</span
            >
          </div>
          <div class="specify-container">
            <bk-select
              v-if="!isDialogItem"
              ext-cls="select-operator"
              v-model="matchOperator"
              :clearable="false"
              :popover-min-width="116"
              @selected="() => handleOperateChange(true)"
            >
              <bk-option
                v-for="item of expressOperatorList"
                :disabled="checkOperatorDisabled(item.id)"
                :id="item.id"
                :key="item.id"
                :name="item.name"
              >
              </bk-option>
            </bk-select>
            <div
              v-else
              class="operator"
            >
              {{ matchItem.operator }}
            </div>
            <span
              class="title-overflow"
              v-bk-overflow-tips
              >{{ matchItem.value || '-' }}</span
            >
          </div>
        </div>
        <div
          v-if="showEdit"
          class="edit flex-ac"
        >
          <span
            class="bk-icon icon-edit-line"
            @click="handleEditItem"
          ></span>
          <span
            class="bk-icon icon-close-line-2"
            @click="handleDeleteItem"
          ></span>
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
        default: () => ({
          key: '',
          operator: 'In',
          value: '',
        }),
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
      isLabelEdit: {
        type: Boolean,
        default: true,
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
          {
            // 表达式操作选项
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
            // eslint-disable-next-line vue/no-side-effects-in-computed-properties
            matchValueError && (this.isValueError = true);
            return false;
          }
        }
        return true;
      },
    },
    watch: {
      matchValue() {
        return (this.isValueError = false);
      },
      'matchValueArr.length': {
        handler() {
          return (this.isValueError = false);
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
          if (!this.isLabelEdit) {
            this.expressOperatorList.shift();
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
            const value = this.expressInputIsDisabled
              ? ''
              : this.isHaveCompared
                ? this.matchValueArr.join(',')
                : this.matchValue;
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
        this.$emit('cancel-edit');
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
        }
        this.isEdit = true;
      },
      handleDeleteItem() {
        this.$emit('delete-item');
      },
      handleValueBlur(input, list) {
        if (!input) return;
        this.matchValueArr = !list.length ? [input] : [...new Set([...this.matchValueArr, input])];
      },
      checkName() {
        if (this.verifyData.matchKey === '') return true;

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
          }
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

  /* stylelint-disable no-descending-specificity */
  .match-container {
    width: 100%;

    .is-disabled {
      cursor: no-drop;
      opacity: 0.6;

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
    display: flex;
    align-items: center;
    width: 100%;
    padding: 4px 0;

    .customize-left {
      flex-shrink: 0;
      width: 53%;
    }

    .customize-right {
      flex-shrink: 0;
      width: calc(47% - 60px);
    }

    .fill-key {
      position: relative;
      z-index: 999;
      width: 100%;
      margin-right: -1px;

      :deep(.bk-form-input) {
        border-top-right-radius: 0;
        border-bottom-right-radius: 0;
      }
    }

    .fill-operate {
      min-width: 100px;
      margin-right: -1px;
      border-radius: 0;

      &.is-focus {
        z-index: 999;
      }
    }

    .fill-value {
      flex-shrink: 0;
      width: 100%;

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
        margin: 0 7px;
        color: #2dcb56;
      }

      .icon-close-line-2 {
        margin-right: 8px;
        color: #c4c6cc;
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
    display: flex;
    flex-flow: wrap;
    width: 100%;
    padding: 2px 8px;
    font-size: 12px;
    background: #f5f7fa;
    border-radius: 2px;

    .specify-container {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      width: 50%;
      padding: 0 6px;
      overflow: hidden;
      line-height: 30px;

      .operator,
      %operator {
        height: 24px;
        padding: 0 6px;
        margin-right: 10px;
        font-weight: 700;
        line-height: 24px;
        color: #ff9c01;
        text-align: center;
        background: #fff;
        border-radius: 2px;
      }

      .select-operator {
        height: 24px;
        padding: 0;
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
    width: calc(100% - 60px);
  }

  .edit {
    font-size: 18px;
    color: #979ba5;
    visibility: hidden;

    .bk-icon {
      cursor: pointer;
    }

    .icon-edit-line {
      margin: 0 8px;
      font-size: 16px;
    }

    .icon-close-line-2 {
      margin-right: 8px;
    }
  }
</style>
