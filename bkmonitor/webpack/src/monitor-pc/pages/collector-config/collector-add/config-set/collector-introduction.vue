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
  <div class="collector-introduction">
    <div class="introduction-header">
      <div class="header-title">
        <div
          v-if="introduction.type === 'method'"
          class="title-method"
        >
          {{ $t('采集方式介绍') }}
        </div>
        <div
          v-else
          class="title-plugin"
        >
          {{ $t('关于{0}的描述', [introduction.pluginId]) }}
        </div>
      </div>
    </div>
    <div
      :style="{ 'padding-left': introduction.type === 'bkmonitor.models.fta.plugin' ? '24px' : '' }"
      class="introduction-content"
    >
      <div
        v-if="introduction.type === 'bkmonitor.models.fta.plugin'"
        class="content-desc"
      >
        <div
          v-if="introduction.isOfficial"
          class="desc-tag tag-success"
        >
          <i class="icon-monitor icon-mc-check-fill tag-icon" />
          <span class="tag-text"> {{ $t('官方') }} </span>
        </div>
        <div class="desc-tag tag-warning">
          <i
            class="icon-monitor tag-icon"
            :class="[introduction.isSafety ? 'icon-mc-verified-fill' : 'icon-mc-uncertified-fill']"
          />
          <span
            v-if="introduction.isSafety"
            class="tag-text"
          >
            {{ $t('已认证') }}
          </span>
          <span
            v-else
            class="tag-text"
          >
            {{ $t('非认证') }}
          </span>
        </div>
        <div
          v-for="item in introduction.osTypeList"
          class="desc-tag"
          :key="item"
        >
          <i :class="['icon-monitor tag-icon', `icon-${item}`]" />
          <span class="tag-text">{{ item }}</span>
        </div>
        <div
          v-if="introduction.createUser"
          class="desc-tag"
        >
          <i class="icon-monitor icon-user tag-icon" />
          <span class="tag-text">
            {{ $t('创建人:') }} <bk-user-display-name :user-id="introduction.createUser" />
          </span>
        </div>
        <div
          v-if="introduction.updateUser"
          class="desc-tag"
        >
          <i class="icon-monitor icon-bianji tag-icon" />
          <span class="tag-text">
            {{ $t('最近更新人') }} <bk-user-display-name :user-id="introduction.updateUser"
          /></span>
        </div>
      </div>
      <viewer
        class="content-viewer"
        :value="introduction.content"
      />
    </div>
  </div>
</template>

<script>
import Viewer from 'monitor-ui/markdown-editor/viewer.tsx';

export default {
  name: 'CollectorIntroduction',
  components: {
    Viewer,
  },
  props: {
    introduction: {
      type: Object,
      default: () => ({
        type: 'method',
        content: '',
      }),
    },
  },
};
</script>

<style lang="scss" scoped>
.collector-introduction {
  // width: 400px;
  height: 100vh;
  background: #fafbfd;

  .introduction-header {
    height: 42px;
    background: #f0f1f5;
    border-bottom: 1px solid #dcdee5;
    border-radius: 0px 0px 1px 1px;

    .header-title {
      height: 42px;
      font-size: 14px;
      line-height: 42px;

      .title-method {
        margin-left: 24px;
        font-weight: bold;
        color: #313238;
      }

      .title-plugin {
        margin-left: 24px;
        color: #63656e;
      }
    }
  }

  .introduction-content {
    max-height: calc(100vh - 122px);
    padding: 0 36px 15px 24px;
    overflow: auto;

    .content-desc {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      margin-top: 20px;

      .desc-tag {
        display: inline-flex;
        align-items: center;
        height: 20px;
        margin-right: 6px;
        margin-bottom: 5px;
        line-height: 18px;
        color: #63656e;
        background: #fff;
        border: 1px solid #979ba5;
        border-radius: 2px;

        .tag-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          font-size: 14px;
          color: #fff;
          background: #979ba5;

          &.icon-bianji {
            font-size: 20px;
          }
        }

        .tag-text {
          padding: 0 9px;
        }

        &.tag-success {
          border-color: #2dcb56;

          .tag-icon {
            background: #2dcb56;
          }

          .tag-text {
            color: #2dcb56;
          }
        }

        &.tag-warning {
          border-color: #979ba5;

          .tag-icon {
            background: #979ba5;
          }
        }
      }
    }

    .content-viewer {
      :deep(.toastui-editor-contents),
      :deep(.tui-editor-contents) {
        /* stylelint-disable-next-line no-descending-specificity */
        pre {
          background: #f0f1f5;
        }
      }
    }
  }
}
</style>
