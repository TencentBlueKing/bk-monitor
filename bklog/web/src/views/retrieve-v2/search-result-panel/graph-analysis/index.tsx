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

import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Message } from 'bk-magic-vue';

import $http from '../../../../api';
import SqlPanel from './SqlPanel.vue';
import GraphChart from './chart/index.tsx';
import FieldSettings from './common/FieldSettings.vue';
import DashboardDialog from './dashboardDialog.vue';
import GraphDragTool from './drag-tool/index.vue';
import StyleImages from './images/index';
import SqlEditor from './sql-editor/index.tsx';
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
  CHART = 'chart',
  LINE = 'line',
  LINE_BAR = 'line_bar',
  PIE = 'pie',
  TABLE = 'table',
}

@Component({
  components: {
    GraphDragTool,
    DashboardDialog,
    TagInput,
    SqlPanel,
    GraphChart,
    FieldSettings,
    SqlEditor,
  },
})
export default class GraphAnalysisIndex extends tsc<IProps> {
  activeItem = OptionList.Analysis;
  minAxiosOptionHeight = 148;
  axiosOptionHeight = 148;
  rightOptionWidth = 360;
  minRightOptionWidth = 360;
  activeGraphCategory = GraphCategory.TABLE;
  chartActiveType = GraphCategory.TABLE;
  xAxis = [];
  yAxis = [];
  chartData: { data?: any; list?: any[]; result_schema?: any[]; select_fields_order?: string[] } = {};
  resultSchema = [];
  hiddenFields = [];
  dimensions = [];
  uiQueryValue = [];
  sqlQueryValue = '';
  advanceHeight = 164;
  activeSettings = ['basic_info', 'field_setting'];
  isSqlMode = true;
  graphCategoryList = [GraphCategory.TABLE, GraphCategory.LINE, GraphCategory.BAR, GraphCategory.PIE];

  basicInfoTitle = {
    show: false,
    title: '',
  };

  basicInfoSubTitle = {
    show: false,
    title: '',
  };

  fieldList = [1];
  advanceSetting = false;

  sqlEditorHeight = 400;
  isSqlValueChanged = false;
  chartCounter = 0;
  errorResponse = { code: 0, message: '', result: true };

  get graphCategory() {
    return {
      [GraphCategory.TABLE]: {
        icon: '',
        text: this.$t('表格'),
        click: () => this.handleGraphCategoryClick(GraphCategory.TABLE),
        images: {
          def: StyleImages.chartTableDef,
          active: StyleImages.chartTableActive,
        },
      },
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

      [GraphCategory.PIE]: {
        icon: '',
        text: this.$t('饼图'),
        click: () => this.handleGraphCategoryClick(GraphCategory.PIE),
        images: {
          def: StyleImages.chartPieDef,
          active: StyleImages.chartPieActive,
        },
      },
    };
  }

  get bottomHeight() {
    return this.isSqlMode ? this.sqlEditorHeight : this.axiosOptionHeight;
  }

  get axiosStyle() {
    return {
      height: `${this.bottomHeight}px`,
    };
  }

  get canvasStyle() {
    return {
      height: `calc(100% - ${this.bottomHeight + 16}px)`,
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

  get chartOptions() {
    const chartType = this.chartActiveType === GraphCategory.TABLE ? GraphCategory.TABLE : this.activeGraphCategory;
    return {
      xFields: this.xAxis,
      yFields: this.yAxis,
      type: chartType,
      dimensions: this.dimensions,
      data: this.chartData.data,
      category: this.activeGraphCategory,
      hiddenFields: this.hiddenFields,
    };
  }

  get storedChartParams() {
    return this.$store.state.indexItem.chart_params ?? {};
  }

  get extendParams() {
    return {
      favorite_type: 'chart',
      chart_params: {
        xFields: this.xAxis,
        yFields: this.yAxis,
        activeGraphCategory: this.activeGraphCategory,
        chartActiveType: this.chartActiveType,
        dimensions: this.dimensions,
      },
      search_mode: 'sql',
    };
  }

  @Watch('storedChartParams', { deep: true })
  handleChartParamsChange() {
    if (this.storedChartParams) {
      ['xFields', 'yFields', 'activeGraphCategory', 'chartActiveType', 'dimensions', 'hiddenFields'].forEach(key => {
        if (this.storedChartParams[key]) {
          Object.assign(this, { [key]: this.storedChartParams[key] });
        }
      });
    }
  }

  handleSqlQueryError(resp) {
    Object.assign(this.errorResponse, resp);
  }

  handleEditorSearchClick() {
    (this.$refs.sqlEditor as any)?.handleQueryBtnClick();
  }

  handleSqlValueChange() {
    this.isSqlValueChanged = true;
  }

  // 如果是table类型，切换为table，反之，切换为图表
  handleGraphCategoryClick(category: GraphCategory) {
    if (category !== GraphCategory.TABLE) {
      this.chartActiveType = GraphCategory.CHART;
    }
    this.activeGraphCategory = category;
    this.chartCounter++;
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
    if (this.isSqlMode) {
      return [
        <SqlEditor
          ref='sqlEditor'
          extendParams={this.extendParams}
          onChange={this.handleSqlQueryResultChange}
          onError={this.handleSqlQueryError}
          onSql-change={this.handleSqlValueChange}
        ></SqlEditor>,
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

  handleCanvasTypeChange(t?: GraphCategory) {
    this.chartActiveType = t;
    this.chartCounter++;
  }

  handleHorizionMoveEnd({ offsetY }) {
    let target = this.axiosOptionHeight + (offsetY ?? 0);
    if (this.minAxiosOptionHeight > target) {
      target = this.minAxiosOptionHeight;
    }

    if (this.isSqlMode) {
      this.sqlEditorHeight = target;
      return;
    }

    this.axiosOptionHeight = target;
  }
  handleVerticalMoveEnd({ offsetX }) {
    let target = this.rightOptionWidth - offsetX;
    if (this.minRightOptionWidth > target) {
      target = this.minRightOptionWidth;
    }

    this.rightOptionWidth = target;
  }

  getExceptionRender() {
    if (!this.errorResponse.result && this.errorResponse.message) {
      <bk-exception
        class='bklog-chart-exception'
        type='500'
      >
        <div class='bk-exception-title'>{this.errorResponse.message}</div>
        <div class='bk-exception-description'>请重新发起查询</div>
        <div class='bk-exception-footer'>
          <bk-button
            class='mr10'
            size='small'
            theme='primary'
            type='submit'
            onClick={this.handleEditorSearchClick}
          >
            查询
          </bk-button>
        </div>
      </bk-exception>;
    }

    if (!this.chartOptions.data?.list?.length) {
      return (
        <bk-exception
          class='bklog-chart-exception'
          scene='part'
          type='empty'
        ></bk-exception>
      );
    }

    if (this.isSqlValueChanged) {
      return (
        <bk-exception
          class='bklog-chart-exception'
          type='500'
        >
          <div class='bk-exception-title'>图表查询配置已变更</div>
          <div class='bk-exception-description'>请重新发起查询</div>
          <div class='bk-exception-footer'>
            <bk-button
              class='mr10'
              size='small'
              theme='primary'
              type='submit'
              onClick={this.handleEditorSearchClick}
            >
              查询
            </bk-button>
            <bk-button
              class='mr10'
              size='small'
              onClick={() => {
                this.isSqlValueChanged = false;
              }}
            >
              我知道了
            </bk-button>
          </div>
        </bk-exception>
      );
    }

    return '';
  }

  renderCanvasChartAndTable() {
    return (
      <GraphChart
        chartCounter={this.chartCounter}
        chartOptions={this.chartOptions}
      ></GraphChart>
    );
  }
  async save() {
    if (!this.basicInfoTitle.title) {
      Message({
        message: '请输入标题',
        theme: 'primary',
      });
      return;
    }
    const res = await $http.request('graphAnalysis/favoriteSQL', {
      data: {
        favorite_type: 'chart',
        space_uid: this.$store.state.spaceUid,
        name: this.basicInfoTitle.title,
        visible_type: 'public',
        index_set_id: this.$store.state.indexId,
        chart_params: {
          aa: 'aa',
        },
      },
    });
    console.log(res);
  }
  /** 打开添加到仪表盘dialog */
  handleAdd() {
    console.log(this.$refs.addDialog);
    // this.$refs.addDialog.handleShow();
  }
  changeModel() {
    this.isSqlMode = !this.isSqlMode;
  }

  handleSqlQueryResultChange(data) {
    this.resultSchema = data.data?.result_schema ?? [];
    this.chartData = data;
    this.$set(this, 'chartData', data);
    this.chartCounter++;
    this.isSqlValueChanged = false;
  }

  updateChartData(axis, newValue) {
    this[axis] = (Array.isArray(newValue) ? newValue : [newValue]).filter(t => !!t);
    this.chartCounter++;
  }
  handleRefresh() {}

  render() {
    return (
      <div class='graph-analysis-index'>
        <div
          style='display: none;'
          class='graph-analysis-navi'
        ></div>

        <div class='graph-analysis-body'>
          <div class='body-left'>
            <div
              style={this.axiosStyle}
              class={['graph-axios-options', this.isSqlMode ? 'sql-mode' : '']}
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
                    class={{ active: this.chartActiveType !== GraphCategory.TABLE }}
                    v-show={this.activeGraphCategory !== GraphCategory.TABLE}
                    onClick={() => this.handleCanvasTypeChange(GraphCategory.CHART)}
                  >
                    <i class='bklog-icon bklog-bar'></i>
                  </span>
                  <span
                    class={{ active: this.chartActiveType === GraphCategory.TABLE }}
                    onClick={() => this.handleCanvasTypeChange(GraphCategory.TABLE)}
                  >
                    <i class='bklog-icon bklog-table'></i>
                  </span>
                </span>
              </div>
              {this.renderCanvasChartAndTable()}
              {this.getExceptionRender()}
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
                    result_schema={this.resultSchema}
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
