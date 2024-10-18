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
  <div class="check-container">
    <div
      v-show="!isShowAddInput"
      class="add-new"
      @click="handleShowAddInput"
    >
      <bk-button
        class="config-btn"
        :text="true"
      >
        <i class="bk-icon icon-plus-circle-shape"></i>
        <span>{{ btnStr }}</span>
      </bk-button>
    </div>
    <bk-form
      v-show="isShowAddInput"
      ref="checkInputForm"
      style="width: 100%"
      :label-width="0"
      :model="verifyData"
      :rules="verifyRules"
    >
      <bk-form-item
        property="inputStr"
        :error-display-type="'normal'"
      >
        <div class="config-tab-item">
          <bk-input
            v-model="verifyData.inputStr"
            :placeholder="placeholder"
            @enter="handleAddNew"
          ></bk-input>
          <div class="panel-operate">
            <i
              class="bk-icon icon-check-line"
              @click="handleAddNew"
            ></i>
            <i
              class="bk-icon icon-close-line-2"
              @click="handleCancelNew"
            ></i>
          </div>
        </div>
      </bk-form-item>
    </bk-form>
  </div>
</template>
<script>
  export default {
    model: {
      prop: 'value',
      event: 'change',
    },
    props: {
      value: {
        type: String,
        default: '',
      },
      btnStr: {
        type: String,
        default: '',
      },
      templateList: {
        type: Array,
        default: () => [],
      },
      placeholder: {
        type: String,
        default: '',
      },
    },
    data() {
      return {
        verifyData: {
          inputStr: '',
        },
        isShowAddInput: false,
        verifyRules: {
          inputStr: [
            {
              validator: this.checkName,
              message: this.$t('{n}不规范, 包含特殊符号', { n: this.$t('模板名称') }),
              trigger: 'blur',
            },
            {
              validator: this.checkExistName,
              message: this.$t('模板名重复'),
              trigger: 'blur',
            },
            {
              required: true,
              message: this.$t('必填项'),
              trigger: 'blur',
            },
            {
              max: 30,
              message: this.$t('不能多于{n}个字符', { n: 30 }),
              trigger: 'blur',
            },
          ],
        },
      };
    },
    computed: {
      inputStr: {
        get() {
          return this.value;
        },
        set(v) {
          this.$emit('change', v);
        },
      },
    },
    methods: {
      checkName() {
        if (this.verifyData.inputStr.trim() === '') return true;
        return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"{}|\s,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
          this.verifyData.inputStr.trim(),
        );
      },
      checkExistName() {
        return !this.templateList.some(item => item.name === this.verifyData.inputStr);
      },
      handleAddNew() {
        this.$refs.checkInputForm.validate().then(() => {
          this.inputStr = this.verifyData.inputStr;
          this.$emit('created', this.verifyData.inputStr);
          this.isShowAddInput = false;
        });
      },
      handleCancelNew() {
        this.verifyData.inputStr = '';
        this.isShowAddInput = false;
      },
      handleShowAddInput() {
        this.isShowAddInput = true;
        this.verifyData.inputStr = this.inputStr;
        this.$refs.checkInputForm.clearError();
      },
    },
  };
</script>
<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .check-container {
    .add-new {
      height: 40px;
      color: #3a84ff;
      cursor: pointer;

      .config-btn {
        width: 100%;
        height: 100%;
        font-size: 12px;
        line-height: 100%;
        @include flex-center();

        .bk-icon {
          transform: translateY(-1px);
        }
      }
    }

    .config-tab-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      height: 40px;

      .config-input {
        width: 100%;
      }

      .panel-name {
        max-width: 100px;
        padding-left: 20px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .panel-operate {
        flex-shrink: 0;
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
    }
  }
</style>
