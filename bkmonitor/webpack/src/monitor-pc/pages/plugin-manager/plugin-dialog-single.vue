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
    v-model="dialog.show"
    :show-footer="false"
    :mask-close="false"
    ext-cls="plugin-manager-dialog"
    header-position="left"
    width="480"
    @after-leave="handleHideDialog"
  >
    <template slot="header">
      <div class="dialog-title">
        {{ dialog.title }}
      </div>
    </template>
    <div class="dilog-container">
      <div class="dialog-content">
        <span class="icon-monitor icon-CPU dialog-content-icon" />
        <div class="dialog-content-desc">
          <div class="desc-name">
            <span
              v-bk-overflow-tips
              class="desc-name-set"
              >{{ dialog.name }}</span
            ><span
              v-if="dialog.status > 1"
              class="desc-name-size"
              >{{ dialog.size }}</span
            >
          </div>
          <bk-progress
            v-if="dialog.status === 1"
            class="desc-process"
            :percent="dialog.percent"
            :show-text="false"
            size="small"
            :color="dialog.status === 2 ? '#EA3636' : '#3A84FF'"
          />
        </div>
      </div>
      <div
        v-if="dialog.percent === 1"
        class="dialog-loading"
      >
        <span
          class="icon-monitor loading-icon"
          :style="{
            'animation-iteration-count': dialog.status === 1 ? 'infinite' : 0,
            color: dialog.status === 2 || dialog.status === 4 ? '#EA3636' : '#3A84FF',
          }"
          :class="[[2, 4, 5].includes(dialog.status) ? 'icon-tixing' : 'icon-loading']"
        />
        <span
          v-if="dialog.status === 1"
          class="loading-text"
        >
          {{ $t('上传中...') }}
        </span>
        <span
          v-else-if="dialog.status === 2"
          class="loading-text"
          >{{ dialog.status === 2 ? $t('上传失败，请重试') : $t('上传完成') }}</span
        >
        <div v-else-if="dialog.status === 4">
          <span style="color: #ea3636">
            {{ $t('注意: 插件ID冲突') }}
            {{ dialog.data.conflict_title ? ',' + dialog.data.conflict_title : '' }}：</span
          >
          {{ dialog.data.conflict_detail }}
        </div>
        <div v-else-if="dialog.status === 5">
          {{ dialog.data.conflict_detail }}
        </div>
      </div>
      <div
        v-if="dialog.data.conflict_detail"
        class="dialog-footer"
      >
        <!-- 非官方插件更新操作 -->
        <bk-button
          v-if="!dialog.data.is_official && dialog.data.is_safety && canIUpdatePlubin"
          class="dialog-footer-btn"
          theme="primary"
          @click="handleToEdit"
        >
          {{ $t('更新插件') }}
        </bk-button>
        <bk-button
          class="dialog-footer-btn"
          theme="success"
          @click="handleCreateNewPlugin"
        >
          {{ $t('创建插件') }}
        </bk-button>
        <bk-button
          v-if="dialog.update && dialog.data.is_official && isSuperUser"
          :loading="dialog.loading"
          class="dialog-footer-btn"
          theme="primary"
          @click="handleUpdatePlugin"
        >
          {{ $t('更新至现有插件') }}
        </bk-button>
        <bk-button
          class="dialog-footer-btn"
          @click="handleHideDialog"
        >
          {{ $t('取消') }}
        </bk-button>
      </div>
    </div>
  </bk-dialog>
</template>

<script>
export default {
  name: 'PluginDialogSingle',
  props: {
    dialog: {
      type: Object,
      default: () => ({}),
    },
  },
  computed: {
    isSuperUser() {
      return this.$store.getters.isSuperUser;
    },
    canIUpdatePlubin() {
      // conflict_title:
      // 1.导入版本不大于当前版本
      // 2.插件类型冲突
      // 3.远程采集配置项冲突
      // 4.插件已关联%s个采集配置
      // 5.导入插件与当前插件内容完全一致
      const arr = this.dialog.data.conflict_ids;
      // 2 3 5 为不需强制更新插件
      const flag = [2, 3, 5].some(item => arr.toString().indexOf(`${item}`) > -1);
      return !flag;
    },
  },
  methods: {
    handleCreateNewPlugin() {
      const { data } = this.dialog;
      if (data.is_official && this.duplicate_type) {
        this.$parent.handleSetUpdatePlugin();
      } else {
        this.handleHideDialog();
        this.$parent.handlePluginAdd(null, data);
      }
    },
    handleUpdatePlugin() {
      const { data } = this.dialog;
      if (data.is_official && this.dialog.update) {
        this.$parent.handleSetUpdatePlugin();
      } else {
        this.handleHideDialog();
        this.$parent.handlePluginEdit(data.plugin_id);
      }
    },
    handleHideDialog() {
      this.$parent.handleHideDialog();
    },
    handleToEdit() {
      // 非官方, 具有完整签名去更新插件
      const { data } = this.dialog;
      this.handleHideDialog();
      this.$router.push({
        name: 'plugin-update',
        params: {
          pluginData: data,
        },
      });
    },
  },
};
</script>

<style lang="scss" scoped>
.plugin-manager-dialog {
  .dialog-title {
    font-size: 24px;
    color: #313238;
    line-height: 32px;
  }

  .dilog-container {
    color: #63656e;
    font-size: 12px;
    margin-top: -10px;

    .dialog-content {
      display: flex;
      flex-direction: row;
      align-items: center;
      border: 1px dashed #c4c6cc;
      border-radius: 2px;
      height: 42px;
      padding: 0 12px;
      background: #f5f7fa;

      &-icon {
        color: #3a84ff;
        font-size: 20px;
      }

      &-desc {
        flex: 1;
        margin-left: 9px;

        .desc-name {
          display: flex;
          align-items: center;

          &-size {
            margin-left: auto;
          }

          &-set {
            max-width: 336px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        }
      }
    }

    .dialog-loading {
      margin-top: 4px;
      display: flex;

      @keyframes done-loading {
        0% {
          transform: rotate(0deg);
        }

        100% {
          transform: rotate(-360deg);
        }
      }

      .loading-icon {
        color: #3a84ff;
        display: flex;
        margin-right: 4px;
        margin-top: 3px;
        align-items: center;
        justify-content: center;
        height: 12px;
        transform-origin: center;
        animation: done-loading 1s linear 0s infinite;
      }
    }

    .dialog-footer {
      margin-top: 24px;
      display: flex;
      justify-content: flex-end;

      &-btn {
        margin-left: 10px;
      }
    }
  }
}
</style>
