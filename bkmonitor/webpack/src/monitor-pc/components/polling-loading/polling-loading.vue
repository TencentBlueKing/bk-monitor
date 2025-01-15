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
    v-model="show"
    :theme="'primary'"
    :close-icon="false"
    header-position="left"
    :show-footer="false"
  >
    <div class="register-dialog">
      <div
        v-if="!status.failMsg"
        class="loading"
      >
        <svg-loading-icon />
      </div>
      <div
        v-else
        class="fail"
      >
        <span class="bk-icon icon-exclamation-circle-shape" />
      </div>
      <div>
        <div class="register-msg">
          {{ status.msg }}
        </div>
        <div
          v-if="!status.failMsg"
          class="wait"
        >
          {{ $t('等待中') }}
        </div>
        <div
          v-else
          class="fail-msg"
        >
          {{ $t('原因:') }} {{ status.failMsg }}
        </div>
        <div
          v-show="status.failMsg"
          class="close-dialog"
        >
          <bk-button
            :text="true"
            @click="close"
          >
            {{ $t('关闭窗口') }}
          </bk-button>
        </div>
      </div>
    </div>
  </bk-dialog>
</template>
<script>
import SvgLoadingIcon from '../svg-loading-icon/svg-loading-icon';

export default {
  components: {
    SvgLoadingIcon,
  },
  props: {
    status: {
      type: Object,
    },
    show: {
      type: Boolean,
    },
  },
  methods: {
    close() {
      this.$emit('update:show', false);
    },
  },
};
</script>
<style lang="scss" scoped>
.register-dialog {
  .loading {
    text-align: center;
  }

  .fail {
    margin-bottom: 16px;
    text-align: center;
  }

  .fail-msg {
    font-size: 12px;
    color: #444;
    text-align: center;
    overflow-wrap: break-word;
  }

  .close-dialog {
    margin-top: 12px;
    text-align: center;

    :deep(.bk-primary) {
      font-size: 12px;
    }
  }

  .icon-exclamation-circle-shape {
    font-size: 60px;
    color: #ff9c01;
  }

  .register-msg {
    margin-bottom: 10px;
    font-size: 20px;
    line-height: 1.3;
    color: #313238;
    text-align: center;
  }

  .wait {
    margin-bottom: 12px;
    font-size: 12px;
    color: #444;
    text-align: center;
  }
}
</style>
