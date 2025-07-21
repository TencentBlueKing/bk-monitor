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
  <div class="intro-panel">
    <div :class="`right-window ${isOpenWindow ? 'window-active' : ''}`">
      <div
        class="create-btn details"
        @click="handleActiveDetails(null)"
      >
        <span
          :style="`color:${isOpenWindow ? '#3A84FF;' : ''}`"
          class="bk-icon icon-text-file"
        ></span>
      </div>
      <div class="top-title">
        <p>{{ $t('帮助文档') }}</p>
        <div
          class="create-btn close"
          @click="handleActiveDetails(false)"
        >
          <span class="bk-icon icon-minus-line"></span>
        </div>
      </div>
      <div class="html-container">
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div v-html="customTypeIntro"></div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex';
import $http from '../../../../../api';
export default {
  props: {
    data: {
      type: Object,
      required: true,
    },
    isOpenWindow: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      proxyHost: [],
    };
  },
  computed: {
    ...mapGetters({
      globalsData: 'globals/globalsData',
    }),
    dataTypeList() {
      const { databus_custom: databusCustom } = this.globalsData;
      return databusCustom || [];
    },
    customTypeIntro() {
      const curType = this.dataTypeList.find(type => type.id === this.data.custom_type);
      return curType ? this.replaceVaribles(curType.introduction) : '';
    },
  },
  mounted() {
    this.initTargetFieldSelectList();
  },
  methods: {
    replaceVaribles(intro) {
      let str = this.updateStringWithNewData(intro);
      const varibleList = intro.match(/\{\{([^)]*)\}\}/g);
      varibleList?.forEach(item => {
        const val = item.match(/\{\{([^)]*)\}\}/)[1];
        str = this.data[val] ? str.replace(item, this.data[val]) : str;
      });

      return str;
    },
    handleActiveDetails(state) {
      this.$emit('handle-active-details', state ? state : !this.isOpenWindow);
      this.$store.commit('updateChartSize');
    },
    async initTargetFieldSelectList() {
      const res = await $http.request('retrieve/getProxyHost', {
        query: {
          space_uid: this.$route.query.spaceUid,
        },
      });
      this.proxyHost = res.data;
    },
    updateStringWithNewData(originalString) {
      const regex = /<code>[\s\S]*?云区域ID[\s\S]*?<\/code>/;

      // 格式化新的数据以便插入到 <code> 标签中
      const newDataContent = this.proxyHost
        .map(dataGroup =>
          dataGroup.urls
            .map(data => `云区域ID ${dataGroup.bk_cloud_id} ${data.protocol}: ${data.report_url}`)
            .join('\n')
        )
        .join('\n');
      console.log(newDataContent);

      const updatedString = originalString.replace(regex, `<code>${newDataContent}</code>`);
      return updatedString;
    },
  },
};
</script>

<style lang="scss">
  @import '@/scss/mixins/flex';
  @import '@/scss/mixins/scroller';

  .intro-panel {
    position: relative;
    width: 100%;
    height: 100%;

    .right-window {
      position: absolute;
      z-index: 99;
      width: 100%;
      height: 100%;
      padding: 16px 0 0 24px;
      color: #63656e;
      background: #fff;
      border: 1px solid #dcdee5;

      .html-container {
        max-height: calc(100vh - 200px);
        padding-right: 24px;
        overflow-y: auto;
      }

      .top-title {
        height: 48px;
      }

      &.window-active {
        right: 0;
      }

      h1 {
        margin: 26px 0 10px;
        font-size: 12px;
        font-weight: 700;

        &:first-child {
          margin-top: 0;
        }
      }

      ul {
        margin-left: 10px;

        li {
          margin-top: 8px;
          font-size: 12px;
          list-style: inside;
        }
      }

      p {
        font-size: 12px;
      }

      pre {
        padding: 10px 14px;
        margin: 0;
        margin-top: 6px;
        overflow-x: auto;
        background: #f4f4f7;

        @include scroller;
      }

      a {
        display: inline-block;
        margin: 10px 0;
        color: #3a84ff;
      }
    }

    .create-btn {
      position: absolute;
      z-index: 999;
      width: 24px;
      height: 24px;

      @include flex-center;

      &.details {
        position: fixed;
        top: 64px;
        right: 16px;
        transform: rotateZ(360deg) rotateX(180deg);

        @include flex-center;
      }

      &.close {
        top: 10px;
        right: 16px;
      }

      &:hover {
        color: #3a84ff;
        cursor: pointer;
        background: #f0f1f5;
        border-radius: 2px;
      }
    }
  }
</style>
