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

import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from '@/store/store.type.ts';
import { isElement, debounce, throttle, isEqual } from 'lodash-es';

import SqlPanel from './SqlPanel.vue';
import GraphChart from './chart/index.tsx';
import FieldSettings from './common/field-settings.vue';
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
  NUMBER = 'number',
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
  axiosOptionHeight = 400;
  rightOptionWidth = 360;
  minRightOptionWidth = 360;
  activeGraphCategory = GraphCategory.TABLE;
  chartActiveType = GraphCategory.TABLE;
  xFields = [];
  yFields = [];
  chartData: { data?: any; list?: any[]; result_schema?: any[]; select_fields_order?: string[] } = {};
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
    with: 300,
    height: 400,
    scrollTop: 0,
  };

  debounceCallback = debounce(entry => {
    const { offsetWidth, offsetHeight } = entry.target;
    Object.assign(this.canvasBodyStyle, { with: offsetWidth, height: offsetHeight });
  }, 120);

  throttleScrollCallback = throttle(event => {
    Object.assign(this.canvasBodyStyle, { scrollTop: (event.target as HTMLElement).scrollTop });
  });

  resizeObserver = null;
  isRequesting = false;

  get exceptionStyle() {
    const scrollHeight =
      this.canvasBodyStyle.scrollTop < this.sqlEditorHeight ? this.canvasBodyStyle.scrollTop : this.sqlEditorHeight;

    return {
      '--exception-width': `${this.canvasBodyStyle.with}px`,
      '--exception-height': `${this.canvasBodyStyle.height - this.sqlEditorHeight + scrollHeight}px`,
      '--exception-right': `${this.rightOptionWidth + 10}px`,
    };
  }

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

      [GraphCategory.NUMBER]: {
        icon: '',
        text: this.$t('数值'),
        click: () => this.handleGraphCategoryClick(GraphCategory.NUMBER),
        images: {
          def: StyleImages.chartLineBarDef,
          active: StyleImages.chartLineBarActive,
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
    const chartType = this.chartActiveType === GraphCategory.TABLE ? GraphCategory.TABLE : this.activeGraphCategory;
    return {
      xFields: this.xFields,
      yFields: this.yFields,
      type: chartType,
      dimensions: this.dimensions,
      data: this.chartData.data,
      category: this.activeGraphCategory,
      activeGraphCategory: this.activeGraphCategory,
      hiddenFields: this.hiddenFields,
    };
  }

  get storedChartParams() {
    return this.$store.state.indexItem.chart_params ?? {};
  }

  get extendParams() {
    return {
      favorite_type: 'chart',
      chart_params: this.storedChartParams,
      search_mode: SEARCH_MODE_DIC[this.$store.state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui',
    };
  }

  @Watch('storedChartParams', { deep: true, immediate: true })
  handleChartParamsChange() {
    if (this.storedChartParams) {
      setTimeout(() => {
        const paramKeys = [
          'xFields',
          'yFields',
          'activeGraphCategory',
          'chartActiveType',
          'dimensions',
          'hiddenFields',
        ];
        for (const key of paramKeys) {
          const target = this.storedChartParams[key];
          if (!isEqual(target, this.chartOptions[key]) && target) {
            if (Array.isArray(target)) {
              this[key].splice(0, this[key].length, ...target);
            } else {
              this[key] = target;
            }
          }
        }

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
    this.axiosOptionHeight += (this.advanceSetting ? 1 : -1) * this.advanceHeight;
    this.minAxiosOptionHeight += (this.advanceSetting ? 1 : -1) * this.advanceHeight;
  }

  renderGraphCategory() {
    return this.graphCategoryList.map(category => {
      const item = this.graphCategory[category];
      const isActive = this.activeGraphCategory === category;
      const imgHref = isActive ? item.images.active : item.images.def;
      return (
        <div
          key={category}
          class={{ 'category-item': true, active: isActive }}
          onClick={item.click}
        >
          <div class='category-img'>
            {/** biome-ignore lint/performance/noImgElement: reason */}
            {/** biome-ignore lint/nursery/useImageSize: reason */}
            {/** biome-ignore lint/a11y/useAltText: reason */}
            <img src={imgHref} />
          </div>
          <div class='category-text'>{item.text}</div>
        </div>
      );
    });
  }

  renderBasicInfo() {
    return [
      <div
        key='info-row'
        class='basic-info-row'
      >
        <div class='title'> {this.$t('标题')}</div>
        <bk-input
          style='margin-top: 8px;'
          v-model={this.basicInfoTitle.title}
          placeholder={this.$t('请输入标题')}
        />
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
        <div
          key='row-filter'
          class='dimensions-index-row'
        >
          <div class='label'>{this.$t('过滤')}</div>
          <div class='settings' />
        </div>,
        <div
          key='row-sort'
          class='dimensions-index-row'
        >
          <div class='label'>{this.$t('排序')}</div>
          <div class='settings' />
        </div>,
        <div
          key='row-limit'
          class='dimensions-index-row'
        >
          <div class='label'>{this.$t('限制')}</div>
          <div class='settings white'>
            <bk-input
              style='width: 120px;'
              type='number'
            />
          </div>
        </div>,
      ];
    };
    if (this.isSqlMode) {
      return [
        <SqlEditor
          key='row-sql-editor'
          ref='sqlEditor'
          extendParams={this.extendParams}
          on-change={this.handleSqlQueryResultChange}
          on-error={this.handleSqlQueryError}
          onSql-change={this.handleSqlValueChange}
        />,
      ];
    }
    return [
      <div
        key='row-fields'
        class='dimensions-index-row'
      >
        <div class='label'>{this.$t('指标')}</div>
        <TagInput />
      </div>,
      <div
        key='row-dimensions'
        class='dimensions-index-row'
      >
        <div class='label'>{this.$t('维度')}</div>
        <div class='settings' />
      </div>,
      <div
        key='row-advance-setting'
        class='dimensions-index-row'
      >
        <div class='label' />
        <div
          class='advance-setting'
          onClick={this.handleAdvanceSettingClick}
        >
          {this.$t('高级设置')}
          <i class={['log-icon', this.advanceSettingClass]} />
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

  // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
  getChartConfigValidate() {
    let showException = false;
    const message =
      this.activeGraphCategory === GraphCategory.PIE
        ? this.$t('至少需要一个指标，一个维度')
        : this.$t('至少需要一个指标，一个维度/时间维度');
    let tips: any;
    const isGraphCategoryPie = this.activeGraphCategory === GraphCategory.PIE;
    const isNumber = this.activeGraphCategory === GraphCategory.NUMBER;

    if (isNumber) {
      tips = this.$t('当前缺少维度');
      return { showException: !this.yFields.length, message, showQuery: false, tips };
    }

    if (!(this.xFields.length || this.yFields.length || this.dimensions.length)) {
      tips = isGraphCategoryPie ? this.$t('当前缺少指标和维度') : this.$t('当前缺少指标和维度/时间维度');
    } else if (this.yFields.length && !(this.xFields.length || this.dimensions.length)) {
      tips = isGraphCategoryPie ? this.$t('当前缺少维度') : this.$t('当前缺少维度/时间维度');
    } else if (!this.yFields.length && (this.xFields.length || this.dimensions.length)) {
      tips = this.$t('当前缺少指标');
    }

    const showQuery = false;
    if (this.activeGraphCategory === GraphCategory.PIE) {
      showException = !(this.xFields.length && this.yFields.length);
      return { showException, message, showQuery, tips };
    }

    if (this.activeGraphCategory !== GraphCategory.TABLE) {
      showException = !((this.dimensions.length || this.xFields.length) && this.yFields.length);
    }

    return { showException, message, showQuery, tips };
  }

  getExceptionMessage() {
    if (this.isRequesting) {
      return { showException: true, message: '请求中...', showQuery: false, tips: '' };
    }

    if (!this.errorResponse.result && this.errorResponse.message) {
      return { showException: true, message: this.errorResponse.message, showQuery: true, tips: '' };
    }

    if (this.isSqlValueChanged) {
      return { showException: true, message: this.$t('图表查询配置已变更'), showQuery: true, tips: '' };
    }

    return this.getChartConfigValidate();
  }

  getExceptionRender() {
    const { showException, message, showQuery, tips = '' } = this.getExceptionMessage();
    if (showException) {
      return (
        <bk-exception
          style={this.exceptionStyle}
          class='bklog-chart-exception'
          type='500'
        >
          <div class='bk-exception-title'>{tips}</div>
          <div class='bk-exception-title'>{message}</div>
          {showQuery
            ? [
                <div
                  key='description'
                  class='bk-exception-description'
                >
                  {this.$t('请重新发起查询')}
                </div>,
                <div
                  key='footer'
                  class='bk-exception-footer'
                >
                  <bk-button
                    class='mr10'
                    size='small'
                    theme='primary'
                    type='submit'
                    onClick={this.handleEditorSearchClick}
                  >
                    {this.$t('查询')}
                  </bk-button>
                  <bk-button
                    class='mr10'
                    size='small'
                    onClick={() => {
                      this.isSqlValueChanged = false;
                    }}
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
          style={this.exceptionStyle}
          class='bklog-chart-exception'
          scene='part'
          type='empty'
        />
      );
    }

    return '';
  }

  renderCanvasChartAndTable() {
    return (
      <GraphChart
        chartCounter={this.chartCounter}
        chartOptions={this.chartOptions}
      />
    );
  }

  changeModel() {
    this.isSqlMode = !this.isSqlMode;
  }

  setDefaultFieldSettings(list: any[]) {
    const fieldList = list.map(item => item.field_alias);
    // 重置字段列表
    const fieldsArr = [this.xFields, this.yFields, this.dimensions, this.hiddenFields];
    for (const data of fieldsArr) {
      const filterList = data.filter(item => fieldList.includes(item));
      data.splice(0, data.length, ...filterList);
    }

    // 重置默认字段
    if (this.xFields.length === 0 && this.dimensions.length === 0) {
      const defValue = (list.find(item => /date|time/.test(item.field_alias)) ?? list[0])?.field_alias;
      if (defValue) {
        this.xFields.push(defValue);
      }
    }

    if (this.yFields.length === 0) {
      const filterList = list.filter(
        item =>
          !(
            /date|time/.test(item.field_alias) ||
            this.xFields.includes(item.field_alias) ||
            this.dimensions.includes(item.field_alias)
          ),
      );

      const defValue = filterList?.find(
        item => /long|number|int|float|bigint|double/.test(item.field_type) && !this.xFields.includes(item.field_alias),
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
    this[axis] = (Array.isArray(newValue) ? newValue : [newValue]).filter(t => !!t);
    this.chartCounter++;

    this.$store.commit('updateChartParams', { [axis]: this[axis] });
  }

  createResizeObserve() {
    const cellElement = this.$refs.refGraphAnalysisBodyLeft;

    if (isElement(cellElement)) {
      // 创建一个 ResizeObserver 实例
      this.resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
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
    (this.$refs.refGraphAnalysisBodyLeft as HTMLElement).addEventListener('scroll', this.throttleScrollCallback);
  }

  unmount() {
    this.destoyResizeObserve();
    (this.$refs.refGraphAnalysisBodyLeft as HTMLElement).removeEventListener('scroll', this.throttleScrollCallback);
  }

  render() {
    return (
      <div class='graph-analysis-index'>
        <div
          style='display: none;'
          class='graph-analysis-navi'
        />

        <div class='graph-analysis-body'>
          <div
            ref='refGraphAnalysisBodyLeft'
            class='body-left'
          >
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
                />
              </div>
            </div>
            <div class='graph-canvas-line' />
            <div
              ref='refCanvasBody'
              style={this.canvasStyle}
              class='graph-canvas-options'
            >
              <div class='canvas-head'>
                {this.basicInfoTitle.title ? <span class='title'>{this.basicInfoTitle.title}</span> : ''}
                <span
                  class='icons'
                  v-show={this.activeGraphCategory !== GraphCategory.TABLE}
                >
                  <span
                    class={{ active: this.chartActiveType !== GraphCategory.TABLE }}
                    onClick={() => this.handleCanvasTypeChange(GraphCategory.CHART)}
                  >
                    <i class='bklog-icon bklog-bar' />
                  </span>
                  <span
                    class={{ active: this.chartActiveType === GraphCategory.TABLE }}
                    onClick={() => this.handleCanvasTypeChange(GraphCategory.TABLE)}
                  >
                    <i class='bklog-icon bklog-table' />
                  </span>
                </span>
              </div>
              {this.renderCanvasChartAndTable()}
              {this.getExceptionRender()}
            </div>
          </div>
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
              />
              <bk-collapse
                class='graph-info-collapse'
                v-model={this.activeSettings}
              >
                <bk-collapse-item name='field_setting'>
                  <span class='graph-info-collapse-title'>{this.$t('字段设置')}</span>
                  <FieldSettings
                    slot='content'
                    options={this.chartOptions}
                    result_schema={this.resultSchema}
                    on-update={this.updateChartData}
                  />
                </bk-collapse-item>
              </bk-collapse>
            </div>
          </div>
        </div>

        <DashboardDialog ref='addDialog' />
      </div>
    );
  }
}
