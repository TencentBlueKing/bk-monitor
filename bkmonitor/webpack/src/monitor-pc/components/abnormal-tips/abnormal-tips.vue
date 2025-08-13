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
  <div class="abnormal-tips-wrap">
    <bk-popover v-bind="$attrs">
      <slot />
      <div
        slot="content"
        :class="['content-wrap', { 'content-en': lang === 'en' }]"
      >
        <span class="text">{{ $attrs['tips-text'] }}</span>
        <span
          v-if="$attrs['link-url'] && $attrs['link-text']"
          class="link"
          @click="handleOpenLink($attrs['link-url'])"
          >{{ $attrs['link-text'] }}<span class="icon-monitor icon-mc-link"
        /></span>
        <span
          v-if="$attrs['doc-link']"
          class="link"
          @click="handleGotoLink($attrs['doc-link'])"
        >
          {{ $t('查看文档') }}
          <span class="icon-monitor icon-mc-link" />
        </span>
      </div>
    </bk-popover>
  </div>
</template>
<script lang="ts">
import { Component, Mixins, Prop } from 'vue-property-decorator';

import { LANGUAGE_COOKIE_KEY } from 'monitor-common/utils/constant';
import { docCookies } from 'monitor-common/utils/utils';

import documentLinkMixin from '../../mixins/documentLinkMixin';

// zh-cn
@Component({
  name: 'abnormal-tips',
})
export default class AbnormalTips extends Mixins(documentLinkMixin) {
  @Prop({ type: Boolean, default: false }) readonly isTpl;
  public handleOpenLink(url: string) {
    window.open(url, '_blank');
  }

  private get lang() {
    const lan = docCookies.getItem(LANGUAGE_COOKIE_KEY);
    return lan === 'en' ? 'en' : 'cn';
  }
}
</script>
<style lang="scss">
.abnormal-tips-wrap {
  .content-wrap {
    width: 195px;
    font-size: 0;

    span {
      font-size: 12px;
      line-height: 20px;
    }

    .link {
      color: #3a84ff;
      white-space: nowrap;
      cursor: pointer;

      .icon-mc-link {
        margin-left: 4px;
      }
    }
  }

  .content-en {
    width: 300px;
  }
}
</style>
