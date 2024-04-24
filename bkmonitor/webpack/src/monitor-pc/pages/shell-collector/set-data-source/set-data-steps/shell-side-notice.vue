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
  <div class="shell-side-notice">
    <div class="notice-title">
      {{ $t('上报格式说明') }}
    </div>
    <div class="notice-content">
      <div class="notice-content-desc">
        <i18n path="数据格式需遵循{0},如下">
          <span @click="handleGotoPage">{{ $t('Prometheus Metrics 标准格式') }}</span>
        </i18n>
      </div>
      <div class="notice-content-code">metric_name{label_name="lable_value"} metric_value timestamp</div>
    </div>
    <div class="notice-table">
      <table>
        <thead>
          <tr>
            <th style="width: 110px">metric_name</th>
            <th style="width: 200px">
              {{ $t('指标名称') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>label_name</td>
            <td>
              {{ $t('维度名称') }}
            </td>
          </tr>
          <tr>
            <td>label_value</td>
            <td>
              {{ $t('维度值, 字符串 ; 可选') }}
            </td>
          </tr>
          <tr>
            <td>metric_value</td>
            <td>{{ $t('指标值,数值 ； ') }}</td>
          </tr>
          <tr>
            <td>timestamp</td>
            <td>{{ $t('时间戳(ms)；可选') }}</td>
          </tr>
          <tr>
            <td>
              {{ $t('一个指标一行') }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="notice-title">
      {{ $t('如标准输出') }}
    </div>
    <div class="notice-content">
      <div class="notice-content-code echo">
        <div>disk_usage 0.75</div>
        <div>http_request_total{method="POST", route="/user"} 94334</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ShellSideNotice',
  methods: {
    handleGotoPage() {
      window.open(
        'https://github.com/prometheus/docs/blob/master/content/docs/instrumenting/exposition_formats.md',
        '_black'
      );
    },
  },
};
</script>

<style scoped lang="scss">
.shell-side-notice {
  padding: 2px 10px 20px;
  background: #3b3c42;
  width: 333px;
  font-size: 12px;

  .notice-title {
    margin-top: 25px;
    height: 16px;
    font-size: 12px;
    font-weight: bold;
    color: rgba(255, 255, 255, 1);
    line-height: 16px;
  }

  .notice-content {
    &-desc {
      margin: 10px 0;
      height: 16px;
      font-size: 12px;
      color: rgba(196, 198, 204, 1);
      line-height: 16px;

      span {
        color: #3b73d1;

        &:hover {
          cursor: pointer;
        }
      }
    }

    &-code {
      width: 313px;
      background: #313238;
      padding: 10px;
      color: #ffb848;
      word-break: break-word;

      &.echo {
        padding: 10px 0;
      }
    }
  }

  .notice-table {
    margin: 10px 0;

    table {
      background: #313238;

      tr {
        height: 27px;
        border-bottom: 0.5px solid #3b3c42;

        td,
        th {
          padding-left: 10px;
          color: #c4c6cc;
          text-align: left;
        }
      }
    }
  }
}
</style>
