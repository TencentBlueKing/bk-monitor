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
  <div class="log-retrieval">
    <iframe
      ref="iframe"
      class="log-retrieval-frame"
      :src="retrievalUrl"
      allow="fullscreen"
    />
  </div>
</template>
<script lang="ts">
import { Component, Ref, Vue } from 'vue-property-decorator';

import bus from 'monitor-common/utils/event-bus';

@Component({
  name: 'log-retrieval',
})
export default class LogRetrieval extends Vue {
  @Ref('iframe') private iframeRef: HTMLIFrameElement;

  get retrievalUrl() {
    // if (process.env.NODE_ENV === 'development') {
    //   return `${this.$store.getters.bkLogSearchUrl}#/retrieve/?from=monitor&bizId=${this.$store.getters.bizId}&lang=zh`;
    // }
    let { bkLogSearchUrl } = this.$store.getters;
    if (window.location.protocol === 'https:' && this.$store.getters.bkLogSearchUrl.match(/^http:/)) {
      bkLogSearchUrl = this.$store.getters.bkLogSearchUrl.replace('http:', 'https:');
    }
    return `${bkLogSearchUrl}#/retrieve/?from=monitor&bizId=${this.$store.getters.bizId}`;
  }

  handleLoad() {
    this.$nextTick(() => {
      const iframeContent = this.iframeRef?.contentWindow;
      iframeContent?.document.body.addEventListener('keydown', this.handleKeydownGlobalSearch);
    });
  }
  handleKeydownGlobalSearch(event) {
    event.stopPropagation();
    bus.$emit('handle-keyup-search', event);
  }

  beforeDestroy() {
    const iframeContent = this.iframeRef?.contentWindow;
    iframeContent?.document.body.removeEventListener('keydown', this.handleKeydownGlobalSearch);
  }
}
</script>
<style lang="scss" scoped>
.log-retrieval {
  // margin: -20px -24px 0;
  &-frame {
    width: 100%;
    min-width: 100%;
    min-height: calc(100vh - 55px);
    border: 0;
  }
}
</style>
