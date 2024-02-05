/*
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
 */
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
// import { copyText } from '../../../../../monitor-common/utils/utils'
import dayjs from 'dayjs';

import { tailEventPluginData } from '../../../../../monitor-api/modules/event_plugin';
import { copyText } from '../../../../../monitor-common/utils/utils';
import MonacoEditor from '../../../../../monitor-pc/components/editors/monaco-editor.vue';

import './data-status.scss';

const { i18n } = window;

interface IDataStatus {
  pluginId: string;
}

/**
 * 规则展示
 */
@Component
export default class RulesViewer extends tsc<IDataStatus> {
  @Prop({ default: '', type: String }) pluginId: string;

  sourceDataLoading = false;

  sideslider = {
    isShow: false,
    data: '',
    title: ''
  };

  data = [
    { name: i18n.t('丢弃率'), count: 9.7, unit: '%' },
    { name: i18n.t('丢弃率'), count: 9.7, unit: '%' },
    { name: i18n.t('丢弃率'), count: 9.7, unit: '%' }
  ];

  // 数据采集表格数据
  sourceData: any = [];
  sourceDataTableColumn: any = [
    { label: i18n.tc('序号'), prop: 'number', key: 'number', width: 60 },
    { label: i18n.tc('原始事件'), prop: 'data', key: 'data' },
    { label: i18n.tc('采集时间'), prop: 'bkIngestTime', key: 'time', width: 150 },
    { label: i18n.tc('操作'), prop: 'handle', key: 'handle', width: 150 }
  ];

  @Watch('pluginId', { immediate: true })
  pluginIdChange(pluginId: string) {
    pluginId && this.getSourceData();
  }

  getSourceData() {
    this.sourceDataLoading = true;
    tailEventPluginData(this.pluginId)
      .then(data => {
        this.sourceData = data;
      })
      .finally(() => (this.sourceDataLoading = false));
  }

  handleRefresh() {
    this.getSourceData();
  }

  handleCopy(text: string) {
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  handleShowSource(row) {
    this.sideslider.isShow = true;
    this.sideslider.title = '';
    this.sideslider.data = JSON.stringify(row, null, '\t');
  }

  handleHiddenSlider() {
    this.sideslider.isShow = false;
  }

  protected render() {
    const scopedSlots = {
      default: ({ column, $index, row }) => {
        const prop = column.property;
        if (prop === 'number') return $index + 1;
        if (prop === 'bkIngestTime') return dayjs.tz(row.bk_ingest_time * 1000).format('YYYY-MM-DD HH:mm:ss');
        if (prop === 'handle') {
          return (
            <div>
              <bk-button
                style='margin-right: 5px;'
                text={true}
                onClick={() => this.handleCopy(JSON.stringify(row.data))}
              >
                {this.$t('复制')}
              </bk-button>
              <bk-button
                text={true}
                onClick={() => this.handleShowSource(row)}
              >
                {this.$t('查看上报日志')}
              </bk-button>
            </div>
          );
        }
        if (prop === 'data') {
          if (!row.data?.length) return '--';
          return (
            <div
              class='data-item-list'
              style='min-height: 42px;'
            >
              {row.data.map(item => (
                <div class='data-item'>{JSON.stringify(item)}</div>
              ))}
            </div>
          );
        }
        return row[column.property];
      }
    };
    return (
      <div class='data-status-wrap'>
        {/* <div class="data-count-wrap">
          {
          this.data.map(item => (
            <div class="data-count-item">
            <span class="count-label">{ item.name }</span>
            <span class="count-text">{ item.count}{item.unit}</span>
            </div>
          ))
          }
        </div> */}
        {/* <div class="data-chart-wrap">
          <div class="content-title-h1">{i18n.t('丢失丢弃')}</div>
        </div> */}
        <div
          class='source-data-wrap'
          v-bkloading={{ isLoading: this.sourceDataLoading }}
        >
          <div class='content-title-h1'>
            <span>{i18n.t('数据采样')}</span>
            <span
              class='right-btn-wrap'
              onClick={this.handleRefresh}
            >
              <i class='icon-monitor icon-shuaxin'></i>
              {i18n.t('button-刷新')}
            </span>
          </div>
          <bk-table data={this.sourceData}>
            {this.sourceDataTableColumn.map((item, i) => (
              <bk-table-column
                key={i}
                label={item.label}
                prop={item.prop}
                width={item.width}
                resizable={false}
                {...{ scopedSlots }}
              ></bk-table-column>
            ))}
          </bk-table>
        </div>
        {/* <MonacoEditor
            class="code-viewer"
            language="json"
            value={this.sideslider.data}
            options={{ readOnly: true }}
            style="height: calc(100vh - 61px)">
        </MonacoEditor> */}
        <bk-sideslider
          ext-cls='data-status-sideslider'
          transfer={true}
          isShow={this.sideslider.isShow}
          {...{ on: { 'update:isShow': v => (this.sideslider.isShow = v) } }}
          quick-close={true}
          width={656}
          onHidden={this.handleHiddenSlider}
        >
          <div
            slot='header'
            class='sideslider-title'
          >
            <span>{this.sideslider.title + this.$t('上报日志详情')}</span>
            <bk-button onClick={() => this.handleCopy(this.sideslider.data)}>{this.$tc('复制')}</bk-button>
          </div>
          <div slot='content'>
            <MonacoEditor
              class='code-viewer'
              language='json'
              value={this.sideslider.data}
              options={{ readOnly: true }}
              style='height: calc(100vh - 60px)'
            ></MonacoEditor>
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
