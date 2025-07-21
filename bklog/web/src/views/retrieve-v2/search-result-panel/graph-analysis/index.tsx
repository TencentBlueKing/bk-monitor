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

import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '@/store/store.type.ts';
import { isElement, debounce, throttle, isEqual } from 'lodash';
import { Component, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SqlPanel from './SqlPanel.vue';
import GraphChart from './chart/index.tsx';
import FieldSettings from './common/field-settings.vue';
import DashboardDialog from './dashboardDialog.vue';
import GraphDragTool from './drag-tool/index.vue';
import StyleImages from './images/index';
import './index.scss';
import SqlEditor from './sql-editor/index.tsx';
import TagInput from './tagInput.vue';

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
  NUMBER = 'number',
  PIE = 'pie',
  TABLE = 'table',
}

@Component({
  components: {
    DashboardDialog,
    FieldSettings,
    GraphChart,
    GraphDragTool,
    SqlEditor,
    SqlPanel,
    TagInput,
  },
})
export default class GraphAnalysisIndex extends tsc<IProps> {
  activeItem = OptionList.Analysis;
  minAxiosOptionHeight = 148;
  axiosOptionHeight = 400;
  rightOptionWidth = 360;
  minRightOptionWidth = 360;
  activeGraphCategory = GraphCategory.TABLE;
  chartActiveType = GraphCategory.TABLE;
  xFields = [];
  yFields = [];
  chartData: {
    data?: any;
    list?: any[];
    result_schema?: any[];
    select_fields_order?: string[];
  } = {};
  resultSchema = [];
  hiddenFields = [];
  dimensions = [];
  uiQueryValue = [];
  sqlQueryValue = '';
  advanceHeight = 164;
  activeSettings = ['basic_info', 'field_setting'];
  isSqlMode = true;

  graphCategoryList = [
    GraphCategory.TABLE,
    GraphCategory.LINE,
    GraphCategory.BAR,
    GraphCategory.PIE,
    GraphCategory.NUMBER,
  ];

  basicInfoTitle = {
    title: '',
  };

  fieldList = [1];
  advanceSetting = false;

  sqlEditorHeight = 400;
  isSqlValueChanged = false;
  chartCounter = 0;
  errorResponse = { code: 0, message: '', result: true };
  sqlContent = '';
  canvasBodyStyle = {
    height: 400,
    scrollTop: 0,
    with: 300,
  };

  debounceCallback = debounce((entry) => {
    const { offsetHeight, offsetWidth } = entry.target;
    Object.assign(this.canvasBodyStyle, {
      height: offsetHeight,
      with: offsetWidth,
    });
  }, 120);

  throttleScrollCallback = throttle((event) => {
    Object.assign(this.canvasBodyStyle, {
      scrollTop: (event.target as HTMLElement).scrollTop,
    });
  });

  resizeObserver = null;
  isRequesting = false;

  get exceptionStyle() {
    const scrollHeight =
      this.canvasBodyStyle.scrollTop < this.sqlEditorHeight
        ? this.canvasBodyStyle.scrollTop
        : this.sqlEditorHeight;

    return {
      '--exception-height': `${this.canvasBodyStyle.height - this.sqlEditorHeight + scrollHeight}px`,
      '--exception-right': `${this.rightOptionWidth + 10}px`,
      '--exception-width': `${this.canvasBodyStyle.with}px`,
    };
  }

  get graphCategory() {
    return {
      [GraphCategory.BAR]: {
        click: () => this.handleGraphCategoryClick(GraphCategory.BAR),
        icon: '',
        images: {
          active: StyleImages.chartBarActive,
          def: StyleImages.chartBarDef,
        },
        text: this.$t('柱状图'),
      },
      [GraphCategory.LINE]: {
        click: () => this.handleGraphCategoryClick(GraphCategory.LINE),
        icon: '',
        images: {
          active: StyleImages.chartLineActive,
          def: StyleImages.chartLineDef,
        },
        text: this.$t('折线图'),
      },
      [GraphCategory.NUMBER]: {
        click: () => this.handleGraphCategoryClick(GraphCategory.NUMBER),
        icon: '',
        images: {
          active: StyleImages.chartLineBarActive,
          def: StyleImages.chartLineBarDef,
        },
        text: this.$t('数值'),
      },

      [GraphCategory.PIE]: {
        click: () => this.handleGraphCategoryClick(GraphCategory.PIE),
        icon: '',
        images: {
          active: StyleImages.chartPieActive,
          def: StyleImages.chartPieDef,
        },
        text: this.$t('饼图'),
      },

      [GraphCategory.TABLE]: {
        click: () => this.handleGraphCategoryClick(GraphCategory.TABLE),
        icon: '',
        images: {
          active: StyleImages.chartTableActive,
          def: StyleImages.chartTableDef,
        },
        text: this.$t('表格'),
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
    if (this.chartActiveType === GraphCategory.TABLE) {
      return {
        minHeight: `calc(100% - ${this.bottomHeight + 16}px)`,
      };
    }

    return {
      height: `calc(100% - ${this.bottomHeight + 16}px)`,
      minHight: '400px',
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
    const chartType =
      this.chartActiveType === GraphCategory.TABLE
        ? GraphCategory.TABLE
        : this.activeGraphCategory;
    return {
      activeGraphCategory: this.activeGraphCategory,
      category: this.activeGraphCategory,
      data: this.chartData.data,
      dimensions: this.dimensions,
      hiddenFields: this.hiddenFields,
      type: chartType,
      xFields: this.xFields,
      yFields: this.yFields,
    };
  }

  get storedChartParams() {
    return this.$store.state.indexItem.chart_params ?? {};
  }

  get extendParams() {
    return {
      chart_params: this.storedChartParams,
      favorite_type: 'chart',
      search_mode:
        SEARCH_MODE_DIC[
          this.$store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE]
        ] ?? 'ui',
    };
  }

  @Watch('storedChartParams', { deep: true, immediate: true })
  handleChartParamsChange() {
    if (this.storedChartParams) {
      setTimeout(() => {
        [
          'xFields',
          'yFields',
          'activeGraphCategory',
          'chartActiveType',
          'dimensions',
          'hiddenFields',
        ].forEach((key) => {
          const target = this.storedChartParams[key];
          if (!isEqual(target, this.chartOptions[key])) {
            if (target) {
              if (Array.isArray(target)) {
                this[key].splice(0, this[key].length, ...target);
              } else {
                this[key] = target;
              }
            }
          }
        });

        this.sqlContent = this.storedChartParams.sql;
      });
    }
  }

  handleSqlQueryError(resp) {
    Object.assign(this.errorResponse, resp);
  }

  handleEditorSearchClick() {
    (this.$refs.sqlEditor as any)?.handleQueryBtnClick();
  }

  handleSqlValueChange(value: string) {
    // 确保是有效修改这里才会触发提示
    if (this.sqlContent?.length && value.length) {
      this.isSqlValueChanged = true;
    }

    this.sqlContent = value;
  }

  // 如果是table类型，切换为table，反之，切换为图表
  handleGraphCategoryClick(category: GraphCategory) {
    if (category !== GraphCategory.TABLE) {
      this.chartActiveType = GraphCategory.CHART;
    }

    this.activeGraphCategory = category;
    this.chartCounter++;
    this.$store.commit('updateChartParams', {
      activeGraphCategory: this.activeGraphCategory,
      chartActiveType: this.chartActiveType,
    });
  }

  handleAdvanceSettingClick() {
    this.advanceSetting = !this.advanceSetting;
    this.axiosOptionHeight =
      this.axiosOptionHeight +
      (this.advanceSetting ? 1 : -1) * this.advanceHeight;
    this.minAxiosOptionHeight =
      this.minAxiosOptionHeight +
      (this.advanceSetting ? 1 : -1) * this.advanceHeight;
  }

  renderGraphCategory() {
    return this.graphCategoryList.map((category) => {
      const item = this.graphCategory[category];
      const isActive = this.activeGraphCategory === category;
      const imgHref = isActive ? item.images.active : item.images.def;
      return (
        <div
          class={{ active: isActive, 'category-item': true }}
          onClick={item.click}
        >
          <div class="category-img">
            <img src={imgHref}></img>
          </div>
          <div class="category-text">{item.text}</div>
        </div>
      );
    });
  }

  renderBasicInfo() {
    return [
      <div class="basic-info-row">
        <div class="title"> {this.$t('标题')}</div>
        <bk-input
          placeholder={this.$t('请输入标题')}
          style="margin-top: 8px;"
          v-model={this.basicInfoTitle.title}
        ></bk-input>
      </div>,
    ];
  }

  renderFieldsSetting() {
    return this.fieldList.map((field) => {
      return (
        <div class="field-setting-row" key={field}>
          <div class="field">{field}</div>
          <div class="type">指标</div>
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
        <div class="dimensions-index-row">
          <div class="label">{this.$t('过滤')}</div>
          <div class="settings"></div>
        </div>,
        <div class="dimensions-index-row">
          <div class="label">{this.$t('排序')}</div>
          <div class="settings"></div>
        </div>,
        <div class="dimensions-index-row">
          <div class="label">{this.$t('限制')}</div>
          <div class="settings white">
            <bk-input style="width: 120px;" type="number"></bk-input>
          </div>
        </div>,
      ];
    };
    if (this.isSqlMode) {
      return [
        <SqlEditor
          extendParams={this.extendParams}
          on-change={this.handleSqlQueryResultChange}
          on-error={this.handleSqlQueryError}
          onSql-change={this.handleSqlValueChange}
          ref="sqlEditor"
        ></SqlEditor>,
      ];
    }
    return [
      <div class="dimensions-index-row">
        <div class="label">{this.$t('指标')}</div>
        <TagInput></TagInput>
      </div>,
      <div class="dimensions-index-row">
        <div class="label">{this.$t('维度')}</div>
        <div class="settings"></div>
      </div>,
      <div class="dimensions-index-row">
        <div class="label"></div>
        <div class="advance-setting" onClick={this.handleAdvanceSettingClick}>
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
    this.$store.commit('updateChartParams', { chartActiveType: t });
  }

  handleHorizionMoveEnd({ offsetY }) {
    let target = this.axiosOptionHeight + (offsetY ?? 0);
    if (this.minAxiosOptionHeight > target) {
      target = this.minAxiosOptionHeight;
    }

    if (this.isSqlMode) {
      this.axiosOptionHeight = target;
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

  getChartConfigValidate() {
    let showException = false;
    const message =
      this.activeGraphCategory === GraphCategory.PIE
        ? this.$t('至少需要一个指标，一个维度')
        : this.$t('至少需要一个指标，一个维度/时间维度');
    let tips;
    const isGraphCategoryPie = this.activeGraphCategory === GraphCategory.PIE;
    const isNumber = this.activeGraphCategory === GraphCategory.NUMBER;

    if (isNumber) {
      tips = this.$t('当前缺少维度');
      return {
        message,
        showException: !this.yFields.length,
        showQuery: false,
        tips,
      };
    }

    if (
      !this.xFields.length &&
      !this.yFields.length &&
      !this.dimensions.length
    ) {
      tips = isGraphCategoryPie
        ? this.$t('当前缺少指标和维度')
        : this.$t('当前缺少指标和维度/时间维度');
    } else if (
      this.yFields.length &&
      !(this.xFields.length || this.dimensions.length)
    ) {
      tips = isGraphCategoryPie
        ? this.$t('当前缺少维度')
        : this.$t('当前缺少维度/时间维度');
    } else if (
      !this.yFields.length &&
      (this.xFields.length || this.dimensions.length)
    ) {
      tips = this.$t('当前缺少指标');
    }

    const showQuery = false;
    if (this.activeGraphCategory === GraphCategory.PIE) {
      showException = !(this.xFields.length && this.yFields.length);
      return { message, showException, showQuery, tips };
    }

    if (this.activeGraphCategory !== GraphCategory.TABLE) {
      showException = !(
        (this.dimensions.length || this.xFields.length) &&
        this.yFields.length
      );
    }

    return { message, showException, showQuery, tips };
  }

  getExceptionMessage() {
    if (this.isRequesting) {
      return {
        message: '请求中...',
        showException: true,
        showQuery: false,
        tips: '',
      };
    }

    if (!this.errorResponse.result && this.errorResponse.message) {
      return {
        message: this.errorResponse.message,
        showException: true,
        showQuery: true,
        tips: '',
      };
    }

    if (this.isSqlValueChanged) {
      return {
        message: this.$t('图表查询配置已变更'),
        showException: true,
        showQuery: true,
        tips: '',
      };
    }

    return this.getChartConfigValidate();
  }

  getExceptionRender() {
    const {
      message,
      showException,
      showQuery,
      tips = '',
    } = this.getExceptionMessage();
    if (showException) {
      return (
        <bk-exception
          class="bklog-chart-exception"
          style={this.exceptionStyle}
          type="500"
        >
          <div class="bk-exception-title">{tips}</div>
          <div class="bk-exception-title">{message}</div>
          {showQuery
            ? [
                <div class="bk-exception-description">
                  {this.$t('请重新发起查询')}
                </div>,
                <div class="bk-exception-footer">
                  <bk-button
                    class="mr10"
                    onClick={this.handleEditorSearchClick}
                    size="small"
                    theme="primary"
                    type="submit"
                  >
                    {this.$t('查询')}
                  </bk-button>
                  <bk-button
                    class="mr10"
                    onClick={() => {
                      this.isSqlValueChanged = false;
                    }}
                    size="small"
                  >
                    {this.$t('我知道了')}
                  </bk-button>
                </div>,
              ]
            : ''}
        </bk-exception>
      );
    }

    if (!this.chartOptions.data?.list?.length) {
      return (
        <bk-exception
          class="bklog-chart-exception"
          scene="part"
          style={this.exceptionStyle}
          type="empty"
        ></bk-exception>
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

  changeModel() {
    this.isSqlMode = !this.isSqlMode;
  }

  setDefaultFieldSettings(list: any[]) {
    const fieldList = list.map((item) => item.field_alias);
    // 重置字段列表
    [this.xFields, this.yFields, this.dimensions, this.hiddenFields].forEach(
      (data) => {
        const filterList = data.filter((item) => fieldList.includes(item));
        data.splice(0, data.length, ...filterList);
      }
    );

    // 重置默认字段
    if (this.xFields.length === 0 && this.dimensions.length === 0) {
      const defValue = (
        list.find((item) => /date|time/.test(item.field_alias)) ?? list[0]
      )?.field_alias;
      if (defValue) {
        this.xFields.push(defValue);
      }
    }

    if (this.yFields.length === 0) {
      const filterList = list.filter(
        (item) =>
          !/date|time/.test(item.field_alias) &&
          !this.xFields.includes(item.field_alias) &&
          !this.dimensions.includes(item.field_alias)
      );

      const defValue = filterList?.find(
        (item) =>
          /long|number|int|float|bigint|double/.test(item.field_type) &&
          !this.xFields.includes(item.field_alias)
      )?.field_alias;

      if (defValue) {
        this.yFields.push(defValue);
      }
    }
  }

  handleSqlQueryResultChange(resp, isRequesting) {
    // 如果data为空，这里只处理请求状态
    if (!resp) {
      this.isRequesting = isRequesting;
      return;
    }

    this.resultSchema = resp.data?.result_schema ?? [];
    this.setDefaultFieldSettings(this.resultSchema);
    this.chartData = resp;
    this.$set(this, 'chartData', resp);
    this.chartCounter++;
    this.isSqlValueChanged = false;
  }

  updateChartData(axis, newValue) {
    this[axis] = (Array.isArray(newValue) ? newValue : [newValue]).filter(
      (t) => !!t
    );
    this.chartCounter++;

    this.$store.commit('updateChartParams', { [axis]: this[axis] });
  }

  createResizeObserve() {
    const cellElement = this.$refs.refGraphAnalysisBodyLeft;

    if (isElement(cellElement)) {
      // 创建一个 ResizeObserver 实例
      this.resizeObserver = new ResizeObserver((entries) => {
        for (let entry of entries) {
          // 获取元素的新高度
          this.debounceCallback(entry);
        }
      });

      this.resizeObserver?.observe(cellElement);
    }
  }

  destoyResizeObserve() {
    const cellElement = this.$refs.refGraphAnalysisBodyLeft;

    if (isElement(cellElement)) {
      this.resizeObserver?.unobserve(cellElement);
      this.resizeObserver?.disconnect();
      this.resizeObserver = null;
    }
  }

  mounted() {
    this.createResizeObserve();
    (this.$refs.refGraphAnalysisBodyLeft as HTMLElement).addEventListener(
      'scroll',
      this.throttleScrollCallback
    );
  }

  unmount() {
    this.destoyResizeObserve();
    (this.$refs.refGraphAnalysisBodyLeft as HTMLElement).removeEventListener(
      'scroll',
      this.throttleScrollCallback
    );
  }

  render() {
    return (
      <div class="graph-analysis-index">
        <div class="graph-analysis-navi" style="display: none;"></div>

        <div class="graph-analysis-body">
          <div class="body-left" ref="refGraphAnalysisBodyLeft">
            <div
              class={['graph-axios-options', this.isSqlMode ? 'sql-mode' : '']}
              style={this.axiosStyle}
            >
              <div class="graph-axios-rows">
                {this.renderDimensionsAndIndexSetting()}
              </div>
              <div class="graph-axios-drag">
                <GraphDragTool
                  class="horizional-drag-tool"
                  direction="horizional"
                  onMove-end={this.handleHorizionMoveEnd}
                ></GraphDragTool>
              </div>
            </div>
            <div class="graph-canvas-line"></div>
            <div
              class="graph-canvas-options"
              ref="refCanvasBody"
              style={this.canvasStyle}
            >
              <div class="canvas-head">
                {this.basicInfoTitle.title ? (
                  <span class="title">{this.basicInfoTitle.title}</span>
                ) : (
                  ''
                )}
                <span
                  class="icons"
                  v-show={this.activeGraphCategory !== GraphCategory.TABLE}
                >
                  <span
                    class={{
                      active: this.chartActiveType !== GraphCategory.TABLE,
                    }}
                    onClick={() =>
                      this.handleCanvasTypeChange(GraphCategory.CHART)
                    }
                  >
                    <i class="bklog-icon bklog-bar"></i>
                  </span>
                  <span
                    class={{
                      active: this.chartActiveType === GraphCategory.TABLE,
                    }}
                    onClick={() =>
                      this.handleCanvasTypeChange(GraphCategory.TABLE)
                    }
                  >
                    <i class="bklog-icon bklog-table"></i>
                  </span>
                </span>
              </div>
              {this.renderCanvasChartAndTable()}
              {this.getExceptionRender()}
            </div>
          </div>
          <div class="body-right" style={this.rightOptionStyle}>
            <div class="graph-category">
              <div class="category-title">{this.$t('图表样式')}</div>
              <div class="category-list">{this.renderGraphCategory()}</div>
            </div>
            <div class="graph-info">
              <GraphDragTool
                class="vertical-drag-tool"
                direction="vertical"
                onMove-end={this.handleVerticalMoveEnd}
              ></GraphDragTool>
              <bk-collapse
                class="graph-info-collapse"
                v-model={this.activeSettings}
              >
                <bk-collapse-item name="field_setting">
                  <span class="graph-info-collapse-title">
                    {this.$t('字段设置')}
                  </span>
                  <FieldSettings
                    on-update={this.updateChartData}
                    options={this.chartOptions}
                    result_schema={this.resultSchema}
                    slot="content"
                  ></FieldSettings>
                </bk-collapse-item>
              </bk-collapse>
            </div>
          </div>
        </div>

        <DashboardDialog ref="addDialog"></DashboardDialog>
      </div>
    );
  }
}
