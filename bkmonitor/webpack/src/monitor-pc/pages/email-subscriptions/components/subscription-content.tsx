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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import Sortable from 'sortablejs';

import { deepClone } from '../../../../monitor-common/utils/utils';

import './subscription-content.scss';

interface ITableData {
  contentDetails?: string;
  contentTitle?: string;
  graphName?: { graphId?: string; graphName?: string }[];
  graphs?: { id?: string; name: string }[];
  id?: number;
  reportItem?: number;
  rowPicturesNum?: number;
  curBizId?: string;
  curGrafana?: string;
  curGrafanaName?: string;
}
interface ISubscriptionContent {
  data: {
    viewData?: ITableData[];
    pullData?: ITableData[];
  };
  contentType?: string;
}

@Component({
  name: 'SubscriptionContent'
})
export default class SubscriptionContent extends tsc<ISubscriptionContent> {
  @Prop({
    type: Object,
    default: () => ({
      viewData: [],
      pullData: []
    })
  })
  data: ISubscriptionContent['data'];
  @Prop({ type: String, default: 'view' }) contentType: string;

  curTab = 'view';
  tabList = [
    { name: 'view', label: window.i18n.t('视图截取') },
    { name: 'full', label: window.i18n.t('整屏截取') }
  ];
  tips = {
    view: window.i18n.t(
      '视图截图指从仪表盘中的视图中获取，可以将不同的仪表盘下的部分内容生成一份报表，而且格式简洁方便邮件的输出。'
    ),
    full: window.i18n.t(
      '整屏截取指截取整个仪表盘，按宽度800截取，方便快速创建一个仪表盘的邮件订阅，因为邮件有大小限制，为保证发送质量会进行长宽限制和切分。并且限制只有一个。'
    )
  };
  tableKey = null;
  curFromIndex = 0;
  sortEndReportContents = [];
  bizIdListNameMap: { [propName: string]: string } = {};
  @Watch('contentType', { immediate: true })
  handleContentType(v) {
    if (v) {
      this.curTab = v;
    }
  }

  // 视图截取排序
  @Emit('viewSort')
  handleViewDataChange(data) {
    return data;
  }
  // 添加内容
  @Emit('add')
  handleAdd() {
    return this.curTab;
  }
  // 删除
  @Emit('del')
  handleDel(index: number) {
    return index;
  }
  // 编辑
  @Emit('edit')
  handleEdit(row: ITableData, index: number) {
    return { row, index };
  }
  // 切换截取类型
  @Emit('typeChange')
  handleTypeChange(type: string) {
    return type;
  }
  created() {
    this.$store.getters.bizList.forEach(item => {
      this.bizIdListNameMap[item.id] = String(item.text).replace(`[${item.id}] `, '');
    });
  }

  mounted() {
    this.rowDrop();
  }

  handleTabChange(val: string) {
    this.curTab = val;
    this.handleTypeChange(val);
  }

  rowDrop() {
    const tbody = this.$el.querySelector('.drag-table-wrap .bk-table-body-wrapper tbody');
    let tableData = [];
    Sortable.create(tbody, {
      onStart: ({ oldIndex: from }) => {
        this.curFromIndex = from;
      },
      onEnd: ({ newIndex: to, oldIndex: from }) => {
        if (to === from) return;
        tableData = deepClone(this.sortEndReportContents);
        this.handleViewDataChange(tableData);
        this.tableKey = String(new Date());
        this.sortEndReportContents = [];
        this.$nextTick(() => {
          this.rowDrop();
        });
      },
      onChange: ({ newIndex: to }) => {
        const from = this.curFromIndex;
        this.sortEndReportContents = this.sortEndReportContents.length
          ? this.sortEndReportContents
          : deepClone(this.data.viewData);
        const temp = this.sortEndReportContents[to];
        this.sortEndReportContents[to] = this.sortEndReportContents[from];
        this.sortEndReportContents[from] = temp;
        this.curFromIndex = to;
      }
    });
  }

  getTabDisable(name: string) {
    if (name === 'view' && this.data.pullData.length) {
      return true;
    }
    if (name === 'full' && this.data.viewData.length) {
      return true;
    }
    return false;
  }
  // 视图截取表格
  getViewTable() {
    const tableColumnsMap: { label: string; key: string; width?: number }[] = [
      { label: window.i18n.tc('子标题'), key: 'contentTitle' },
      { label: window.i18n.tc('图表数量'), key: 'graphs', width: 150 },
      { label: window.i18n.tc('布局'), key: 'rowPicturesNum', width: 150 },
      { label: window.i18n.tc('说明'), key: 'contentDetails' }
    ];
    const formatterColumn = (row, column, cellValue) => {
      if (column.property === 'layout') return cellValue + this.$t('个/行');
      if (column.property === 'graphs') return cellValue.length;
      return cellValue;
    };
    const iconSlot = {
      default: () => <span class='icon-drag'></span>
    };
    const operateSlot = {
      default: props => [
        <bk-button
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleEdit(props.row, props.$index)}
        >
          {this.$t('button-编辑')}
        </bk-button>,
        <bk-button
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleDel(props.$index)}
        >
          {this.$t('删除')}
        </bk-button>
      ]
    };
    return (
      <bk-table
        class='drag-table-wrap'
        key={this.tableKey}
        data={this.data.viewData}
      >
        <bk-table-column
          width={52}
          scopedSlots={iconSlot}
        ></bk-table-column>
        {tableColumnsMap.map(item => (
          <bk-table-column
            key={item.key}
            label={item.label}
            prop={item.key}
            show-overflow-tooltip={['contentTitle', 'contentDetails'].includes(item.key)}
            width={item.width}
            formatter={formatterColumn}
          ></bk-table-column>
        ))}
        <bk-table-column
          label={this.$t('操作')}
          width={150}
          scopedSlots={operateSlot}
        ></bk-table-column>
      </bk-table>
    );
  }
  // 整屏截取表格
  getPullTable() {
    const tableColumnsMap: { label: string; key: string; width?: number }[] = [
      { label: window.i18n.tc('子标题'), key: 'contentTitle' },
      { label: window.i18n.tc('说明'), key: 'contentDetails', width: 150 },
      { label: window.i18n.tc('业务'), key: 'curBizId', width: 150 },
      { label: window.i18n.tc('仪表盘名称'), key: 'curGrafanaName' }
    ];
    const operateSlot = {
      default: props => [
        <bk-button
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleEdit(props.row, props.$index)}
        >
          {this.$t('编辑')}
        </bk-button>,
        <bk-button
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleDel(props.$index)}
        >
          {this.$t('删除')}
        </bk-button>
      ]
    };
    return (
      <bk-table data={this.data.pullData}>
        <bk-table-column width={52}></bk-table-column>
        {tableColumnsMap.map(item => {
          if (item.key === 'curBizId') {
            return (
              <bk-table-column
                key={item.key}
                label={item.label}
                width={item.width}
                scopedSlots={{ default: ({ row }) => this.bizIdListNameMap[row.curBizId] || '--' }}
              ></bk-table-column>
            );
          }
          if (item.key === 'curGrafanaName') {
            return (
              <bk-table-column
                key={item.key}
                label={item.label}
                width={item.width}
                scopedSlots={{
                  default: ({ row }) => row.curGrafanaName || <div class='status-loading'></div>
                }}
              ></bk-table-column>
            );
          }
          return (
            <bk-table-column
              key={item.key}
              label={item.label}
              prop={item.key}
              width={item.width}
            ></bk-table-column>
          );
        })}
        <bk-table-column
          label={this.$t('操作')}
          width={150}
          scopedSlots={operateSlot}
        ></bk-table-column>
      </bk-table>
    );
  }

  render() {
    return (
      <div class='subscription-content-component'>
        <div class='content-tab'>
          <bk-tab
            active={this.curTab}
            on-tab-change={this.handleTabChange}
            type='unborder-card'
          >
            {this.tabList.map(item => (
              <bk-tab-panel
                {...{ props: item }}
                key={item.name}
                disabled={this.getTabDisable(item.name)}
              ></bk-tab-panel>
            ))}
          </bk-tab>
        </div>
        <div class='content-tip'>
          <span class='icon-monitor icon-hint'></span>
          <span class='text'>{this.tips[this.curTab]}</span>
        </div>
        <bk-button
          theme='primary'
          outline={true}
          on-click={this.handleAdd}
        >
          {this.$t('button-添加内容')}
        </bk-button>
        <div class='content-table'>
          <div style={{ display: this.curTab === this.tabList[0].name ? 'block' : 'none' }}>{this.getViewTable()}</div>
          <div style={{ display: this.curTab === this.tabList[1].name ? 'block' : 'none' }}>{this.getPullTable()}</div>
        </div>
      </div>
    );
  }
}
