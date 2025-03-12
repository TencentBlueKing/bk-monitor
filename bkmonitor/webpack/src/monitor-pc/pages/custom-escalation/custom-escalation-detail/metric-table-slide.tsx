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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils';

import { statusMap } from './metric-table';

import './metric-table-slide.scss';

const radioOption = [
  {
    id: 'allOption',
    label: window.i18n.tc('全选'),
  },
  {
    id: 'checkedOption',
    label: window.i18n.tc('勾选项'),
  },
];

const ALL_OPTION = 'allOption';
const CHECKED_OPTION = 'checkedOption';

@Component
export default class IndicatorTableSlide extends tsc<any, any> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ default: () => [] }) metricTable;
  @Prop({ default: () => [] }) unitList;

  @Ref() metricSliderPopover: any;

  emitIsShow = false;
  loading = false;
  width = 1400;

  unitConfig = {
    mode: 'allOption',
    checkedList: [],
  };
  localUnitConfig;
  table = {
    loading: false,
    select: [],
  };
  localTable = [];
  units = [];
  fieldSettingData: {
    name: any;
    enabled: any;
    unit: any;
    hidden: any;
    aggregateMethod: any;
    func: any;
    status: any;
    group: any;
    set: any;
    interval: any;
    description: any;
  };

  getUnits() {
    if (this.unitConfig.mode === ALL_OPTION) {
      return this.unitList;
    }

    const unitMap = this.unitConfig.checkedList.reduce((map, [name, child]) => {
      const unit = map.get(name) || { id: name, name, formats: [] };
      unit.formats.push({ id: child, name: child });
      map.set(name, unit);
      return map;
    }, new Map());

    return Array.from(unitMap.values());
  }
  handleClick() {
    // modifyCustomTsFields
    this.$store.dispatch('custom-escalation/modifyCustomTsFields', {
      time_series_group_id: this.$route.params.id,
      update_fields: this.localTable,
    });
  }

  handleCancel() { }

  renderHeader(label) {
    return (
      <bk-popover
        // ref='metricSliderPopover'
        class='metric-slider-popover'
        tippyOptions={{
          interactive: true, // 允许在弹出层内进行交互操作
          appendTo: document.body, // 明确指定挂载节点
          // zIndex: 9999, // 确保在最上层显示
          hideOnClick: false, // 禁用点击空白区域关闭
        }}
        // always={true}
        arrow={false}
        offset={'0, 0'}
        placement='bottom-start'
        theme='light common-monitor'
        transfer={true}
        trigger='click'
      >
        {this.$t(label)} <i class='icon-monitor icon-mc-wholesale-editor' />
        <div slot='content'>
          <div class='header'>
            <span>{this.$t('编辑范围')}</span>
            <bk-radio-group v-model={this.localUnitConfig.mode}>
              {radioOption.map(({ id, label }) => (
                <bk-radio
                  key={id}
                  disabled={id === CHECKED_OPTION && this.localUnitConfig.checkedList.length === 0}
                  value={id}
                >
                  {label}
                </bk-radio>
              ))}
            </bk-radio-group>
          </div>
          <div>
            <span>{this.$t('单位')}</span>
            <bk-cascade
              style='width: 250px;'
              v-model={this.localUnitConfig.checkedList}
              list={this.unitList.map(item => {
                item.children = item.formats || [];
                item.id = item.name;
                return item;
              })}
              multiple={true}
            // remote-method={() => {}}
            />
          </div>
          <div>
            <bk-button
              onClick={() => {
                this.unitConfig = deepClone(this.localUnitConfig);
                this.units = this.getUnits();
                this.$refs.metricSliderPopover.hide(); // 手动关闭弹窗
                this.metricSliderPopover.instance.hide();
              }}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button
              onClick={() => {
                this.localUnitConfig = deepClone(this.unitConfig);
              }}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </div>
      </bk-popover>
    );
  }

  @Watch('metricTable')
  metricTableChange(v) {
    this.localTable = deepClone(v);
  }
  @Watch('unitList')
  unitListChange(v) {
    this.units = v;
  }

  created() {
    this.fieldSettingData = {
      name: {
        checked: true,
        disable: false,
        name: this.$t('名称'),
        id: 'name',
      },
      description: {
        checked: true,
        disable: false,
        name: this.$t('别名'),
        id: 'description',
      },
      status: {
        checked: true,
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
    this.localTable = deepClone(this.metricTable);
    this.units = this.unitList;
    this.localUnitConfig = deepClone(this.unitConfig);
  }

  @Emit('hidden')
  handleHiddenSlider() {
    return false;
  }
  handleMouseLeave: ((payload: MouseEvent) => void)[] | ((payload: MouseEvent) => void) = () => { };
  handleToggleChange = () => { };
  getTableComponent() {
    const overflowGroupDom = (props, type, customTip = '' /* 通用组样式 */) => (
      <div class='col-classifiy'>
        {props.row[type].length > 0 ? (
          <div
            ref={`table-${type}-${props.$index}`}
            class='col-classifiy-wrap'
            v-bk-tooltips={{
              placements: ['top-start'],
              boundary: 'window',
              content: () => customTip || props.row[type].join('、 '),
              delay: 200,
              allowHTML: false,
            }}
          >
            {props.row[type]?.map((item, index) => (
              <span
                key={`${item}-${index}`}
                class='classifiy-label gray'
              >
                <span class='text-overflow'>{item}</span>
              </span>
            ))}
            {props.row[`overflow${type}`] ? <span class='classifiy-overflow gray'>...</span> : undefined}
          </div>
        ) : (
          <div>--</div>
        )}
      </div>
    );

    const statusPoint = (color1: string, color2: string) => (
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

    const enabledDom = (props, type: 'enabled' | 'hidden' /* 通用开关样式 */) => (
      <div class='switch-wrap'>
        <bk-switcher
          key={props.row.id}
          v-model={props.row[type]}
          // pre-check={() => this.handlePreSwitchChange(props.row, type)}
          size='small'
          theme='primary'
        />
        {/* {!this.authority.MANAGE_AUTH ? (
          <div
            class='switch-wrap-modal'
            v-authority={{ active: !this.authority.MANAGE_AUTH }}
            onClick={(e: Event) => {
              e.stopPropagation();
              e.preventDefault();
              !this.authority.MANAGE_AUTH && this.handleShowAuthorityDetail(this.authorityMap.MANAGE_AUTH);
            }}
          />
        ) : undefined} */}
      </div>
    );
    const nameSlot = {
      /* 名称 */ default: props => (
        <span
          class='name'
          onClick={() => this.showMetricDetail(props)}
        >
          {props.row.name || '--'}
        </span>
      ),
    };
    const descriptionSlot = {
      /* 别名 */ default: props => (
        <bk-input
          v-model={props.row.description}
          value={props.row.description || props.row.name}
        />
      ),
    };
    const statusSlot = {
      /* 状态 */ default: props => {
        return (
          <span class='status-wrap'>
            {statusPoint(
              statusMap.get(Boolean(props.row?.disabled)).color1,
              statusMap.get(Boolean(props.row?.disabled)).color2
            )}
            <span>{statusMap.get(Boolean(props.row?.disabled)).name}</span>
          </span>
        );
      },
    };
    const enabledSlot = {
      /* 启停 */ default: props => enabledDom(props, 'enabled'),
    };
    const unitSlot = {
      /* 单位 */ default: props => (
        <div
          class='cell-margin'
          onMouseleave={this.handleMouseLeave}
        >
          <bk-select
            v-model={props.row.unit}
            clearable={false}
            popover-width={180}
            searchable
            onToggle={this.handleToggleChange}
          >
            {this.units.map((group, index) => (
              <bk-option-group
                key={index}
                name={group.name}
              >
                {group.formats.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-option-group>
            ))}
          </bk-select>
        </div>
      ),
    };
    const hiddenSlot = {
      /* 显示 */ default: props => enabledDom(props, 'hidden'),
    };
    const aggregateMethodSlot = {
      /* 汇聚方法 */ default: props => (
        <bk-select
          clearable={false}
          value={props.row.name || '--'}
        >
          {['SUM'].map(item => (
            <bk-option
              id={item}
              key={item}
              name={item}
            >
              {item}
            </bk-option>
          ))}
        </bk-select>
      ),
    };
    const funcSlot = {
      /* 函数 */ default: props => props.row.name || '--',
    };
    const intervalSlot = {
      /* 上报周期 */ default: props => props.row.name || '--',
    };
    const setSlot = {
      /* 操作 */ default: props => (
        <div>
          <i
            class='icon-monitor icon-double-up'
            onClick={() => this.handClickRow(props, 'add')}
          />
          <i
            class='icon-monitor icon-double-down'
            onClick={() => this.handClickRow(props, 'del')}
          />
        </div>
      ),
    };
    const { name, enabled, unit, hidden, aggregateMethod, func, status, group, set, interval, description } =
      this.fieldSettingData;
    return (
      <bk-table
        ref='strategyTable'
        class='slider-table'
        v-bkloading={{ isLoading: this.table.loading }}
        // col-border={true}
        empty-text={this.$t('无数据')}
        max-height={474}
        // on={{
        //   'hook:mounted': this.handleTableMountedOrActivated,
        //   'hook:activated': this.handleTableMountedOrActivated,
        // }}
        // on-header-dragend={this.handleHeaderDragend}
        // on-selection-change={this.handleSelectionChange}
        {...{
          props: {
            data: this.localTable,
          },
        }}
      >
        <div slot='empty'>
          {/* <EmptyStatus
            type={this.emptyType}
            // onOperation={this.handleOperation}
            onOperation={() => { }}
          /> */}
        </div>
        {/* <bk-table-column
          scopedSlots={{
            default: ({ row }) => (
              <bk-checkbox
                v-model={row.selection}
                onChange={this.updateCheckValue}
              />
            ),
          }}
          align='center'
          type='selection'
          value={this.allCheckValue}
          onChange={this.handleCheckChange}
        /> */}
        {name.checked && (
          <bk-table-column
            key='name'
            width='150'
            label={this.$t('名称')}
            prop='name'
            scopedSlots={nameSlot}
          />
        )}
        {description.checked && (
          <bk-table-column
            key='description'
            width='200'
            label={this.$t('别名')}
            prop='description'
            scopedSlots={descriptionSlot}
          />
        )}
        {unit.checked && (
          <bk-table-column
            key='unit'
            width='100'
            label={this.$t('单位')}
            prop='unit'
            // TODO: 表头编辑功能
            // renderHeader={() => this.renderHeader('单位')}
            scopedSlots={unitSlot}
          />
        )}
        {aggregateMethod.checked && (
          <bk-table-column
            key='aggregateMethod'
            width='100'
            class-name='ahahahah'
            label={this.$t('汇聚方法')}
            prop='aggregateMethod'
            scopedSlots={aggregateMethodSlot}
          />
        )}
        {interval.checked && (
          <bk-table-column
            key='interval'
            width='100'
            label={this.$t('上报周期')}
            prop='interval'
            scopedSlots={intervalSlot}
          />
        )}
        {enabled.checked && (
          <bk-table-column
            key='enabled'
            width='100'
            label={this.$t('启/停')}
            scopedSlots={enabledSlot}
          />
        )}
        {hidden.checked && (
          <bk-table-column
            key='hidden'
            width='100'
            label={this.$t('显示')}
            scopedSlots={hiddenSlot}
          />
        )}
        {set.checked && (
          <bk-table-column
            key='set'
            width='100'
            label={this.$t('操作')}
            scopedSlots={setSlot}
          />
        )}
      </bk-table>
    );
  }
  handClickRow(props: any, arg1: string): void { }
  showMetricDetail(props: any): void { }
  render() {
    return (
      <div>
        <bk-sideslider
          {...{ on: { 'update:isShow': this.handleHiddenSlider } }}
          width={this.width}
          ext-cls='event-detail-sideslider'
          isShow={this.isShow}
          quickClose
          onHidden={this.handleHiddenSlider}
        >
          <div
            class='sideslider-title'
            slot='header'
          >
            <span>{this.$t('批量编辑指标')}</span>
          </div>
          <div
            class='metric-slider-content'
            slot='content'
            v-bkloading={{ isLoading: this.loading }}
          >
            <div class='slider-search'>
              <bk-input />
            </div>
            {this.getTableComponent()}
            <div class='slider-btn'>
              <bk-button onClick={this.handleClick}>{this.$t('保存')}</bk-button>
              <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
            </div>
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
