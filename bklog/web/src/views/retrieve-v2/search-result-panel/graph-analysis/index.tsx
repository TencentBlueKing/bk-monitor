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

import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SqlPanel from './SqlPanel.vue';
import GraphChart from './chart/graph-chart.vue';
import GraphTable from './chart/graph-table.vue';
import FieldSettings from './common/FieldSettings.vue';
import DashboardDialog from './dashboardDialog.vue';
import GraphDragTool from './drag-tool/index.vue';
import StyleImages from './images/index';
import TagInput from './tagInput.vue';

import './index.scss';

interface IProps {
  data: any;
}

enum OptionList {
  Analysis = 'analysis',
  Overview = 'overview',
}

enum GraphCategory {
  BAR = 'bar',
  LINE = 'line',
  LINE_BAR = 'line_bar',
  PIE = 'pie',
  TABLE = 'table',
}

@Component({
  components: { GraphDragTool, DashboardDialog, TagInput, SqlPanel, GraphTable, GraphChart, FieldSettings },
})
export default class GraphAnalysisIndex extends tsc<IProps> {
  activeItem = OptionList.Analysis;
  minAxiosOptionHeight = 148;
  axiosOptionHeight = 148;
  rightOptionWidth = 360;
  minRightOptionWidth = 360;
  activeGraphCategory = GraphCategory.BAR;
  xAxis = '';
  yAxis = '';
  chartData = {};
  select_fields_order = [];
  hidden = [];
  segmented = [];
  advanceHeight = 164;
  activeSettings = ['basic_info', 'field_setting'];
  isChartMode = false;
  graphCategoryList = [
    GraphCategory.LINE,
    GraphCategory.BAR,
    GraphCategory.LINE_BAR,
    GraphCategory.PIE,
    GraphCategory.TABLE,
  ];

  basicInfoTitle = {
    show: true,
    title: '',
  };

  basicInfoSubTitle = {
    show: false,
    title: '',
  };

  basicInfoDescription = {
    show: false,
    title: '',
  };

  fieldList = [1];
  advanceSetting = false;
  activeCanvasType = 'bar';

  get graphCategory() {
    return {
      [GraphCategory.LINE]: {
        icon: '',
        text: this.$t('折线图'),
        click: () => this.handleGraphCategoryClick(GraphCategory.LINE),
        images: {
          def: StyleImages.chartLineDef,
          active: StyleImages.chartLineActive,
        },
      },
      [GraphCategory.BAR]: {
        icon: '',
        text: this.$t('柱状图'),
        click: () => this.handleGraphCategoryClick(GraphCategory.BAR),
        images: {
          def: StyleImages.chartBarDef,
          active: StyleImages.chartBarActive,
        },
      },
      [GraphCategory.LINE_BAR]: {
        icon: '',
        text: this.$t('数字'),
        click: () => this.handleGraphCategoryClick(GraphCategory.LINE_BAR),
        images: {
          def: StyleImages.chartLineBarDef,
          active: StyleImages.chartLineBarActive,
        },
      },
      [GraphCategory.PIE]: {
        icon: '',
        text: this.$t('饼图'),
        click: () => this.handleGraphCategoryClick(GraphCategory.PIE),
        images: {
          def: StyleImages.chartPieDef,
          active: StyleImages.chartPieActive,
        },
      },
      [GraphCategory.TABLE]: {
        icon: '',
        text: this.$t('表格'),
        click: () => this.handleGraphCategoryClick(GraphCategory.TABLE),
        images: {
          def: StyleImages.chartTableDef,
          active: StyleImages.chartTableActive,
        },
      },
    };
  }

  get axiosStyle() {
    return {
      height: `${this.axiosOptionHeight}px`,
    };
  }

  get canvasStyle() {
    return {
      height: `calc(100% - ${this.axiosOptionHeight + 16}px)`,
    };
  }

  get rightOptionStyle() {
    return {
      width: `${this.rightOptionWidth}px`,
    };
  }

  get advanceSettingClass() {
    return this.advanceSetting ? 'icon-collapse-small' : 'icon-expand-small';
  }
  // 如果是table类型，切换为table，反之，切换为图表
  handleGraphCategoryClick(category: GraphCategory) {
    this.activeGraphCategory = category;
    this.activeCanvasType = category;
  }

  handleAdvanceSettingClick() {
    this.advanceSetting = !this.advanceSetting;
    this.axiosOptionHeight = this.axiosOptionHeight + (this.advanceSetting ? 1 : -1) * this.advanceHeight;
    this.minAxiosOptionHeight = this.minAxiosOptionHeight + (this.advanceSetting ? 1 : -1) * this.advanceHeight;
  }

  renderGraphCategory() {
    return this.graphCategoryList.map(category => {
      const item = this.graphCategory[category];
      const isActive = this.activeGraphCategory === category;
      const imgHref = isActive ? item.images.active : item.images.def;
      return (
        <div
          class={{ 'category-item': true, active: isActive }}
          onClick={item.click}
        >
          <div class='category-img'>
            <img src={imgHref}></img>
          </div>
          <div class='category-text'>{item.text}</div>
        </div>
      );
    });
  }

  renderBasicInfo() {
    return [
      <div class='basic-info-row'>
        <bk-checkbox
          v-model={this.basicInfoTitle.show}
          checked={true}
          false-value={false}
          true-value={true}
        >
          {this.$t('标题')}
        </bk-checkbox>
        {this.basicInfoTitle.show && (
          <bk-input
            style='margin-top: 8px;'
            v-model={this.basicInfoTitle.title}
            placeholder={this.$t('请输入标题')}
          ></bk-input>
        )}
      </div>,
      <div class='basic-info-row'>
        <bk-checkbox
          v-model={this.basicInfoSubTitle.show}
          checked={false}
          false-value={false}
          true-value={true}
        >
          {this.$t('副标题')}
        </bk-checkbox>
        {this.basicInfoSubTitle.show && (
          <bk-input
            style='margin-top: 8px;'
            v-model={this.basicInfoSubTitle.title}
            placeholder={this.$t('请输入副标题')}
          ></bk-input>
        )}
      </div>,
      <div class='basic-info-row'>
        <bk-checkbox
          v-model={this.basicInfoDescription.show}
          checked={false}
          false-value={false}
          true-value={true}
        >
          {this.$t('描述')}
        </bk-checkbox>
        {this.basicInfoDescription.show && (
          <bk-input
            style='margin-top: 8px;'
            v-model={this.basicInfoDescription.title}
            placeholder={this.$t('请输入描述')}
            type='textarea'
          ></bk-input>
        )}
      </div>,
    ];
  }

  renderFieldsSetting() {
    return this.fieldList.map(field => {
      return (
        <div
          key={field}
          class='field-setting-row'
        >
          <div class='field'>{field}</div>
          <div class='type'>指标</div>
        </div>
      );
    });
  }

  renderDimensionsAndIndexSetting() {
    const getAadvanceSettingList = () => {
      if (!this.advanceSetting) {
        return [];
      }
      return [
        <div class='dimensions-index-row'>
          <div class='label'>{this.$t('过滤')}</div>
          <div class='settings'></div>
        </div>,
        <div class='dimensions-index-row'>
          <div class='label'>{this.$t('排序')}</div>
          <div class='settings'></div>
        </div>,
        <div class='dimensions-index-row'>
          <div class='label'>{this.$t('限制')}</div>
          <div class='settings white'>
            <bk-input
              style='width: 120px;'
              type='number'
            ></bk-input>
          </div>
        </div>,
      ];
    };
    if (this.isChartMode) {
      return [
        <SqlPanel
          ref='sqlPanelRef'
          onSearch-completed={this.echartData}
        ></SqlPanel>,
      ];
    }
    return [
      <div class='dimensions-index-row'>
        <div class='label'>{this.$t('指标')}</div>
        <TagInput></TagInput>
      </div>,
      <div class='dimensions-index-row'>
        <div class='label'>{this.$t('维度')}</div>
        <div class='settings'></div>
      </div>,
      <div class='dimensions-index-row'>
        <div class='label'></div>
        <div
          class='advance-setting'
          onClick={this.handleAdvanceSettingClick}
        >
          {this.$t('高级设置')}
          <i class={['log-icon', this.advanceSettingClass]}></i>
        </div>
      </div>,
      ...getAadvanceSettingList(),
    ];
  }

  handleCanvasTypeChange(t) {
    this.activeCanvasType = t;
  }

  handleHorizionMoveEnd({ offsetY }) {
    let target = this.axiosOptionHeight + (offsetY ?? 0);
    if (this.minAxiosOptionHeight > target) {
      target = this.minAxiosOptionHeight;
    }

    this.axiosOptionHeight = target;
    if (this.isChartMode && this.$refs.sqlPanelRef) {
      this.$refs.sqlPanelRef.resize();
    }
  }
  handleVerticalMoveEnd({ offsetX }) {
    let target = this.rightOptionWidth - offsetX;
    if (this.minRightOptionWidth > target) {
      target = this.minRightOptionWidth;
    }

    this.rightOptionWidth = target;
  }

  renderCanvasChartAndTable() {
    const showTable = this.activeCanvasType === 'table';
    const tableStyle = { display: showTable ? 'block' : 'none' };
    const chartStyle = { display: !showTable ? 'block' : 'none' };
    return [
      <GraphTable
        ref='refGraphTable'
        style={tableStyle}
        hidden={this.hidden}
      ></GraphTable>,
      <GraphChart
        ref='refGraphChart'
        style={chartStyle}
        activeGraphCategory={this.activeGraphCategory}
      ></GraphChart>,
    ];
  }
  save() {}
  /** 打开添加到仪表盘dialog */
  handleAdd() {
    console.log(this.$refs.addDialog);
    this.$refs.addDialog.handleShow();
  }
  changeModel() {
    this.isChartMode = !this.isChartMode;
    // const { query } = panelModel.value;
    // // query为空，无需切换提示
    // if (isEqual(query, new QueryPanelClass())) {
    //   switchSqlMode();
    //   return;
    // }
    // // sql模式，没有配置指标维度，无需切换提示
    // if (query.raw_query && query.dimensions?.length === 0 && query.metrics?.length === 0 && !query.query_text) {
    //   switchSqlMode();
    //   return;
    // }
    // Confirm(t('common.提示'), t('dashboards.切换模式后，图表配置将会被清空，是否继续？'), () => {
    //   switchSqlMode();
    // });
  }
  /** echart和字段配置展示 */
  echartData(data) {
    let arr = data.data.result_schema.filter(item => item.field_type !== 'string');
    this.xAxis = arr[0].field_name;
    this.yAxis = arr[1].field_name;
    this.select_fields_order = data.data.select_fields_order;
    this.chartData = data;
    this.$refs.refGraphChart.setOption(data, this.xAxis, this.yAxis);

    this.$refs.refGraphTable.setOption(data);
    this.fieldList = data.data.select_fields_order;
  }
  updateChartData(axis, newValue) {
    console.log(axis, newValue);
    if (axis === 'x') {
      this.xAxis = newValue;
      this.$refs.refGraphChart.setOption(this.chartData, this.xAxis, this.yAxis, this.segmented);
    } else if (axis === 'y') {
      this.yAxis = newValue;
      this.$refs.refGraphChart.setOption(this.chartData, this.xAxis, this.yAxis, this.segmented);
    } else if (axis === 'hidden') {
      this.hidden = newValue;
    } else if (axis === 'segmented') {
      this.segmented = newValue;
      this.$refs.refGraphChart.setOption(this.chartData, this.xAxis, this.yAxis, this.segmented);
    }
  }

  // updateYAxis(newValue) {
  //   this.yAxis = newValue;
  //   this.$refs.refGraphChart.setOption(this.chartData, this.xAxis, this.yAxis);
  // }
  render() {
    return (
      <div class='graph-analysis-index'>
        <div class='graph-analysis-navi'>
          <div class='option-switch'>
            <bk-switcher
              class='ml-medium mr-min'
              theme='primary'
              value={this.isChartMode}
              onChange={this.changeModel}
            ></bk-switcher>
            <span>{this.$t('SQL模式')}</span>
          </div>
          <div class='option-list'>
            <div class={{ active: this.activeItem === OptionList.Analysis }}>
              <span class='bklog-icon bklog-help'></span>
              <span>分析</span>
            </div>
            <div class={{ active: this.activeItem === OptionList.Overview }}>
              <span class='bklog-icon bklog-overview'></span>
              <span>概览</span>
            </div>
          </div>
          <div class='option-btn'>
            <bk-button
              style='margin-right: 8px;'
              outline={true}
              theme='primary'
              onClick={this.save}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button
              outline={true}
              onClick={this.handleAdd}
            >
              {this.$t('添加至仪表盘')}
            </bk-button>
          </div>
        </div>

        <div class='graph-analysis-body'>
          {/* {this.isChartMode ? (
            <SqlPanel></SqlPanel>
          ) : ( */}
          <div class='body-left'>
            <div
              style={this.axiosStyle}
              class='graph-axios-options'
            >
              <div class='graph-axios-rows'>{this.renderDimensionsAndIndexSetting()}</div>
              <div class='graph-axios-drag'>
                <GraphDragTool
                  class='horizional-drag-tool'
                  direction='horizional'
                  onMove-end={this.handleHorizionMoveEnd}
                ></GraphDragTool>
              </div>
            </div>
            <div
              style={this.canvasStyle}
              class='graph-canvas-options'
            >
              <div class='canvas-head'>
                {this.basicInfoTitle.show ? <span class='title'>{this.basicInfoTitle.title}</span> : ''}
                <span class='icons'>
                  <span
                    class={{ active: this.activeCanvasType !== 'table' }}
                    onClick={() => this.handleCanvasTypeChange('bar')}
                  >
                    <i class='bklog-icon bklog-bar'></i>
                  </span>
                  <span
                    class={{ active: this.activeCanvasType === 'table' }}
                    onClick={() => this.handleCanvasTypeChange('table')}
                  >
                    <i class='bklog-icon bklog-table'></i>
                  </span>
                </span>
              </div>
              {this.renderCanvasChartAndTable()}
            </div>
          </div>
          {/* )} */}
          <div
            style={this.rightOptionStyle}
            class='body-right'
          >
            <div class='graph-category'>
              <div class='category-title'>{this.$t('图表样式')}</div>
              <div class='category-list'>{this.renderGraphCategory()}</div>
            </div>
            <div class='graph-info'>
              <GraphDragTool
                class='vertical-drag-tool'
                direction='vertical'
                onMove-end={this.handleVerticalMoveEnd}
              ></GraphDragTool>
              <bk-collapse
                class='graph-info-collapse'
                v-model={this.activeSettings}
              >
                <bk-collapse-item name='basic_info'>
                  <span class='graph-info-collapse-title'>{this.$t('基础信息')}</span>
                  <div slot='content'>{this.renderBasicInfo()}</div>
                </bk-collapse-item>
                <bk-collapse-item name='field_setting'>
                  <span class='graph-info-collapse-title'>{this.$t('字段设置')}</span>
                  {/* <div slot='content'>{this.renderFieldsSetting()}</div> */}
                  <FieldSettings
                    slot='content'
                    activeGraphCategory={this.activeGraphCategory}
                    select_fields_order={this.select_fields_order}
                    xAxis={this.xAxis}
                    yAxis={this.yAxis}
                    onUpdate={this.updateChartData}
                  ></FieldSettings>
                </bk-collapse-item>
              </bk-collapse>
            </div>
          </div>
        </div>

        <DashboardDialog ref='addDialog'></DashboardDialog>
      </div>
    );
  }
}
