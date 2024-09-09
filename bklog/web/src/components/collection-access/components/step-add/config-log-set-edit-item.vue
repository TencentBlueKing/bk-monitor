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
  <div class="config-item">
    <div class="config-item-title flex-ac">
      <span v-if="isLabelEdit">{{ $t('按标签选择{n}', { n: isNode ? 'Node' : 'Container' }) }}</span>
      <span v-else>{{ $t('按注解选择{n}', { n: isNode ? 'Node' : 'Container' }) }}</span>
      <span
        class="bk-icon icon-delete"
        @click="handleDeleteConfigParamsItem"
      >
      </span>
    </div>
    <div
      v-if="!handleEdit"
      class="select-label flex-ac"
    >
      <div
        class="manually"
        @click="handleEdit = true"
      >
        <span class="bk-icon icon-close-circle"></span>
        <span v-if="isLabelEdit">{{ $t('手动输入标签') }}</span>
        <span v-else>{{ $t('手动输入annotation') }}</span>
      </div>
      <div
        v-if="isLabelEdit"
        class="select"
        @click="handelShowDialog"
      >
        <span class="bk-icon icon-close-circle"></span>
        <span>{{ $t('选择已有标签') }}</span>
      </div>
    </div>
    <match-label-item
      v-else
      :label-selector="config[selectorType]"
      :submit-edit="handleSubmitExpressions"
      :is-label-edit="isLabelEdit"
      @cancel-edit="handleEdit = false"
      only-show-select-edit
    />
    <div class="specify-domain">
      <template>
        <match-label-item
          v-for="labItem in config[selectorType]"
          :key="labItem.id"
          :is-label-edit="isLabelEdit"
          :label-selector="config[selectorType]"
          :match-item="labItem"
          :submit-edit="val => handleLabelEdit(labItem.id, val)"
          show-edit
          @delete-item="deleteLabItem(labItem.id)"
        />
      </template>
    </div>
  </div>
</template>
<script>
  import EmptyStatus from '@/components/empty-status';
  import matchLabelItem from './match-label-item';
  import { random } from '@/common/util';

  export default {
    components: {
      EmptyStatus,
      matchLabelItem,
    },
    props: {
      editType: {
        type: String,
        required: true,
      },
      config: {
        type: Object,
        required: true,
      },
      isNode: {
        type: Boolean,
        required: true,
      },
    },
    data() {
      return {
        handleEdit: false,
      };
    },
    computed: {
      selectorType() {
        return this.editType === 'label' ? 'labelSelector' : 'annotationSelector';
      },
      isLabelEdit() {
        return this.editType === 'label';
      },
    },
    methods: {
      handleDeleteConfigParamsItem() {
        this.$emit('delete-config-params-item', this.editType);
      },
      // 手动添加表达式
      handleSubmitExpressions(val) {
        const selector = this.config?.[this.selectorType];
        const isRepeat = selector.some(item => {
          return val.key === item.key && val.value === item.value && val.operator === item.operator;
        });
        return new Promise(resolve => {
          if (!isRepeat) {
            let type;
            if (this.isLabelEdit) {
              type = val.operator === '=' ? 'match_labels' : 'match_expressions';
            } else {
              type = 'match_annotations';
            }
            selector.unshift({
              ...val,
              id: random(10),
              type,
            });
            this.$emit('config-change', {
              [this.selectorType]: selector,
            });
          }
          this.handleEdit = false;
          resolve(true);
        });
      },
      handelShowDialog() {
        this.$emit('show-dialog');
      },
      handleLabelEdit(matchID, newValue) {
        const selector = this.config?.[this.selectorType];

        const isRepeat = selector.some(item => {
          return newValue.key === item.key && newValue.value === item.value && newValue.operator === item.operator;
        });

        let type;
        if (this.isLabelEdit) {
          type = newValue.operator === '=' ? 'match_labels' : 'match_expressions';
        } else {
          type = 'match_annotations';
        }

        return new Promise(resolve => {
          const labelIndex = selector.findIndex(item => item.id === matchID);
          if (!isRepeat) {
            const newMatchObject = { ...selector[labelIndex], ...newValue, type };
            selector.splice(labelIndex, 1, newMatchObject);
          } else {
            if (newValue?.isExternal) selector.splice(labelIndex, 1);
          }
          resolve(true);
        });
      },
      deleteLabItem(matchID) {
        const selector = this.config?.[this.selectorType];
        const labelIndex = selector.findIndex(item => item.id === matchID);
        selector.splice(labelIndex, 1);
      },
    },
  };
</script>
<style lang="scss" scoped>
  .config-item-title {
    padding-bottom: 8px;

    :last-child {
      margin-left: 8px;
      cursor: pointer;
    }

    .icon-delete {
      display: none;
      font-size: 14px;
      color: #ea3636;
      cursor: pointer;
    }
  }

  .config-item {
    padding: 8px 12px;
    margin-bottom: 12px;
    font-size: 12px;
    border-radius: 2px;

    .select-label {
      margin-top: 4px;
      color: #3a84ff;

      .manually {
        margin-right: 15px;
        cursor: pointer;
      }

      .select {
        position: relative;
        margin-left: 15px;
        cursor: pointer;

        &::before {
          position: absolute;
          top: 4px;
          left: -14px;
          display: inline-block;
          width: 1px;
          height: 14px;
          content: ' ';
          background: #eaebf0;
        }
      }
    }

    &.hover-light:hover {
      background: #f5f7fa;
    }

    &:hover .icon-delete {
      display: inline-block;
    }

    .specify-domain {
      max-height: 210px;
      margin-top: 8px;
      overflow-y: auto;

      > div {
        padding: 4px 0;
      }
    }
  }
</style>
