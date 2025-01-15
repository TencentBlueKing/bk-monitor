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
  <article class="export-import">
    <section class="export-import-panel">
      <div
        v-for="(item, index) in panel"
        :key="index"
        class="panel"
      >
        <span class="panel-icon"
          ><i
            class="icon-monitor"
            :class="item.icon"
        /></span>
        <span class="panel-title">{{ item.title }}</span>
        <button
          v-authority="{
            active: item.type === 'import' ? !authority.MANAGE_IMPORT_CONFIG : !authority.MANAGE_EXPORT_CONFIG,
          }"
          class="panel-button"
          @click="handleClick(item.type)"
        >
          {{ item.btnText }}
        </button>
      </div>
    </section>
    <section class="export-import-history">
      <div class="history">
        <span> {{ $t('需要查看历史导入任务详情') }} </span>
        <span
          v-authority="{ active: !authority.MANAGE_IMPORT_CONFIG }"
          class="history-btn"
          @click="handleGoConfigHistory"
        >
          {{ $t('导入历史') }}
        </span>
      </div>
    </section>
  </article>
</template>

<script>
import aurhorityMixinCreate from '../../mixins/authorityMixin';
import * as exportImportAuth from './authority-map';

export default {
  name: 'ExportImport',
  mixins: [aurhorityMixinCreate(exportImportAuth)],
  data() {
    return {
      panel: [
        {
          icon: 'icon-mc-import',
          title: this.$t('可以批量导入插件,采集配置,策略配置等. 建议:导入的监控目标相同.'),
          btnText: this.$t('导入'),
          type: 'import',
        },
        {
          icon: 'icon-mc-export icon-export',
          title: this.$t('可以批量导出采集配置,策略配置和相应的依赖. 注意:不包括监控目标.'),
          btnText: this.$t('点击导出'),
          type: 'export',
        },
      ],
    };
  },
  methods: {
    handleClick(type) {
      switch (type) {
        case 'export':
          this.authority.MANAGE_EXPORT_CONFIG
            ? this.handleExport()
            : this.handleShowAuthorityDetail(exportImportAuth.MANAGE_EXPORT_CONFIG);
          break;
        case 'import':
          this.authority.MANAGE_IMPORT_CONFIG
            ? this.handleImport()
            : this.handleShowAuthorityDetail(exportImportAuth.MANAGE_IMPORT_CONFIG);
          break;
      }
    },
    handleExport() {
      this.$router.push({ name: 'export-configuration' });
    },
    handleImport() {
      this.$router.push({ name: 'import-configuration-upload' });
    },
    handleGoConfigHistory() {
      this.authority.MANAGE_IMPORT_CONFIG
        ? this.$router.push({ name: 'import-configuration-history' })
        : this.handleShowAuthorityDetail(exportImportAuth.MANAGE_IMPORT_CONFIG);
    },
  },
};
</script>

<style lang="scss" scoped>
@import '../../theme/index';

$whiteColor: #fff;
$panelBorderColor: #f0f1f5;
$importIconColor: #a3c5fd;
$exportIconColor: #ffd695;

@mixin layout-flex($flexDirection, $alignItems, $justifyContent) {
  display: flex;
  flex-direction: $flexDirection;
  align-items: $alignItems;
  justify-content: $justifyContent;
}

@mixin layout-export-import {
  border-radius: 2px;
  min-height: 270px;
  width: 301px;
  margin-top: 132px;
  padding: 51px 48px 40px 48px;
  background: $whiteColor;

  @include layout-flex(column, center, flex-start);
  @include border-1px($panelBorderColor);
}

@mixin export-import-font($fontSize, $fontColor) {
  font-size: $fontSize;
  color: $fontColor;
}

.export-import {
  @include layout-flex(column, center, flex-start);

  &-panel {
    @include layout-flex(row, stretch, center);

    .panel {
      @include layout-export-import();

      &:not(:first-child) {
        margin-left: 20px;
      }

      &-icon {
        width: 52px;
        height: 52px;
        line-height: 1;

        @include export-import-font(52px, $importIconColor);

        .icon-monitor {
          font-size: inherit;
        }
      }

      &-title {
        margin-top: 17px;
        text-align: center;

        @include export-import-font(12px, $defaultFontColor);
      }

      .icon-export {
        color: $exportIconColor;
      }
    }

    button {
      background: $whiteColor;
      border-radius: 18px;
      margin-top: 34px;
      width: 160px;
      height: 36px;

      @include border-1px($defaultBorderColor);
      @include export-import-font(14px, $defaultFontColor);

      &:hover {
        box-shadow: 0px 2px 6px 0px rgba(58, 132, 255, 0.1);
        border: 1px solid $primaryFontColor;
        color: $primaryFontColor;
      }
    }
  }

  &-history {
    margin-top: 27px;

    @include export-import-font(12px, $unsetIconColor);

    .history-btn {
      cursor: pointer;

      @include export-import-font(12px, $primaryFontColor);
    }
  }
}
</style>
