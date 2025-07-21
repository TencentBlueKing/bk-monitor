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
<!--
 * @Date: 2021-06-08 11:44:55
 * @LastEditTime: 2021-07-17 12:59:58
 * @Description:
-->
<template>
  <div>
    <bk-table :data="data">
      <bk-table-column
        :label="$t('时间')"
        prop="time"
        width="150"
      >
        <template #default="{ row }">
          {{ getFormatTime(row) }}
        </template>
      </bk-table-column>
      <bk-table-column
        :label="columnName"
        prop="content"
        :min-width="200"
      >
        <template #default="{ row }">
          <span
            class="log"
            @click="handleShowDetai(row)"
          >{{ row['event.content'] }}</span>
        </template>
      </bk-table-column>
    </bk-table>
    <!-- <div class="load-more" v-if="data.length > 0 && !isLast">
      <bk-button class="btn" text @click="handleLoadMore">{{$t('查看更多')}}</bk-button>
    </div> -->
    <bk-dialog
      v-model="showLogDetail"
      :show-footer="false"
      header-position="left"
      :width="700"
      :title="detailTitle"
    >
        <JsonViewer
          class="log-content"
          :preview-mode="true"
          :value="logDetail"
        />
    </bk-dialog>
  </div>
</template>
<script lang="ts">
import dayjs from 'dayjs';
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';
import JsonViewer from 'vue-json-viewer';

@Component({
  name: 'strategy-view-log',
  components: {
    JsonViewer,
  },
})
export default class StrategyViewLog extends Vue {
  @Prop({ default: () => [], type: Array }) private readonly data!: any[];
  @Prop({ default: false, type: Boolean }) private readonly isLast!: boolean;
  @Prop({ default: '', type: String }) private readonly metricMetaId!: string;

  private showLogDetail = false;
  private logDetail = '';
  get detailTitle() {
    switch (this.metricMetaId) {
      case 'bk_fta|alert':
      case 'bk_monitor|alert':
      case 'bk_fta|event':
        return this.$t('告警内容');
      default:
      case 'bk_log_search|log':
        return this.$t('日志详情');
    }
  }
  get columnName() {
    switch (this.metricMetaId) {
      case 'bk_fta|alert':
      case 'bk_monitor|alert':
      case 'bk_fta|event':
        return this.$t('告警内容');
      default:
      case 'bk_log_search|log':
        return this.$t('日志');
    }
  }
  handleShowDetai(row) {
    const content = row.content || row['event.content'];
    try {
      this.logDetail = JSON.parse(content);
    } catch {
      this.logDetail = content;
    }
    this.showLogDetail = true;
  }

  @Emit('load-more')
  handleLoadMore() {}

  getFormatTime({ time }) {
    if (typeof time === 'string') {
      return dayjs.tz(+time).format('YYYY-MM-DD HH:mm:ss');
    }
    if (typeof time === 'number') {
      if (time.toString().length === 10) {
        return dayjs.tz(time * 1000).format('YYYY-MM-DD HH:mm:ss');
      }
      return dayjs.tz(time).format('YYYY-MM-DD HH:mm:ss');
    }
    return time;
  }
}
</script>
<style lang="scss" scoped>
.log {
  cursor: pointer;

  &:hover {
    color: #3a84ff;
  }

  &-content {
    height: 380px;
    padding: 15px 20px;
    overflow: auto;
    word-break: break-all;
    background: #f5f6fa;
    border-radius: 2px;

    &.jv-light {
      background: #f5f6fa;
    }

    :deep(.jv-code) {
      padding: 0;
    }
  }
}

.load-more {
  display: flex;
  justify-content: center;
  height: 24px;
  margin-top: -1px;
  background: #fafbfd;
  border: 1px solid #dcdee5;

  .btn {
    font-size: 12px;
  }
}
</style>
