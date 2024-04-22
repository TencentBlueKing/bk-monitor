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
  <section class="business-panel">
    <div class="title">
      <span class="title-name">{{ title || 'Title' }}</span>
      <span
        class="title-icon"
        :class="`title-icon-${icon}`"
      >
        <span :class="['icon-monitor', `${iconClass}`]" />
        <!-- <svg-icon class="svg-icon" :icon-name="iconClass"></svg-icon> -->
      </span>
    </div>
    <slot />
    <div
      v-if="log"
      class="footer"
    >
      <h4 class="footer-title">
        {{ $t('操作日志') }}
      </h4>
      <div class="footer-message">
        {{ log }}
      </div>
    </div>
  </section>
</template>

<script>
// import SvgIcon from '../../../../components/svg-icon/svg-icon';

export default {
  name: 'BusinessAlarmPanel',
  props: {
    title: {
      type: String,
      default: '',
    },
    icon: {
      type: String,
      default: 'normal',
    },
    log: {
      type: String,
      default: '',
    },
  },
  computed: {
    iconClass() {
      if (this.icon === 'serious' || this.icon === 'slight') {
        return 'icon-mc-chart-alert';
      }
      if (this.icon === 'unset') {
        return 'icon-tixing';
      }
      return '';
    },
  },
};
</script>

<style scoped lang="scss">
@import '../../common/mixins';

.business-panel {
  margin: 35px 0 0 40px;
  background: #fafbfd;
  position: relative;
  .title {
    font-size: 0;
    overflow: hidden;
    padding-bottom: 13px;
    &-name {
      display: inline-block;
      height: 26px;
      font-size: 20px;
      color: #313238;
      line-height: 26px;
    }
    &-icon {
      margin-left: 6px;
      font-size: 16px;
      position: relative;
      top: -1.5px;
      .icon-mc-chart-alert {
        font-size: 12px;
      }
    }
    .svg-icon {
      width: 24px;
      height: 24px;
    }
    &-icon-serious {
      color: $seriousIconColor;
    }
    &-icon-slight {
      color: $slightIconColor;
    }
    &-icon-unset {
      color: $unsetIconColor;
    }
    &-icon-normal {
      color: $normalIconColor;
    }
  }
  .footer {
    margin-right: 40px;
    padding-top: 15px;
    border-top: 1px solid #ddd;
    color: $defaultFontColor;
    &-title {
      height: 23px;
      font-size: 14px;
      font-weight: bold;
      line-height: 23px;
      margin: 0 0 5px 0;
    }
    &-message {
      height: 23px;
      font-size: 12px;
      line-height: 23px;
    }
  }
}
</style>
