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
    width="640"
    ext-cls="plugin-dialog-multiple"
    :mask-close="false"
    :show-footer="false"
    :value="show"
    header-position="left"
    @cancel="handleDialogClose"
  >
    <template slot="header">
      <div class="dialog-title">
        {{ $t('导入中') }}
      </div>
    </template>
    <div class="dilog-container">
      <div
        v-for="(item, index) in files"
        ref="content"
        :key="index"
        class="dialog-content"
      >
        <span class="icon-monitor icon-CPU dialog-content-icon" />
        <div class="dialog-content-desc">
          <div class="desc-name">
            <div
              v-bk-overflow-tips
              class="item-name"
            >
              {{ item.name }}
            </div>
            <div
              v-if="item.versonShow"
              class="item-verson"
            >
              （{{ $t('版本') }}{{ item.verson }}）
            </div>
            <div
              :style="{ color: statusMap[item.status] }"
              class="item-status"
              @mouseenter="handleMouseEnter($event, item.text)"
              @mouseleave="handleMouseLeave"
            >
              {{ item.status }}
            </div>
          </div>
          <bk-progress
            v-if="item.percentShow"
            class="desc-process"
            :percent="item.percent"
            :show-text="false"
            color="#3A84FF"
            size="small"
          />
        </div>
      </div>
      <div class="dialog-footer">
        <bk-button
          v-show="isSuccess"
          class="dialog-footer-btn"
          theme="primary"
          @click="handleDialogClose"
        >
          {{ $t('button-完成') }}
        </bk-button>
      </div>
    </div>
    <div />
  </bk-dialog>
</template>

<script>
export default {
  name: 'PluginDialogMultiple',
  props: {
    show: Boolean,
    files: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      statusMap: {
        [this.$t('成功')]: '#2DCB56',
        [this.$t('上传失败')]: '#EA3636',
        [this.$t('注意: 名字冲突')]: '#EA3636',
        [this.$t('注意: 插件冲突')]: '#EA3636',
        [this.$t('非官方插件')]: '#EA3636',
        [this.$t('插件包不完整')]: '#EA3636',
        [this.$t('上传中...')]: '#3A84FF',
        [this.$t('解析中...')]: '#3A84FF',
        [this.$t('解析失败')]: '#EA3636',
      },
      popoverInstance: null,
    };
  },
  computed: {
    isSuccess() {
      return this.files.every(item => item.isOk);
    },
  },
  methods: {
    handleDialogClose() {
      this.$emit('update:show', false);
      this.$emit('refalsh-table-data');
    },
    handleMouseEnter(event, text) {
      if (text) {
        this.popoverInstance = this.$bkPopover(event.target, {
          content: text,
          arrow: true,
          maxWidth: 382,
          showOnInit: true,
          distance: 22,
          offset: -120,
        });
        this.popoverInstance.show(100);
      }
    },
    handleMouseLeave() {
      if (this.popoverInstance) {
        this.popoverInstance.hide(0);
        this.popoverInstance.destroy();
        this.popoverInstance = null;
      }
    },
  },
};
</script>

<style lang="scss">
.plugin-dialog-multiple {
  .bk-dialog-body {
    padding: 3px 26px 26px;
  }

  .dialog-title {
    font-size: 24px;
    line-height: 32px;
    color: #313238;
  }

  .dilog-container {
    margin-top: -10px;
    font-size: 12px;
    color: #63656e;

    .dialog-content {
      display: flex;
      align-items: center;
      height: 42px;
      padding: 0 12px;
      margin-bottom: 6px;
      background: #f5f7fa;
      border-radius: 2px;

      &-icon {
        font-size: 20px;
        color: #3a84ff;
      }

      &-desc {
        flex: 1;
        margin-left: 9px;

        .desc-name {
          display: flex;
          align-items: center;
          justify-content: space-between;

          &-size {
            margin-left: auto;
          }

          .item-name {
            flex-grow: 1;
            width: 226px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .item-verson {
            width: 66px;
            margin-right: 10px;
          }

          .item-status {
            width: 72px;
            text-align: right;
          }
        }
      }
    }

    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      margin-top: 24px;

      &-btn {
        margin-left: 10px;
      }
    }
  }
}
</style>
