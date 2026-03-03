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
import { Component, Prop, InjectReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import DimensionBatchEdit from './components/batch-edit';
import infoSrc from '../../../../../../../static/images/png/dimension-guide.png';
import { fuzzyMatch } from '../../../../utils';
import { NULL_LABEL } from '../../../../type';
import type { ICustomTsFields } from '../../../../../service';
import type { RequestHandlerMap } from '../../../../type';

import './index.scss';

/**
 * 组件 Props 接口定义
 */
interface IProps {
  /** 选中的分组信息，包含分组ID和名称 */
  selectedGroupInfo: { id: number; name: string };
  /** 表格加载状态 */
  loading: boolean;
  /** 维度表格数据列表 */
  dimensionTable: DimensionDetail[];
}

/**
 * 组件事件接口定义
 */
interface IEmits {
  /** 刷新事件，当数据更新后触发 */
  onRefresh: () => void;
  /** 别名变化事件 */
  onAliasChange: () => void;
}

/**
 * 维度详情类型定义
 * 从 ICustomTsFields 的 dimensions 数组中提取单个维度项的类型
 */
type DimensionDetail = ICustomTsFields['dimensions'][number];

/**
 * 维度列表组件
 * 用于展示和管理自定义时序指标的维度信息，包括维度的别名、显示状态、常用维度等配置
 */
@Component
export default class DimensionTabDetail extends tsc<IProps, IEmits> {
  /** 选中的分组信息 */
  @Prop({ default: () => {} }) selectedGroupInfo: IProps['selectedGroupInfo'];
  /** 维度表格数据列表 */
  @Prop({ default: () => [] }) dimensionTable: IProps['dimensionTable'];
  /** 表格加载状态 */
  @Prop({ default: false }) loading: IProps['loading'];

  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  /** 编辑时临时保存的别名，用于在失焦时判断是否需要更新 */
  copyAlias = '';
  /** 当前正在编辑的行索引，-1 表示没有行在编辑状态 */
  editingIndex = -1;
  /** 搜索关键词，用于过滤维度列表 */
  search = '';
  /** 是否显示维度批量编辑抽屉 */
  isShowDimensionSlider = false;

  /**
   * 过滤后的表格数据
   * 根据搜索关键词对维度名称和别名进行模糊匹配
   */
  get tableData() {
    return this.dimensionTable.filter(item => {
      return fuzzyMatch(item.name, this.search) || fuzzyMatch(item.config.alias, this.search);
    });
  }

  @Watch('selectedGroupInfo', { immediate: true })
  handleSelectedGroupInfoChange() {
    this.search = '';
  }

  /**
   * 显示维度批量编辑抽屉
   */
  handleShowDimensionSlider() {
    this.isShowDimensionSlider = true;
  }

  /**
   * 处理别名输入框聚焦事件
   * @param props 表格行属性，包含 row 和 $index
   */
  handleDescFocus(props) {
    this.copyAlias = props.row.config.alias;
    this.editingIndex = props.$index;
  }

  /**
   * 处理别名编辑完成事件
   * 当别名输入框失焦时，如果别名有变化则更新到服务器
   * @param row 当前编辑的维度数据
   */
  async handleEditDescription(row: DimensionDetail) {
    if (this.copyAlias === row.config.alias) return;
    row.config.alias = this.copyAlias;
    await this.updateDimensionField(row, 'alias', this.copyAlias);
    this.$emit('aliasChange');
  }

  /**
   * 切换维度的显示/隐藏状态
   * @param v 切换后的状态值
   * @param row 当前操作的维度数据
   */
  handleEditHidden(v, row) {
    row.config.hidden = !row.config.hidden;
    this.updateDimensionField(row, 'hidden', !v);
  }

  /**
   * 处理常用维度切换
   * @param row 当前操作的维度数据
   * @param val 是否设置为常用维度
   */
  async handleCommonChange(row: DimensionDetail, val: boolean) {
    row.config.common = val;
    await this.updateDimensionField(row, 'common', val);
  }

  /**
   * 统一更新维度字段的API调用
   * 根据字段类型（alias、hidden、common 或其他）构建不同的更新结构
   * @param dimensionInfo 要更新的维度信息
   * @param k 要更新的字段名
   * @param v 要更新的字段值
   */
  async updateDimensionField(dimensionInfo: DimensionDetail, k: string, v: any) {
    const updateField = {
      type: 'dimension',
      name: dimensionInfo.name,
      scope: dimensionInfo.scope,
      config: {},
    };
    if (['alias', 'hidden', 'common'].includes(k)) {
      updateField.config[k] = v;
    } else {
      updateField[k] = v;
      delete updateField.config;
    }
    try {
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
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
    } catch (e) {
      console.error('Update dimension failed:', e);
      this.$bkMessage({
        message: this.$t('更新失败'),
        theme: 'error',
      });
    }
  }

  /**
   * 表格列配置
   * 定义维度列表表格的列配置，包括名称、别名、分组、显示、常用维度等列
   */
  get columnConfigs() {
    return [
      {
        id: 'name',
        minWidth: 150,
        label: this.$t('名称'),
        scopedSlots: {
          default: (props: { row: DimensionDetail }) => (
            <div
              class='name'
              v-bk-overflow-tips
            >
              {props.row.name || '--'}
            </div>
          ),
        },
      },
      {
        id: 'alias',
        minWidth: 100,
        label: this.$t('别名'),
        scopedSlots: {
          default: (props: { $index: number; row: DimensionDetail }) => (
            <div
              class='description-cell'
              onClick={() => this.handleDescFocus(props)}
            >
              <bk-input
                ext-cls='description-input'
                readonly={this.editingIndex !== props.$index}
                value={props.row.config.alias}
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
        },
      },
      {
        id: 'scope',
        minWidth: 150,
        label: this.$t('分组'),
        scopedSlots: {
          default: (props: { row: DimensionDetail }) => (
            <div
              class='name'
              v-bk-overflow-tips
            >
              {props.row.scope.name && props.row.scope.name === NULL_LABEL
                ? this.$t('默认分组')
                : props.row.scope.name || '--'}
            </div>
          ),
        },
      },
      {
        id: 'hidden',
        width: 100,
        label: this.$t('显示'),
        scopedSlots: {
          default: props => (
            <bk-switcher
              class='switcher-btn'
              size='small'
              theme='primary'
              value={!props.row.config.hidden}
              onChange={v => this.handleEditHidden(v, props.row)}
            />
          ),
        },
        renderHeaderFn: () => (
          <div class='common-title'>
            <span>{this.$t('显示')}</span>
            <bk-popover ext-cls='render-header-hidden-popover'>
              <bk-icon type='info-circle' />
              <div slot='content'>{this.$t('关闭后，在可视化视图里，将被隐藏')}</div>
            </bk-popover>
          </div>
        ),
      },
      {
        id: 'common',
        width: 100,
        label: this.$t('常用维度'),
        scopedSlots: {
          default: (props: { row: DimensionDetail }) => (
            <bk-checkbox
              false-value={false}
              true-value={true}
              value={props.row.config.common}
              onChange={(val: boolean) => this.handleCommonChange(props.row, val)}
            />
          ),
        },
        renderHeaderFn: config => (
          <div class='common-title'>
            <div>{this.$t(config.label as string)}</div>
            <bk-popover
              ext-cls='common-info-popover'
              offset='-50, 0'
              placement='top-start'
              theme='light common-monitor'
            >
              <bk-icon type='info-circle' />
              <div slot='content'>
                <div class='info'>{this.$t('打开后，可以在 [可视化] 的 [过滤条件] 里快速展开：')}</div>
                <div class='img'>
                  <img
                    alt=''
                    src={infoSrc}
                  />
                </div>
              </div>
            </bk-popover>
          </div>
        ),
      },
    ];
  }

  /**
   * 保存抽屉信息
   * @param updateArray 更新数组
   * @param delArray 删除数组
   */
  async handleSaveSliderInfo(updateArray: any[], delArray: any[] = []): Promise<void> {
    this.isShowDimensionSlider = false;
    const params = {
      time_series_group_id: this.timeSeriesGroupId,
      update_fields: updateArray,
      delete_fields: delArray,
    };
    if (this.isAPM) {
      delete params.time_series_group_id;
      Object.assign(params, {
        app_name: this.appName,
        service_name: this.serviceName,
      });
    }
    await this.requestHandlerMap.modifyCustomTsFields(params);
    this.$emit('refresh');
    this.$emit('aliasChange');
    this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
  }

  render() {
    return (
      <div class='dimension-table-content'>
        <div class='dimension-table-header'>
          <div class='dimension-btn'>
            <bk-button
              class='header-btn'
              theme='primary'
              onClick={this.handleShowDimensionSlider}
            >
              {this.$t('管理')}
            </bk-button>
          </div>
          <bk-input
            ext-cls='search-table'
            v-model={this.search}
            placeholder={this.$t('搜索 名称、别名')}
            right-icon='icon-monitor icon-mc-search'
          />
        </div>
        <div
          class='table-container'
          v-bkloading={{ isLoading: this.loading }}
        >
          <bk-table
            class='dimension-table'
            data={this.tableData}
            max-height={window.innerHeight - 550}
            row-hover='auto'
          >
            {this.columnConfigs.map(config => (
              <bk-table-column
                key={config.id}
                prop={config.id}
                width={config.width}
                minWidth={config.minWidth}
                renderHeader={config?.renderHeaderFn ? () => config.renderHeaderFn(config) : undefined}
                label={config.label}
                scopedSlots={config.scopedSlots}
              />
            ))}
          </bk-table>
        </div>
        <DimensionBatchEdit
          selectedGroupInfo={this.selectedGroupInfo}
          dimensionTable={this.dimensionTable}
          isShow={this.isShowDimensionSlider}
          onHidden={v => {
            this.isShowDimensionSlider = v;
          }}
          onSaveInfo={this.handleSaveSliderInfo}
        />
      </div>
    );
  }
}
