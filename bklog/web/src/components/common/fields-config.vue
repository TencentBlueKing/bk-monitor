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
  <div
    class="fields-config-tippy"
    v-bkloading="{ isLoading }"
    :id="id"
  >
    <!-- 字段显示设置 -->
    <div class="config-title">{{ $t('设置显示与排序') }}</div>
    <div class="field-list-container">
      <!-- 已选字段 -->
      <div class="field-list">
        <div class="list-title">
          <i18n path="显示字段（已选 {0} 条)">
            <span>{{ displayFieldNames.length }}</span>
          </i18n>
        </div>
        <vue-draggable
          v-bind="dragOptions"
          v-model="displayFieldNames"
        >
          <transition-group>
            <li
              v-for="(field, index) in displayFieldNames"
              class="list-item display-item"
              :key="field"
            >
              <span class="icon bklog-icon bklog-drag-dots"></span>
              <div class="field_name">{{ field }}</div>
              <div
                :class="['operate-button', disabledRemove && 'disabled']"
                @click="removeItem(index)"
              >
                {{ $t('删除') }}
              </div>
            </li>
          </transition-group>
        </vue-draggable>
      </div>
      <!-- 其他字段 -->
      <div class="field-list">
        <div class="list-title">{{ $t('其他字段') }}</div>
        <ul>
          <li
            v-for="field in restFieldNames"
            class="list-item rest-item"
            :key="field"
          >
            <div class="field_name">{{ field }}</div>
            <div
              class='operate-button'
              @click="addItem(field)"
            >
              {{ $t('添加') }}
            </div>
          </li>
        </ul>
      </div>
    </div>
    <div class="config-buttons">
      <!-- 确定、取消按钮 -->
      <bk-button
        style="margin-right: 8px"
        size="small"
        theme="primary"
        @click="handleConfirm"
        >{{ $t('确定') }}</bk-button
      >
      <bk-button
        style="margin-right: 24px"
        size="small"
        @click="handleCancel"
        >{{ $t('取消') }}</bk-button
      >
    </div>
  </div>
</template>

<script>
  import VueDraggable from 'vuedraggable';

  export default {
    components: {
      VueDraggable,
    },
    props: {
      id: {
        type: String,
        required: true,
      },
      isLoading: {
        type: Boolean,
        required: true,
      },
      total: {
        type: Array,
        required: true,
      },
      display: {
        type: Array,
        required: true,
      },
    },
    data() {
      return {
        totalFieldNames: [], // 所有的字段名
        displayFieldNames: [], // 展示的字段名

        dragOptions: {
          animation: 150,
          tag: 'ul',
          handle: '.bklog-drag-dots',
          'ghost-class': 'sortable-ghost-class',
        },
      };
    },
    computed: {
      restFieldNames() {
        return this.totalFieldNames.filter(field => !this.displayFieldNames.includes(field));
      },
      // 最少显示一个字段
      disabledRemove() {
        return this.displayFieldNames.length <= 1;
      },
    },
    watch: {
      total() {
        this.totalFieldNames = [...this.total];
        this.displayFieldNames = [...this.display];
      },
    },
    methods: {
      /**
       * 移除某个显示字段
       * @param {Number} index
       */
      removeItem(index) {
        !this.disabledRemove && this.displayFieldNames.splice(index, 1);
      },
      /**
       * 增加某个字段名
       * @param {String} fieldName
       */
      addItem(fieldName) {
        this.displayFieldNames.push(fieldName);
      },
      handleConfirm() {
        this.$emit('confirm', this.displayFieldNames);
      },
      handleCancel() {
        this.$emit('cancel');
      },
    },
  };
</script>

<style lang="scss">
  .fields-config-tippy > .tippy-tooltip {
    padding: 0;
    border: 1px solid #dcdee5;

    .fields-config-tippy {
      .config-title {
        padding: 20px 24px 0;
        font-size: 20px;
        font-weight: normal;
        line-height: 28px;
        color: #313238;
      }

      .field-list-container {
        max-height: 400px;
        padding: 10px 24px;
        overflow: auto;
        color: #63656e;

        .field-list {
          .list-title,
          .list-item,
          .operate-button {
            line-height: 32px;
          }

          .list-item {
            position: relative;
            display: flex;
            align-items: center;
            padding-left: 12px;
            margin-bottom: 2px;
            background-color: #f5f6fa;

            &.display-item {
              .bklog-drag-dots {
                width: 16px;
                font-size: 14px;
                color: #979ba5;
                text-align: left;
                cursor: move;
                transition: opacity 0.2s linear;
              }
            }

            .operate-button {
              position: absolute;
              top: 0;
              right: 0;
              width: 40px;
              text-align: center;
              cursor: pointer;

              &:hover {
                color: #3a84ff;
              }

              &.disabled {
                color: #dcdee5;
                cursor: not-allowed;
              }
            }
          }
        }
      }

      .config-buttons {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        height: 50px;
        background: #fafbfd;
        border-top: 1px solid #dcdee5;
      }
    }
  }
</style>
