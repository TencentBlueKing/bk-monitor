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
  <bk-dialog
    width="600"
    :auto-close="false"
    :mask-close="false"
    :show-footer="false"
    :title="$t('label-预览').replace('label-', '')"
    :value="isShowDialog"
    header-position="left"
    theme="primary"
    @cancel="handelCancelDialog"
  >
    <div
      class="view-main"
      v-bkloading="{ isLoading: loading }"
    >
      <template v-if="viewList.length">
        <div
          v-for="(vItem, vIndex) in viewList"
          class="view-container"
          :key="vIndex"
        >
          <div
            :class="['view-title', !vItem.isShowTarget && 'hidden-bottom']"
            @click="handleClickTitle(vIndex, vItem.isShowTarget)"
          >
            <div
              class="match title-overflow"
              v-bk-overflow-tips
            >
              <span>{{ vItem.group }}</span>
            </div>
            <i18n
              class="hit"
              path="已命中 {0} 个内容"
            >
              <span class="number">{{ vItem.total }}</span>
            </i18n>
          </div>
          <div
            class="view-target"
            v-show="vItem.isShowTarget"
          >
            <div
              v-for="(item, iIndex) in vItem.items"
              class="title-overflow"
              v-bk-overflow-tips
              :key="iIndex"
            >
              <span>{{ item }}</span>
            </div>
          </div>
        </div>
      </template>
      <empty-status
        v-else
        :show-text="false"
        empty-type="empty"
      >
        <p>{{ $t('暂无命中内容') }}</p>
      </empty-status>
    </div>
  </bk-dialog>
</template>
<script>
  import EmptyStatus from '@/components/empty-status';

  export default {
    components: {
      EmptyStatus,
    },
    props: {
      isShowDialog: {
        type: Boolean,
        default: false,
      },
      viewQueryParams: {
        type: Object,
        require: true,
      },
      isNode: {
        type: Boolean,
        require: true,
      },
    },
    data() {
      return {
        isShowList: false,
        viewList: [],
        loading: false,
      };
    },
    computed: {},
    watch: {
      isShowDialog(val) {
        if (val) {
          this.loading = true;
          this.$http
            .request('container/getLabelHitView', {
              data: this.viewQueryParams,
            })
            .then(res => {
              this.viewList = res.data.map(item => ({ ...item, isShowTarget: true }));
            })
            .finally(() => {
              this.loading = false;
            });
        } else {
          setTimeout(() => {
            this.viewList = [];
          }, 1000);
        }
      },
    },
    methods: {
      handelCancelDialog() {
        this.$emit('update:is-show-dialog', false);
      },
      handleClickTitle(index, showValue) {
        this.viewList[index].isShowTarget = !showValue;
      },
    },
  };
</script>
<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  .view-main {
    min-height: 200px;
    max-height: 600px;
    padding: 0 6px;
    margin-top: -14px;
    overflow-y: auto;
    font-size: 12px;

    .view-container {
      box-sizing: border-box;
      max-height: 264px;
      margin-bottom: 12px;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .view-title {
        padding: 6px 12px;
        cursor: pointer;
        background: #f0f1f5;
        border-bottom: 1px solid #dcdee5;

        @include flex-justify(space-between);

        .match {
          font-weight: 700;
          color: #63656e;
        }

        .number {
          font-weight: 700;
          color: #3a84ff;
        }
      }

      .hidden-bottom {
        /* stylelint-disable-next-line declaration-no-important */
        border-bottom: none !important;
      }

      .view-target {
        max-height: 232px;
        overflow-y: auto;
        border-top: none;

        div {
          width: calc(100% - 32px);
          margin: 8px 16px;
        }
      }
    }
  }
</style>
