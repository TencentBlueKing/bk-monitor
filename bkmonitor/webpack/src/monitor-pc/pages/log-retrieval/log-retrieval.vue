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
  private initRouteString = '';
  private initBizId = -1;
  private indexId: number | string = '';

  getUrlParamsString() {
    const { from, spaceUid, bizId, indexId, ...otherQuery } = this.$route.query;
    this.indexId = indexId;
    const queryVal = Object.entries(otherQuery).reduce(
      (acc, [key, val]) => {
        if (val) acc[key] = val;
        return acc;
      },
      {
        bizId: this.$store.getters.bizId,
      }
    );
    const str = Object.entries({
      ...(queryVal || {}),
      ...Object.fromEntries(new URLSearchParams(location.search)),
    })
      .map(entry => entry.join('='))
      .join('&');
    if (str.length) return `&${str}`;
    return '';
  }

  get retrievalUrl() {
    // if (process.env.NODE_ENV === 'development') {
    //   return `${this.$store.getters.bkLogSearchUrl}#/retrieve/?from=monitor&bizId=${this.$store.getters.bizId}&lang=zh`;
    // }
    let { bkLogSearchUrl } = this.$store.getters;
    if (window.location.protocol === 'https:' && this.$store.getters.bkLogSearchUrl.match(/^http:/)) {
      bkLogSearchUrl = this.$store.getters.bkLogSearchUrl.replace('http:', 'https:');
    }
    return `${bkLogSearchUrl}#/retrieve/${this.indexId || ''}?from=monitor${this.initRouteString}`;
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
  receiveMessage(event) {
    // 检查消息来源是否可信
    const data = event.data;
    // if (data._MONITOR_URL_ !== location.origin) return;
    // 获取来自iframe的内容
    if ('_LOG_TO_MONITOR_' in data) {
      // 测试代码，验证成功后就删除
      console.log(event.data, event.origin, location.origin);
      this.$router
        .replace({
          query: { ...data._MONITOR_URL_PARAMS_, ...data._MONITOR_URL_QUERY_ },
        })
        .catch(err => err);
    }
  }

  mounted() {
    this.initBizId = this.$store.getters.bizId;
    this.initRouteString = this.getUrlParamsString();
    window.addEventListener('message', this.receiveMessage, false);
  }

  beforeDestroy() {
    if (this.$store.getters.bizId !== this.initBizId) {
      this.$router.replace({
        query: {
          bizId: this.$store.getters.bizId,
        },
      });
    }
    const iframeContent = this.iframeRef?.contentWindow;
    iframeContent?.document.body.removeEventListener('keydown', this.handleKeydownGlobalSearch);
    window.removeEventListener('message', this.receiveMessage, false);
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
