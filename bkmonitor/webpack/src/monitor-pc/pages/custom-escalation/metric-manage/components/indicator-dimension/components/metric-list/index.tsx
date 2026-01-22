/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Emit, Watch, Prop, Ref, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SearchSelect from '@blueking/search-select-v3/vue2';
import dayjs from 'dayjs';
import { Debounce } from 'monitor-common/utils';

import EmptyStatus from '../../../../../../../components/empty-status/empty-status';
import type { EmptyStatusType } from '../../../../../../../components/empty-status/types';
import TableSkeleton from '../../../../../../../components/skeleton/table-skeleton';
import { METHOD_LIST } from '../../../../../../../constant/constant';
import ColumnCheck from '../../../../../../performance/column-check/column-check.vue';
import { matchRuleFn } from '../../../../utils';
import type { ICustomTsFields, IUnitItem } from '../../../../../service';
import { DEFAULT_HEIGHT_OFFSET, type IGroupListItem, NULL_LABEL, type RequestHandlerMap } from '../../../../type';
import BatchEdit from './components/batch-edit';
import MetricDetail from './components/metric-detail';
import type { IMetricGroupMapItem } from '../../index';

import './index.scss';
import '@blueking/search-select-v3/vue2/vue2.css';

export type IMetricItem = ICustomTsFields['metrics'][number] & { selection: boolean; isNew?: boolean; error?: string };

interface IProps {
  /** 当前选中的分组信息 */
  selectedGroupInfo: { id: number; name: string };
  /** 指标表格数据列表 */
  metricTable: IMetricItem[];
  /** 单位列表 */
  unitList: IUnitItem[];
  /** 分组选择列表 */
  groupSelectList: { id: number; name: string }[];
  /** 维度表格数据 */
  dimensionTable: ICustomTsFields['dimensions'];
  /** 表格加载状态 */
  loading: boolean;
  /** 所有数据预览 */
  // allDataPreview: Record<string, any>;
  /** 分组映射表，key为分组名称，value为分组信息 */
  groupsMap: Map<string, IGroupListItem>;
  /** 全选状态值：0-未选，1-部分选中，2-全选 */
  allCheckValue: number;
  /** 默认分组信息 */
  defaultGroupInfo: { id: number; name: string };
  /** 指标分组映射表 */
  metricGroupsMap: Map<string, IMetricGroupMapItem>;
}

interface IEmits {
  onShowAddGroup: () => void;
  onHandleBatchAddGroup: (groupName: string, metricList: { field_id: number; metric_name: string }[]) => void;
  onRefresh: () => void;
  onSwitcherChange: (v: boolean) => void;
  onRowCheck: () => void;
  onUpdateAllSelection: (v: boolean) => void;
  onSearchChange: (list: any[]) => void;
  onAliasChange: () => void;
}

@Component
export default class MetricList extends tsc<IProps, IEmits> {
  @Prop({ default: () => {} }) selectedGroupInfo: IProps['selectedGroupInfo'];
  @Prop({ default: () => [] }) metricTable: IProps['metricTable'];
  @Prop({ default: () => [] }) unitList: IProps['unitList'];
  @Prop({ default: () => [] }) groupSelectList: IProps['groupSelectList'];
  @Prop({ default: () => [] }) dimensionTable: IProps['dimensionTable'];
  @Prop({ default: false }) loading: IProps['loading'];
  // @Prop({ default: () => {} }) allDataPreview: IProps['allDataPreview'];
  @Prop({ default: 0 }) allCheckValue: IProps['allCheckValue'];
  @Prop({ default: () => {} }) defaultGroupInfo: IProps['defaultGroupInfo'];
  @Prop({ default: () => new Map() }) groupsMap: IProps['groupsMap'];
  @Prop({ default: () => new Map() }) metricGroupsMap: IProps['metricGroupsMap'];

  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  /** 批量添加分组弹窗引用 */
  @Ref() readonly batchAddGroupPopover!: HTMLInputElement;
  /** 指标表格头部引用，用于监听尺寸变化 */
  @Ref() readonly metricTableHeader!: HTMLInputElement;
  /** 指标详情引用 */
  @Ref() readonly metricDetailRef!: HTMLInputElement;
  /** 表格盒子引用 */
  @Ref() readonly tableBoxRef!: HTMLInputElement;

  /** 表格数据配置 */
  table = {
    data: [],
    select: [],
  };

  /** 别名编辑时的备份值，用于判断是否有修改 */
  copyAlias = '';
  /** 是否显示确认关闭对话框 */
  isShowDialog = false;

  /** 字段设置数据，控制表格列的显示/隐藏 */
  fieldSettingData: any = {};
  /** 是否显示指标详情侧边栏 */
  showDetail = false;
  /** 当前激活的详情索引 */
  detailActiveIndex = -1;
  /** 表格分页实例配置 */
  tableInstance = {
    data: [],
    page: 1,
    pageSize: 10,
    total: 0,
    pageList: [10, 20, 50, 100],
  };

  /** 批量操作头部配置 */
  header = {
    value: 0,
    dropdownShow: false,
    list: [{ id: 0, name: this.$t('移动至分组') }],
  };
  /** 当前正在编辑的行索引，-1表示未编辑 */
  editingIndex = -1;

  /** 空状态类型 */
  emptyType = 'empty' as EmptyStatusType;
  /** 分组列宽度 */
  groupWidth = 200;
  /** ResizeObserver实例，用于监听元素尺寸变化 */
  resizeObserver = null;
  /** 表格头部高度 */
  rectHeight = 32;
  /** 表格搜索条件列表 */
  search = [];
  /** 是否显示批量编辑侧边栏 */
  isShowMetricSlider = false;
  /** 表格盒子高度 */
  tableBoxHeight = window.innerHeight;

  /** 计算详情侧边栏宽度，根据屏幕宽度自适应 */
  get computedWidth() {
    return window.innerWidth < 1920 ? 388 : 456;
  }

  /** 计算表格高度，基于头部高度和默认偏移量 */
  get computedHeight() {
    return this.rectHeight + DEFAULT_HEIGHT_OFFSET;
  }

  /** 获取当前选中项的数量 */
  get selectionLength() {
    const selectionList = this.metricTableVal.filter(item => item.selection);
    return selectionList.length;
  }

  /** 获取当前页的指标表格数据，包含分页逻辑 */
  get metricTableVal() {
    this.tableInstance.total = this.metricTable.length;
    return this.metricTable.slice(
      this.tableInstance.pageSize * (this.tableInstance.page - 1),
      this.tableInstance.pageSize * this.tableInstance.page
    );
  }

  /** 获取当前激活的指标详情数据 */
  get metricData() {
    return this.metricTableVal[this.detailActiveIndex] || ({} as IMetricItem);
  }

  /** 获取搜索选择器的配置数据 */
  get metricSearchData() {
    return [
      {
        name: this.$t('名称'),
        id: 'name',
        multiple: false,
        children: [],
      },
      {
        name: this.$t('别名'),
        id: 'alias',
        multiple: false,
        children: [],
      },
      {
        name: this.$t('单位'),
        id: 'unit',
        multiple: false,
        children: this.unitList,
      },
      {
        name: this.$t('汇聚方法'),
        id: 'aggregate',
        multiple: false,
        children: METHOD_LIST,
      },
      {
        name: this.$t('显/隐'),
        id: 'show',
        multiple: false,
        children: [
          { id: 'true', name: this.$t('显示') },
          { id: 'false', name: this.$t('隐藏') },
        ],
      },
    ];
  }

  /** 获取所有分组名称列表 */
  get groupNames() {
    return Array.from(this.groupsMap.keys()).filter(item => !!item);
  }

  @Watch('selectedGroupInfo', { immediate: true })
  handleSelectedGroupInfoChange() {
    this.tableInstance.page = 1;
    this.search = [];
  }

  /** 监听指标数据变化，当数据为空时关闭详情面板 */
  @Watch('metricData', { immediate: true, deep: true })
  handleMetricDataChange() {
    if (!this.metricData?.name) {
      this.showDetail = false;
    }
  }

  @Watch('search', { immediate: true, deep: true })
  handleSearchValueChange() {
    this.emptyType = this.search.length ? 'search-empty' : 'empty';
  }

  /** 组件创建时初始化字段设置数据和表格数据 */
  created() {
    this.fieldSettingData = {
      name: {
        checked: true,
        disable: false,
        name: this.$t('名称'),
        id: 'name',
      },
      alias: {
        checked: true,
        disable: false,
        name: this.$t('别名'),
        id: 'alias',
      },
      group: {
        checked: true,
        disable: false,
        name: this.$t('分组'),
        id: 'scope_name',
      },
      status: {
        checked: false, // TODO: 暂不支持配置
        disable: false,
        name: this.$t('状态'),
        id: 'status',
      },
      unit: {
        checked: true,
        disable: false,
        name: this.$t('单位'),
        id: 'unit',
      },
      aggregateMethod: {
        checked: true,
        disable: false,
        name: this.$t('汇聚方法'),
        id: 'aggregateMethod',
      },
      interval: {
        checked: true,
        disable: false,
        name: this.$t('上报周期'),
        id: 'interval',
      },
      function: {
        checked: true,
        disable: false,
        name: this.$t('函数'),
        id: 'function',
      },
      hidden: {
        checked: true,
        disable: false,
        name: this.$t('显示'),
        id: 'hidden',
      },
      enabled: {
        checked: true,
        disable: false,
        name: this.$t('启/停'),
        id: 'enabled',
      },
      set: {
        checked: true,
        disable: false,
        name: this.$t('操作'),
        id: 'set',
      },
    };
    this.table.data = this.metricTableVal;
  }

  /**
   * 获取展示时间
   * @param timeStr 时间戳（秒）
   * @returns 格式化后的时间字符串
   */
  getShowTime(timeStr: number) {
    if (!timeStr) return '-';
    const timestamp = new Date(timeStr * 1000);
    return dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss');
  }

  /**
   * 显示指标详情侧边栏
   * @param props 表格行属性对象，包含$index等
   */
  showMetricDetail(props) {
    this.detailActiveIndex = props.$index;
    this.showDetail = true;
    setTimeout(() => {
      this.tableBoxHeight = this.tableBoxRef.scrollHeight + 63;
    });
  }

  /**
   * 处理分组选择切换
   * @param id 选中的分组ID
   * @param row 当前指标行数据
   */
  handleGroupSelectToggle(id: number, row: IMetricItem) {
    const name = this.groupSelectList.find(item => item.id === id)?.name;
    if (name === row.scope.name) {
      return;
    }
    let infoObj = {
      id,
      name,
    };
    if (!id) {
      // 未分组
      infoObj = this.defaultGroupInfo;
    }
    this.updateCustomFields('scope', infoObj, row, true);
  }

  /**
   * 判断指标是否由匹配规则生成，如果是则禁用选择
   * @param metricName 指标名称
   * @param key 分组ID
   * @returns 是否禁用
   */
  getIsDisable(metricName, key) {
    if (!metricName) {
      return false;
    }
    return this.groupsMap.get(key)?.matchRulesOfMetrics?.includes?.(metricName) || false;
  }
  /**
   * 获取由匹配规则生成的提示信息
   * @param metricName 指标名称
   * @param groupName 分组名称
   * @returns 匹配规则字符串
   */
  getDisableTip(metricName, groupName) {
    const targetGroup = this.groupsMap.get(groupName);
    let targetRule = '';
    targetGroup?.matchRules?.forEach(rule => {
      if (!targetRule) {
        if (matchRuleFn(metricName, rule)) {
          targetRule = rule;
        }
      }
    });
    return targetRule;
  }

  /** 显示分组管理弹窗 */
  @Emit('showAddGroup')
  handleShowGroupManage(): boolean {
    return true;
  }

  /**
   * 渲染状态点组件
   * @param color1 内层颜色
   * @param color2 外层颜色
   * @returns JSX元素
   */
  statusPoint(color1: string, color2: string) {
    return (
      <div
        style={{ background: color2 }}
        class='status-point'
      >
        <div
          style={{ background: color1 }}
          class='point'
        />
      </div>
    );
  }

  /** 渲染表格选择列头部，包含全选/部分选中/未选状态 */
  renderSelectionHeader() {
    return (
      <ColumnCheck
        {...{
          props: {
            list: this.metricTableVal,
            value: this.allCheckValue,
            defaultType: 'current',
          },
          on: {
            change: this.handleCheckChange,
          },
        }}
      />
    );
  }

  handleEmptyOperation(type: string) {
    if (type === 'clear-filter') {
      this.handleSearchChange([]);
    }
  }

  /** 获取表格组件，包含所有列的定义和插槽 */
  getTableComponent() {
    /* 名称 */
    const nameSlot = {
      default: props => (
        <div
          class='name'
          v-bk-overflow-tips
          onClick={(e: MouseEvent) => {
            e.stopPropagation();
            this.showMetricDetail(props);
          }}
        >
          {props.row.name || '--'}
        </div>
      ),
    };
    /* 别名 */
    const aliasSlot = {
      default: props => (
        <div
          class='description-content'
          onClick={() => this.handleDescFocus(props)}
        >
          <bk-input
            ext-cls='description-input'
            readonly={this.editingIndex !== props.$index}
            value={props.row.config.alias}
            show-overflow-tooltips
            onBlur={() => {
              this.editingIndex = -1;
              this.handleEditDescription(props.row);
            }}
            onEnter={() => {
              this.handleEditDescription(props.row);
            }}
            onChange={v => {
              this.copyAlias = v;
            }}
          />
        </div>
      ),
    };
    /* 分组 */
    const groupSlot = {
      default: ({ row, $index }) => (
        <div
          key={this.groupWidth}
          style={`width: ${this.groupWidth - 20}px;`}
          class='table-group-box'
        >
          {this.getGroupCpm(row, $index)}
        </div>
      ),
    };

    const hiddenSlot = {
      default: props => (
        <bk-switcher
          class='switcher-btn'
          size='small'
          theme='primary'
          value={!props.row.config.hidden}
          onChange={v => this.handleEditHidden(v, props.row)}
        />
      ),
    };

    const { name, group, alias, hidden } = this.fieldSettingData;
    return (
      <div
        class='indicator-table'
        ref='tableBoxRef'
      >
        <bk-table
          v-bkloading={{ isLoading: this.loading }}
          empty-text={this.$t('无数据')}
          max-height={this.isAPM ? window.innerHeight - 220 : window.innerHeight - 610}
          on-header-dragend={(newWidth, _, col) => {
            if (col.property === 'group') {
              this.groupWidth = newWidth;
            }
          }}
          on-selection-change={this.handleCheckChange}
          {...{
            props: {
              data: this.metricTableVal,
            },
          }}
        >
          <div slot='empty'>
            <EmptyStatus
              type={this.emptyType}
              onOperation={this.handleEmptyOperation}
            />
          </div>
          <bk-table-column
            scopedSlots={{
              default: ({ row }) => (
                <bk-checkbox
                  v-bk-tooltips={{ content: this.$t('该指标已预设分组，暂不支持页面修改。'), disabled: row.movable }}
                  v-model={row.selection}
                  disabled={!row.movable}
                  onChange={this.handleRowCheck}
                />
              ),
            }}
            align='center'
            fixed='left'
            renderHeader={this.renderSelectionHeader}
            type='selection'
          />
          {name.checked && (
            <bk-table-column
              key='name'
              label={this.$t('名称')}
              minWidth='150'
              fixed='left'
              prop='name'
              scopedSlots={nameSlot}
            />
          )}
          {alias.checked && (
            <bk-table-column
              key='alias'
              label={this.$t('别名')}
              minWidth='200'
              prop='config.alias'
              scopedSlots={aliasSlot}
            />
          )}
          {group.checked && (
            <bk-table-column
              key='scope'
              width='200'
              label={this.$t('分组')}
              prop='scope.name'
              scopedSlots={groupSlot}
            />
          )}
          {/* {status.checked && (
            <bk-table-column
              key='status'
              label={this.$t('状态')}
              minWidth='125'
              prop='status'
              scopedSlots={statusSlot}
            />
          )} */}
          {hidden.checked && (
            <bk-table-column
              key='hidden'
              renderHeader={() => (
                <div>
                  <span>{this.$t('显示')}</span>
                  <bk-popover ext-cls='render-header-hidden-popover'>
                    <bk-icon type='info-circle' />
                    <div slot='content'>{this.$t('关闭后，在可视化视图里，将被隐藏')}</div>
                  </bk-popover>
                </div>
              )}
              label={this.$t('显示')}
              minWidth='75'
              prop='hidden'
              scopedSlots={hiddenSlot}
            />
          )}
        </bk-table>
      </div>
    );
  }

  /**
   * 批量添加选中指标至指定分组
   * @param groupName 分组名称
   */
  handleBatchAdd(groupName) {
    this.batchAddGroupPopover?.hideHandler?.();
    if (!groupName) {
      return;
    }
    this.$emit(
      'handleBatchAddGroup',
      groupName,
      this.metricTableVal
        .filter(item => item.selection)
        .map(metric => ({
          field_id: metric.id,
          metric_name: metric.name,
        }))
    );
  }

  /** 切换开关状态变化事件 */
  @Emit('switcherChange')
  switcherChange(v: boolean) {
    this.isShowDialog = false;
    return v;
  }
  /**
   * 处理分页页码变化
   * @param v 新的页码
   */
  handlePageChange(v: number) {
    this.updateAllSelection();
    this.tableInstance.page = v;
  }

  /**
   * 处理每页条数变化
   * @param v 新的每页条数
   */
  handleLimitChange(v: number) {
    this.tableInstance.page = 1;
    this.tableInstance.pageSize = v;
    this.updateAllSelection();
  }

  /** 行选择变化事件 */
  @Emit('rowCheck')
  handleRowCheck() {}

  /**
   * 处理全选/取消全选变化
   * @param value 选择状态：0-未选，1-部分选中，2-全选
   */
  handleCheckChange({ value }) {
    this.updateAllSelection(value === 2);
  }

  /**
   * 更新全选状态
   * @param v 是否全选
   */
  @Emit('updateAllSelection')
  updateAllSelection(v = false) {
    return v;
  }

  /**
   * 处理搜索条件变化
   * @param list 搜索条件列表
   */
  @Emit('searchChange')
  handleSearchChange(list) {
    this.search = list;
    return list;
  }

  /** 点击管理按钮，显示批量编辑侧边栏 */
  handleClickSlider() {
    this.isShowMetricSlider = true;
  }

  /**
   * 更新自定义字段
   * @param k 字段键名，如'alias'、'hidden'、'scope'等
   * @param v 字段值
   * @param metricInfo 指标信息对象
   * @param showMsg 是否显示成功提示消息
   */
  async updateCustomFields(k: string, v: any, metricInfo: IMetricItem, showMsg = false) {
    try {
      const isConfigKey = ['alias', 'hidden'].includes(k);
      const updateField = {
        type: 'metric',
        name: metricInfo.name,
        id: metricInfo.id,
        scope: metricInfo.scope,
        config: metricInfo.config,
      };
      if (!isConfigKey) {
        updateField[k] = v;
      }
      const params = {
        time_series_group_id: this.timeSeriesGroupId,
        update_fields: [updateField],
      };
      if (this.isAPM) {
        delete params.time_series_group_id;
        Object.assign(params, {
          app_name: this.appName,
          service_name: this.serviceName,
        });
      }
      await this.requestHandlerMap.modifyCustomTsFields(params);
      if (showMsg) {
        this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      }
      // 仅在更新分组后才刷新外部数据
      if (!isConfigKey) {
        this.$emit('refresh');
      }
    } catch (error) {
      console.error('Update metric failed:', error);
    }
  }

  /**
   * 编辑指标别名
   * @param metricInfo 指标信息对象
   */
  async handleEditDescription(metricInfo) {
    if (this.copyAlias === metricInfo.config.alias) {
      this.copyAlias = '';
      return;
    }
    const currentAlias = this.copyAlias; // 防止编辑时点击其他input后触发blur 导致copyAlias变化赋值错误
    metricInfo.config.alias = currentAlias;
    await this.updateCustomFields('alias', currentAlias, metricInfo, true);
    this.$emit('aliasChange');
  }

  /**
   * 处理别名输入框获得焦点
   * @param props 表格行属性对象
   */
  handleDescFocus(props) {
    this.copyAlias = props.row.config.alias;
    this.editingIndex = props.$index;
  }

  /**
   * 切换指标显示/隐藏状态
   * @param v 开关值，true表示显示，false表示隐藏
   * @param metricInfo 指标信息对象
   */
  handleEditHidden(v, metricInfo) {
    metricInfo.config.hidden = !metricInfo.config.hidden;
    this.updateCustomFields('hidden', !v, metricInfo, true);
  }

  /**
   * 获取分组选择组件
   * @param row 表格行数据
   * @param _ 未使用的参数
   * @param showFoot 是否显示底部"新建分组"选项，默认为true
   * @returns JSX元素
   */
  getGroupCpm(row: IMetricItem, _, showFoot = true) {
    return (
      <bk-select
        key={row.name}
        value={row.scope.id}
        displayTag
        searchable
        clearable={false}
        disabled={!row.movable}
        onChange={(v: number) => this.handleGroupSelectToggle(v, row)}
      >
        {this.groupSelectList.map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            v-bk-tooltips={
              !this.getIsDisable(row.name, item.id)
                ? { disabled: true }
                : {
                    content: this.$t('由匹配规则{0}生成', [this.getDisableTip(row.name, item.id)]),
                    placements: ['right'],
                    boundary: 'window',
                    allowHTML: false,
                  }
            }
            disabled={this.getIsDisable(row.name, item.id)}
            name={item.name === NULL_LABEL ? this.$t('默认分组') : item.name}
          />
        ))}
        {showFoot && (
          <div
            class='edit-group-manage'
            slot='extension'
            onClick={this.handleShowGroupManage}
          >
            <i class='icon-monitor icon-jia' />
            <span>{this.$t('新建分组')}</span>
          </div>
        )}
      </bk-select>
    );
  }

  handleClickDetailOutside(event: MouseEvent) {
    const isClickDetail = this.metricDetailRef?.contains(event.target as Node);
    const isNodeExisted = !document.contains(event.target as Node);
    const isClickFunctionPanel = event.target.closest('#function-menu-panel-main');
    const isClickSelectPanel = ['bk-select-search-input', 'bk-option-content-default', 'bk-option-name'].includes(
      (event.target as HTMLElement).className
    );
    if (isClickDetail || isNodeExisted || isClickSelectPanel || isClickFunctionPanel) {
      return;
    }
    if (this.showDetail) {
      this.showDetail = false;
    }
  }

  /** 组件挂载后初始化：设置默认高度并监听表格头部尺寸变化 */
  mounted() {
    this.handleSetDefault();
    this.resizeObserver = new ResizeObserver(this.handleResize);
    if (this.metricTableHeader) {
      this.resizeObserver.observe(this.metricTableHeader);
    }
    document.addEventListener('click', this.handleClickDetailOutside);
  }
  /** 组件销毁前清理：移除窗口resize监听和ResizeObserver */
  destroyed() {
    window.removeEventListener('resize', this.handleClientResize);
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
    }
    document.removeEventListener('click', this.handleClickDetailOutside);
  }
  /** 处理元素尺寸变化（带防抖） */
  @Debounce(100)
  handleResize(entries) {
    const entry = entries[0];
    if (entry) {
      this.rectHeight = entry.contentRect.height;
    }
  }
  /** 初始化或窗口调整时设置默认值 */
  handleSetDefault() {
    if (this.metricTableHeader) {
      const rect = this.metricTableHeader.getBoundingClientRect();
      this.rectHeight = rect.height;
    }
  }
  /** 窗口调整防抖处理 */
  @Debounce(100)
  handleClientResize() {
    this.handleSetDefault();
  }

  /** 批量编辑成功后处理：关闭侧边栏、更新选择状态、刷新数据 */
  handleEditSuccess() {
    this.isShowMetricSlider = false;
    this.updateAllSelection();
    this.$emit('refresh');
    this.$emit('aliasChange');
  }

  render() {
    return (
      <div class='indicator-table-content'>
        <div
          ref='metricTableHeader'
          class='indicator-table-header'
        >
          <div class='indicator-btn'>
            <bk-button
              theme='primary'
              onClick={this.handleClickSlider}
            >
              {this.$t('管理')}
            </bk-button>
            <bk-popover
              ext-cls='header-select-btn-popover'
              arrow={false}
              disabled={!this.selectionLength}
              placement='bottom-start'
              theme='light common-monitor'
              trigger='click'
            >
              <div
                class={['header-select-btn', { 'btn-disabled': !this.selectionLength }]}
                v-bk-tooltips={{
                  content: this.$t('请先选择指标'),
                  disabled: this.selectionLength,
                }}
              >
                <span class='btn-name'> {this.$t('批量操作')} </span>
                <i class={['icon-monitor', this.header.dropdownShow ? 'icon-arrow-up' : 'icon-arrow-down']} />
              </div>
              <div
                class='header-select-list'
                slot='content'
              >
                {this.header.list.map((option, index) => (
                  <bk-popover
                    key={index}
                    ref='batchAddGroupPopover'
                    ext-cls='header-select-popover'
                    arrow={false}
                    placement='right-start'
                    theme='light common-monitor'
                  >
                    <div class='list-item'>{option.name}</div>
                    <div
                      class='header-select-list mh-300'
                      style='width: 280px;'
                      slot='content'
                    >
                      {this.groupNames.map(group => (
                        <div
                          key={group}
                          class='list-item'
                          v-bk-overflow-tips={{
                            content: group,
                            placement: 'right',
                          }}
                          onClick={() => this.handleBatchAdd(group)}
                        >
                          {group === NULL_LABEL ? this.$t('默认分组') : group}
                        </div>
                      ))}
                    </div>
                  </bk-popover>
                ))}
              </div>
            </bk-popover>
          </div>
          <SearchSelect
            class='search-table'
            ext-cls='search-table'
            data={this.metricSearchData}
            modelValue={this.search}
            placeholder={this.$t('搜索 名称、别名、单位、汇聚方法、显/隐')}
            show-popover-tag-change
            on-change={this.handleSearchChange}
          />
        </div>
        <div class='strategy-config-wrap'>
          {this.loading ? (
            <TableSkeleton type={2} />
          ) : (
            <div
              class='table-box'
              v-bkloading={{ isLoading: this.loading }}
            >
              {[
                this.getTableComponent(),
                this.metricTableVal?.length ? (
                  <bk-pagination
                    key='table-pagination'
                    class='list-pagination'
                    v-show={this.metricTableVal.length}
                    align='right'
                    count={this.tableInstance.total}
                    current={this.tableInstance.page}
                    limit={this.tableInstance.pageSize}
                    limit-list={this.tableInstance.pageList}
                    size='small'
                    pagination-able
                    show-total-count
                    on-change={this.handlePageChange}
                    on-limit-change={this.handleLimitChange}
                  />
                ) : undefined,
              ]}
            </div>
          )}
          <div
            style={{ width: `${this.computedWidth}px`, height: `${this.tableBoxHeight}px` }}
            class='detail'
            v-show={this.showDetail}
            ref='metricDetailRef'
          >
            <MetricDetail
              metricData={this.metricData}
              unitList={this.unitList}
              groupSelectList={this.groupSelectList}
              defaultGroupInfo={this.defaultGroupInfo}
              dimensionTable={this.dimensionTable}
              // allDataPreview={this.allDataPreview}
              groupsMap={this.groupsMap}
              onShowAddGroup={this.handleShowGroupManage}
              onClose={() => {
                this.showDetail = false;
              }}
              onRefresh={() => this.$emit('refresh')}
            />
          </div>
        </div>
        <bk-dialog
          ext-cls=''
          v-model={this.isShowDialog}
          headerPosition='left'
          title={this.$t('确认关闭？')}
          onCancel={() => {
            this.isShowDialog = false;
          }}
          onConfirm={() => this.switcherChange(false)}
        />
        <BatchEdit
          selectedGroupInfo={this.selectedGroupInfo}
          dimensionTable={this.dimensionTable}
          isShow={this.isShowMetricSlider}
          metricTable={this.metricTable}
          unitList={this.unitList}
          onEditSuccess={this.handleEditSuccess}
          onClose={() => {
            this.isShowMetricSlider = false;
          }}
        />
      </div>
    );
  }
}
