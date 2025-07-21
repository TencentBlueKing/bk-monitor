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
  <div class="empty-status-container">
    <bk-exception
      :scene="scene"
      :type="emptyType"
    >
      <div class="empty-text-content">
        <p
          v-if="showText"
          class="empty-text"
        >
          {{ typeText }}
        </p>
        <template v-if="$slots.default">
          <p class="empty-text">
            <slot />
          </p>
        </template>
        <template v-else>
          <i18n
            v-if="emptyType === 'search-empty'"
            class="operation-text"
            path="可以尝试{0}或{1}"
          >
            <span style="margin: 0 3px">{{ $t('调整关键词') }}</span>
            <div
              style="margin-left: 3px"
              class="operation-btn"
              @click="handleOperation('clear-filter')"
            >
              {{ $t('清空筛选条件') }}
            </div>
          </i18n>
          <span
            v-if="emptyType === '500'"
            class="operation-btn"
            @click="handleOperation('refresh')"
          >
            {{ $t('刷新') }}
          </span>
        </template>
      </div>
    </bk-exception>
  </div>
</template>

<script>
export default {
  props: {
    emptyType: {
      type: String,
      default: 'empty',
    },
    scene: {
      type: String,
      default: 'part',
    },
    showOperation: {
      type: Boolean,
      default: true,
    },
    showText: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      defaultTextMap: {
        empty: this.$t('暂无数据'),
        'search-empty': this.$t('搜索结果为空'),
        500: this.$t('数据获取异常'),
        403: this.$t('无业务权限'),
      },
    };
  },
  computed: {
    typeText() {
      return this.defaultTextMap[this.emptyType];
    },
  },
  methods: {
    handleOperation(type) {
      this.$emit('operation', type);
    },
  },
};
</script>

<style lang="scss">
  .empty-status-container {
    padding: 20px 0;

    .exception-image {
      height: 180px;
      user-select: none;

      /* stylelint-disable-next-line property-no-unknown */
      onselectstart: none;
    }

    .empty-text-content {
      margin-top: 20px;
    }

    .empty-text {
      margin: 8px 0;
      font-size: 14px;
      line-height: 22px;
      color: #63656e;
    }

    .operation-text {
      font-size: 12px;
      line-height: 20px;
      color: #63656e;
    }

    .operation-btn {
      color: #3a84ff;
      cursor: pointer;
    }
  }
</style>
