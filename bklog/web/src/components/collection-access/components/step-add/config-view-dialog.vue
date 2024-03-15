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
  <bk-dialog
    width="600"
    theme="primary"
    header-position="left"
    :value="isShowDialog"
    :mask-close="false"
    :title="$t('label-预览').replace('label-', '')"
    :auto-close="false"
    :show-footer="false"
    @cancel="handelCancelDialog"
  >
    <div
      v-bkloading="{ isLoading: loading }"
      class="view-main"
    >
      <template v-if="viewList.length">
        <div
          v-for="(vItem, vIndex) in viewList"
          :key="vIndex"
          class="view-container"
        >
          <div
            :class="['view-title', !vItem.isShowTarget && 'hidden-bottom']"
            @click="handleClickTitle(vIndex, vItem.isShowTarget)"
          >
            <div
              v-bk-overflow-tips
              class="match title-overflow"
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
            v-show="vItem.isShowTarget"
            class="view-target"
          >
            <div
              v-for="(item, iIndex) in vItem.items"
              :key="iIndex"
              v-bk-overflow-tips
              class="title-overflow"
            >
              <span>{{ item }}</span>
            </div>
          </div>
        </div>
      </template>
      <empty-status
        v-else
        empty-type="empty"
        :show-text="false"
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
    EmptyStatus
  },
  props: {
    isShowDialog: {
      type: Boolean,
      default: false
    },
    viewQueryParams: {
      type: Object,
      require: true
    },
    isNode: {
      type: Boolean,
      require: true
    }
  },
  data() {
    return {
      isShowList: false,
      viewList: [],
      loading: false
    };
  },
  computed: {},
  watch: {
    isShowDialog(val) {
      if (val) {
        this.loading = true;
        this.$http
          .request('container/getLabelHitView', {
            data: this.viewQueryParams
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
    }
  },
  methods: {
    handelCancelDialog() {
      this.$emit('update:is-show-dialog', false);
    },
    handleClickTitle(index, showValue) {
      this.viewList[index].isShowTarget = !showValue;
    }
  }
};
</script>
<style lang="scss" scoped>
@import '@/scss/mixins/flex.scss';

.view-main {
  max-height: 600px;
  min-height: 200px;
  padding: 0 6px;
  margin-top: -14px;
  overflow-y: auto;
  font-size: 12px;

  .view-container {
    max-height: 264px;
    margin-bottom: 12px;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-sizing: border-box;

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
