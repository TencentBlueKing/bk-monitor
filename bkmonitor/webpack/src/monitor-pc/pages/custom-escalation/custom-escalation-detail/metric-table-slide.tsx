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
// import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
// import { Component as tsc } from 'vue-tsx-support';

// import { deepClone } from 'monitor-common/utils';

// import { METHOD_LIST } from '../../../constant/constant';
// import FunctionMenu from '../../strategy-config/strategy-config-set-new/monitor-data/function-menu';
// import { statusMap } from './metric-table';

// import './metric-table-slide.scss';

// const radioOption = [
//   {
//     id: 'allOption',
//     label: window.i18n.tc('全选'),
//   },
//   {
//     id: 'checkedOption',
//     label: window.i18n.tc('勾选项'),
//   },
// ];

// const ALL_OPTION = 'allOption';
// const CHECKED_OPTION = 'checkedOption';

// @Component
// export default class IndicatorTableSlide extends tsc<any, any> {
//   @Prop({ type: Boolean, default: false }) isShow: boolean;
//   @Prop({ default: () => [] }) metricTable;
//   @Prop({ default: () => [] }) unitList;
//   @Prop({ default: () => [] }) cycleOption;

//   @Ref() metricSliderPopover: any;
//   @Ref('metricTableRef') metricTableRef: any;

//   inputFocus = -1;
//   emitIsShow = false;
//   loading = false;
//   width = 1400;

//   unitConfig = {
//     mode: 'allOption',
//     checkedList: [],
//   };
//   localUnitConfig;
//   table = {
//     loading: false,
//     select: [],
//   };
//   localTable = [];
//   units = [];
//   fieldSettingData: {
//     name: any;
//     enabled: any;
//     unit: any;
//     hidden: any;
//     aggregateMethod: any;
//     func: any;
//     status: any;
//     group: any;
//     set: any;
//     interval: any;
//     description: any;
//   };

//   getUnits() {
//     if (this.unitConfig.mode === ALL_OPTION) {
//       return this.unitList;
//     }

//     const unitMap = this.unitConfig.checkedList.reduce((map, [name, child]) => {
//       const unit = map.get(name) || { id: name, name, formats: [] };
//       unit.formats.push({ id: child, name: child });
//       map.set(name, unit);
//       return map;
//     }, new Map());

//     return Array.from(unitMap.values());
//   }

//   @Emit('saveInfo')
//   handleSaveTableInfo() {
//     // return this.localTable;
//   }

//   @Emit('hidden')
//   handleCancel(): boolean {
//     this.localTable = deepClone(this.metricTable);
//     return false;
//   }

//   renderHeader(label) {
//     return (
//       <bk-popover
//         // ref='metricSliderPopover'
//         class='metric-slider-popover'
//         tippyOptions={{
//           interactive: true, // 允许在弹出层内进行交互操作
//           appendTo: document.body, // 明确指定挂载节点
//           hideOnClick: false, // 禁用点击空白区域关闭
//         }}
//         arrow={false}
//         offset={'0, 0'}
//         placement='bottom-start'
//         theme='light common-monitor'
//         transfer={true}
//         trigger='click'
//       >
//         {this.$t(label)} <i class='icon-monitor icon-mc-wholesale-editor' />
//         <div slot='content'>
//           <div class='header'>
//             <span>{this.$t('编辑范围')}</span>
//             <bk-radio-group v-model={this.localUnitConfig.mode}>
//               {radioOption.map(({ id, label }) => (
//                 <bk-radio
//                   key={id}
//                   disabled={id === CHECKED_OPTION && this.localUnitConfig.checkedList.length === 0}
//                   value={id}
//                 >
//                   {label}
//                 </bk-radio>
//               ))}
//             </bk-radio-group>
//           </div>
//           <div>
//             <span>{this.$t('单位')}</span>
//             <bk-cascade
//               v-model={this.localUnitConfig.checkedList}
//               list={this.unitList.map(item => {
//                 item.children = item.formats || [];
//                 item.id = item.name;
//                 return item;
//               })}
//               multiple={true}
//             // remote-method={() => {}}
//             />
//           </div>
//           <div>
//             <bk-button
//               onClick={() => {
//                 this.unitConfig = deepClone(this.localUnitConfig);
//                 this.units = this.getUnits();
//                 this.$refs.metricSliderPopover.hide(); // 手动关闭弹窗
//                 this.metricSliderPopover.instance.hide();
//               }}
//             >
//               {this.$t('确定')}
//             </bk-button>
//             <bk-button
//               onClick={() => {
//                 this.localUnitConfig = deepClone(this.unitConfig);
//               }}
//             >
//               {this.$t('取消')}
//             </bk-button>
//           </div>
//         </div>
//       </bk-popover>
//     );
//   }

//   @Watch('metricTable')
//   metricTableChange(v) {
//     this.localTable = deepClone(v);
//   }
//   @Watch('unitList')
//   unitListChange(v) {
//     this.units = v;
//   }

//   created() {
//     this.fieldSettingData = {
//       name: {
//         checked: true,
//         disable: false,
//         name: this.$t('名称'),
//         id: 'name',
//       },
//       description: {
//         checked: true,
//         disable: false,
//         name: this.$t('别名'),
//         id: 'description',
//       },
//       status: {
//         checked: true,
//         disable: false,
//         name: this.$t('状态'),
//         id: 'status',
//       },
//       unit: {
//         checked: true,
//         disable: false,
//         name: this.$t('单位'),
//         id: 'unit',
//       },
//       aggregateMethod: {
//         checked: true,
//         disable: false,
//         name: this.$t('汇聚方法'),
//         id: 'aggregateMethod',
//       },
//       interval: {
//         checked: true,
//         disable: false,
//         name: this.$t('上报周期'),
//         id: 'interval',
//       },
//       func: {
//         checked: true,
//         disable: false,
//         name: this.$t('函数'),
//         id: 'function',
//       },
//       hidden: {
//         checked: true,
//         disable: false,
//         name: this.$t('显示'),
//         id: 'hidden',
//       },
//       enabled: {
//         checked: true,
//         disable: false,
//         name: this.$t('启/停'),
//         id: 'enabled',
//       },
//       set: {
//         checked: true,
//         disable: false,
//         name: this.$t('操作'),
//         id: 'set',
//       },
//     };
//     this.localTable = deepClone(this.metricTable);
//     this.units = this.unitList;
//     this.localUnitConfig = deepClone(this.unitConfig);
//   }

//   @Emit('hidden')
//   handleHiddenSlider() {
//     return false;
//   }
//   handleMouseLeave: ((payload: MouseEvent) => void)[] | ((payload: MouseEvent) => void) = () => { };
//   handleToggleChange = isShow => { };
//   getTableComponent() {

//     const statusPoint = (color1: string, color2: string) => (
//       <div
//         style={{ background: color2 }}
//         class='status-point'
//       >
//         <div
//           style={{ background: color1 }}
//           class='point'
//         />
//       </div>
//     );

//     const enabledDom = (props, type: 'enabled' | 'hidden' /* 通用开关样式 */) => (
//       <div class='switch-wrap'>
//         <bk-switcher
//           key={props.row.id}
//           v-model={props.row[type]}
//           // pre-check={() => this.handlePreSwitchChange(props.row, type)}
//           size='small'
//           theme='primary'
//         />
//       </div>
//     );
//     const nameSlot = {
//       /* 名称 */ default: props => (
//         <span
//           class='name'
//           onClick={() => this.showMetricDetail(props)}
//         >
//           {props.row.name || '--'}
//         </span>
//       ),
//     };
//     const descriptionSlot = {
//       /* 别名 */ default: props => (
//         <bk-input
//           class={['slider-input', this.inputFocus === props.$index ? 'focus' : '']}
//           v-model={props.row.description}
//           value={props.row.description || props.row.name}
//           onBlur={() => (this.inputFocus = -1)}
//           onFocus={() => (this.inputFocus = props.$index)}
//         />
//       ),
//     };
//     const statusSlot = {
//       /* 状态 */ default: props => {
//         return (
//           <span class='status-wrap'>
//             {statusPoint(
//               statusMap.get(Boolean(props.row?.disabled)).color1,
//               statusMap.get(Boolean(props.row?.disabled)).color2
//             )}
//             <span>{statusMap.get(Boolean(props.row?.disabled)).name}</span>
//           </span>
//         );
//       },
//     };
//     const enabledSlot = {
//       /* 启停 */ default: props => enabledDom(props, 'enabled'),
//     };
//     const unitSlot = {
//       /* 单位 */ default: props => (
//         <div
//           class={'slider-select'}
//           onMouseleave={this.handleMouseLeave}
//         >
//           <bk-select
//             v-model={props.row.unit}
//             clearable={false}
//             popover-width={180}
//             searchable
//             onToggle={this.handleToggleChange}
//           >
//             {this.units.map((group, index) => (
//               <bk-option-group
//                 key={index}
//                 name={group.name}
//               >
//                 {group.formats.map(option => (
//                   <bk-option
//                     id={option.id}
//                     key={option.id}
//                     name={option.name}
//                   />
//                 ))}
//               </bk-option-group>
//             ))}
//           </bk-select>
//         </div>
//       ),
//     };
//     const hiddenSlot = {
//       /* 显示 */ default: props => enabledDom(props, 'hidden'),
//     };
//     const aggregateMethodSlot = {
//       /* 汇聚方法 */ default: props => (
//         <bk-select
//           class='slider-select'
//           v-model={props.row.aggregate_method}
//           clearable={false}
//         >
//           {METHOD_LIST.map(({ id, name }) => (
//             <bk-option
//               id={id}
//               key={id}
//               name={name}
//             />
//           ))}
//         </bk-select>
//       ),
//     };
//     const intervalSlot = {
//       /* 上报周期 */ default: props => (
//         <bk-select
//           class='slider-select'
//           v-model={props.row.interval}
//           clearable={false}
//         >
//           {this.cycleOption.map(option => (
//             <bk-option
//               id={option.id}
//               key={option.id}
//               name={`${option.name}s`}
//             />
//           ))}
//         </bk-select>
//       ),
//     };
//     const functionSlot = {
//       /* 函数 */ default: props => (
//         <FunctionMenu
//           class='init-add'
//           list={[]}
//         // onFuncSelect={v => this.editFunction(v, metricData)}
//         >
//           {props.row.function?.id ?? '-'}
//         </FunctionMenu>
//       ),
//     };
//     const setSlot = {
//       /* 操作 */ default: props => (
//         <div>
//           <i
//             class='bk-icon icon-plus-circle-shape set-icon'
//             onClick={() => this.handClickRow(props, 'add')}
//           />
//           <i
//             class='bk-icon icon-minus-circle-shape set-icon'
//             onClick={() => this.handClickRow(props, 'del')}
//           />
//         </div>
//       ),
//     };
//     const { name, enabled, unit, hidden, aggregateMethod, func, status, group, set, interval, description } =
//       this.fieldSettingData;
//     return (
//       <bk-table
//         ref='metricTableRef'
//         class='slider-table'
//         v-bkloading={{ isLoading: this.table.loading }}
//         col-border={true}
//         empty-text={this.$t('无数据')}
//         // on={{
//         //   'hook:mounted': this.handleTableMountedOrActivated,
//         //   'hook:activated': this.handleTableMountedOrActivated,
//         // }}
//         // on-header-dragend={this.handleHeaderDragend}
//         // on-selection-change={this.handleSelectionChange}
//         {...{
//           props: {
//             data: this.localTable,
//           },
//         }}
//       >
//         <div slot='empty'>
//           {/* <EmptyStatus
//             type={this.emptyType}
//             // onOperation={this.handleOperation}
//             onOperation={() => { }}
//           /> */}
//         </div>
//         {/* <bk-table-column
//           scopedSlots={{
//             default: ({ row }) => (
//               <bk-checkbox
//                 v-model={row.selection}
//                 onChange={this.updateCheckValue}
//               />
//             ),
//           }}
//           align='center'
//           type='selection'
//           value={this.allCheckValue}
//           onChange={this.handleCheckChange}
//         /> */}
//         {name.checked && (
//           <bk-table-column
//             key='name'
//             width='150'
//             label={this.$t('名称')}
//             prop='name'
//             scopedSlots={nameSlot}
//           />
//         )}
//         {description.checked && (
//           <bk-table-column
//             key='description'
//             width='150'
//             label={this.$t('别名')}
//             prop='description'
//             scopedSlots={descriptionSlot}
//           />
//         )}
//         {unit.checked && (
//           <bk-table-column
//             key='unit'
//             width='100'
//             label={this.$t('单位')}
//             prop='unit'
//             // TODO: 表头编辑功能
//             // renderHeader={() => this.renderHeader('单位')}
//             scopedSlots={unitSlot}
//           />
//         )}
//         {aggregateMethod.checked && (
//           <bk-table-column
//             key='aggregateMethod'
//             width='100'
//             class-name='ahahahah'
//             label={this.$t('汇聚方法')}
//             prop='aggregateMethod'
//             scopedSlots={aggregateMethodSlot}
//           />
//         )}
//         {interval.checked && (
//           <bk-table-column
//             key='interval'
//             width='100'
//             label={this.$t('上报周期')}
//             prop='interval'
//             scopedSlots={intervalSlot}
//           />
//         )}
//         {func.checked && (
//           <bk-table-column
//             key='function'
//             width='100'
//             label={this.$t('函数')}
//             prop='function'
//             scopedSlots={functionSlot}
//           />
//         )}
//         {enabled.checked && (
//           <bk-table-column
//             key='enabled'
//             width='100'
//             label={this.$t('启/停')}
//             scopedSlots={enabledSlot}
//           />
//         )}
//         {hidden.checked && (
//           <bk-table-column
//             key='hidden'
//             width='100'
//             label={this.$t('显示')}
//             scopedSlots={hiddenSlot}
//           />
//         )}
//         {set.checked && (
//           <bk-table-column
//             key='set'
//             width='100'
//             label={this.$t('操作')}
//             scopedSlots={setSlot}
//           />
//         )}
//       </bk-table>
//     );
//   }
//   handClickRow(props: any, type: string): void {
//     const typeMap = {
//       add: () => {
//         this.localTable.splice(props.$index + 1, 0, {});
//       },
//       del: () => {
//         this.localTable.splice(props.$index, 1);
//       },
//     };
//     typeMap[type]();
//   }
//   showMetricDetail(props: any): void {
//     console.log(props);
//   }
//   render() {
//     return (
//       <div class='haha'>
//         <bk-sideslider
//           {...{ on: { 'update:isShow': this.handleHiddenSlider } }}
//           width={this.width}
//           ext-cls='metric-slider-box'
//           isShow={this.isShow}
//           quickClose
//           onHidden={this.handleHiddenSlider}
//         >
//           <div
//             class='sideslider-title'
//             slot='header'
//           >
//             <span>{this.$t('批量编辑指标')}</span>
//           </div>
//           <div
//             class='metric-slider-content'
//             slot='content'
//             v-bkloading={{ isLoading: this.loading }}
//           >
//             <div class='slider-search'>
//               <bk-input />
//             </div>
//             {this.getTableComponent()}
//             <div class={'slider-btn'}>
//               <bk-button
//                 theme='primary'
//                 onClick={this.handleSaveTableInfo}
//               >
//                 {this.$t('保存')}
//               </bk-button>

//               <bk-button
//                 theme='default'
//                 onClick={this.handleCancel}
//               >
//                 {this.$t('取消')}
//               </bk-button>
//             </div>
//           </div>
//         </bk-sideslider>
//       </div>
//     );
//   }
// }

import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils';

import { METHOD_LIST } from '../../../constant/constant';
import FunctionMenu from '../../strategy-config/strategy-config-set-new/monitor-data/function-menu';
import { statusMap } from './metric-table';

import './metric-table-slide.scss';

// 常量定义
const RADIO_OPTIONS = [
  { id: 'allOption', label: window.i18n.tc('全选') },
  { id: 'checkedOption', label: window.i18n.tc('勾选项') },
];

const FIELD_SETTINGS = {
  name: { label: '名称', width: 175 },
  description: { label: '别名', width: 175 },
  unit: { label: '单位', width: 125 },
  aggregateMethod: { label: '汇聚方法', width: 125 },
  interval: { label: '上报周期', width: 125 },
  func: { label: '函数', width: 125 },
  enabled: { label: '启/停', width: 125 },
  hidden: { label: '显示', width: 125 },
  set: { label: '操作', width: 125 },
};

const ALL_OPTION = 'allOption';
const CHECKED_OPTION = 'checkedOption';

interface IMetricItem {
  id: string;
  name: string;
  description?: string;
  unit?: string;
  aggregate_method?: string;
  interval?: number;
  function?: any;
  enabled?: boolean;
  hidden?: boolean;
  disabled?: boolean;
  [key: string]: any;
}

@Component
export default class IndicatorTableSlide extends tsc<any> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ default: () => [] }) metricTable: IMetricItem[];
  @Prop({ default: () => [] }) unitList: any[];
  @Prop({ default: () => [] }) cycleOption: any[];

  @Ref() metricSliderPopover: any;
  @Ref('metricTableRef') metricTableRef: HTMLDivElement;
  @InjectReactive('metricFunctions') metricFunctions;

  // 响应式数据
  localTable: IMetricItem[] = [];
  units: any[] = [];
  inputFocus = -1;
  loading = false;
  width = 1400;

  // 单位配置
  unitConfig = { mode: ALL_OPTION, checkedList: [] };
  localUnitConfig = deepClone(this.unitConfig);

  // 表格配置
  tableConfig = {
    loading: false,
    fieldSettings: {
      name: { checked: true, disable: false },
      description: { checked: true, disable: false },
      unit: { checked: true, disable: false },
      aggregateMethod: { checked: true, disable: false },
      interval: { checked: true, disable: false },
      func: { checked: true, disable: false },
      enabled: { checked: true, disable: false },
      hidden: { checked: true, disable: false },
      set: { checked: true, disable: false },
    },
  };

  // 生命周期钩子
  created() {
    this.initData();
  }

  // 数据初始化
  initData() {
    this.localTable = deepClone(this.metricTable);
    this.units = this.unitList;
  }

  // 事件处理
  @Emit('saveInfo')
  handleSave() {
    return this.localTable;
  }

  @Emit('hidden')
  handleCancel() {
    return false;
  }

  // 响应式处理
  @Watch('metricTable', { immediate: true, deep: true })
  handleMetricTableChange(newVal: IMetricItem[]) {
    this.localTable = deepClone(newVal);
  }

  @Watch('unitList', { immediate: true })
  handleUnitListChange(newVal: any[]) {
    this.units = newVal;
    this.localUnitConfig = deepClone(this.unitConfig);
  }

  // 主渲染逻辑
  render() {
    return (
      <bk-sideslider
        {...{ on: { 'update:isShow': this.handleCancel } }}
        width={this.width}
        ext-cls='metric-slider-box'
        isShow={this.isShow}
        quickClose
        onHidden={this.handleCancel}
      >
        <div
          class='sideslider-title'
          slot='header'
        >
          {this.$t('批量编辑指标')}
        </div>

        <div
          class='metric-slider-content'
          slot='content'
        >
          <div class='slider-search'>
            <bk-input
              placeholder={this.$t('搜索指标')}
              right-icon='bk-icon icon-search'
            />
          </div>

          <bk-table
            ref='metricTableRef'
            class='slider-table'
            v-bkloading={{ isLoading: this.tableConfig.loading }}
            data={this.localTable}
            empty-text={this.$t('无数据')}
            colBorder
          >
            {Object.entries(FIELD_SETTINGS).map(([key, config]) => {
              if (!this.tableConfig.fieldSettings[key].checked) return null;

              return (
                <bk-table-column
                  key={key}
                  width={config.width}
                  scopedSlots={{
                    default: props => {
                      switch (key) {
                        case 'name':
                          return this.renderNameColumn(props);
                        case 'description':
                          return this.renderDescriptionColumn(props);
                        case 'unit':
                          return this.renderUnitColumn(props);
                        case 'enabled':
                        case 'hidden':
                          return this.renderSwitch(props.row, key);
                        case 'status':
                          return this.renderStatusPoint(props.row);
                        case 'aggregateMethod':
                          return this.renderAggregateMethod(props.row);
                        case 'interval':
                          return this.renderInterval(props.row);
                        case 'func':
                          return this.renderFunction(props.row);
                        case 'set':
                          return this.renderOperations(props);
                        default:
                          return props.row[key] || '--';
                      }
                    },
                    header:
                      key === 'unit'
                        ? () => (
                          <bk-popover
                            ref='metricSliderPopover'
                            placement='bottom-start'
                            tippyOptions={{ appendTo: 'parent' }}
                          >
                            {this.$t('单位')} <i class='icon-monitor icon-mc-wholesale-editor' />
                            {this.renderUnitConfigPopover()}
                          </bk-popover>
                        )
                        : null,
                  }}
                  label={this.$t(config.label)}
                  prop={key}
                />
              );
            })}
          </bk-table>

          <div class='slider-footer'>
            <bk-button
              theme='primary'
              onClick={this.handleSave}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
          </div>
        </div>
      </bk-sideslider>
    );
  }

  // 单位处理逻辑
  private getUnits() {
    if (this.unitConfig.mode === ALL_OPTION) return this.unitList;

    return Array.from(
      this.unitConfig.checkedList
        .reduce((map, [name, child]) => {
          const unit = map.get(name) || { id: name, name, formats: [] };
          unit.formats.push({ id: child, name: child });
          return map.set(name, unit);
        }, new Map())
        .values()
    );
  }

  // 渲染辅助方法
  private renderStatusPoint(row: IMetricItem) {
    const status = statusMap.get(!!row.disabled);
    return (
      <div
        style={{ background: status.color2 }}
        class='status-point'
      >
        <div
          style={{ background: status.color1 }}
          class='point'
        />
        <span class='status-text'>{status.name}</span>
      </div>
    );
  }

  private renderSwitch(row: IMetricItem, field: 'enabled' | 'hidden') {
    return (
      <div class='switch-wrap'>
        <bk-switcher
          v-model={row[field]}
          size='small'
          theme='primary'
          onChange={() => this.handleSwitchChange(row, field)}
        />
      </div>
    );
  }

  // 表格列渲染逻辑
  private renderNameColumn(props: { row: IMetricItem }) {
    return (
      <span
        class='name'
        onClick={() => this.showMetricDetail(props.row)}
      >
        {props.row.name || '--'}
      </span>
    );
  }

  private renderDescriptionColumn(props: { row: IMetricItem; $index: number }) {
    return (
      <bk-input
        class={['slider-input', this.inputFocus === props.$index ? 'focus' : '']}
        v-model={props.row.description}
        onBlur={() => (this.inputFocus = -1)}
        onFocus={() => (this.inputFocus = props.$index)}
      />
    );
  }

  private renderUnitColumn(props: { row: IMetricItem }) {
    return (
      <bk-select
        class='slider-select'
        v-model={props.row.unit}
        clearable={false}
        popover-width={180}
        searchable
      >
        {this.units.map(group => (
          <bk-option-group
            key={group.id}
            name={group.name}
          >
            {group.formats.map(opt => (
              <bk-option
                id={opt.id}
                key={opt.id}
                name={opt.name}
              />
            ))}
          </bk-option-group>
        ))}
      </bk-select>
    );
  }

  // 单位配置弹窗
  private renderUnitConfigPopover() {
    return (
      <div slot='content'>
        <div class='unit-config-header'>
          <span>{this.$t('编辑范围')}</span>
          <bk-radio-group v-model={this.localUnitConfig.mode}>
            {RADIO_OPTIONS.map(opt => (
              <bk-radio
                key={opt.id}
                disabled={opt.id === CHECKED_OPTION && !this.localUnitConfig.checkedList.length}
                value={opt.id}
              >
                {opt.label}
              </bk-radio>
            ))}
          </bk-radio-group>
        </div>

        <div class='unit-selection'>
          <bk-cascade
            v-model={this.localUnitConfig.checkedList}
            list={this.unitList.map(item => ({
              ...item,
              id: item.name,
              children: item.formats || [],
            }))}
            multiple
          />
        </div>

        <div class='unit-config-footer'>
          <bk-button
            theme='primary'
            onClick={this.confirmUnitConfig}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button onClick={this.cancelUnitConfig}>{this.$t('取消')}</bk-button>
        </div>
      </div>
    );
  }

  private confirmUnitConfig() {
    this.unitConfig = deepClone(this.localUnitConfig);
    this.units = this.getUnits();
    this.metricSliderPopover.hide();
  }

  private cancelUnitConfig() {
    this.localUnitConfig = deepClone(this.unitConfig);
    this.metricSliderPopover.hide();
  }

  // 其他渲染方法
  private renderAggregateMethod(row: IMetricItem) {
    return (
      <bk-select
        class='slider-select'
        v-model={row.aggregate_method}
        clearable={false}
      >
        {METHOD_LIST.map(m => (
          <bk-option
            id={m.id}
            key={m.id}
            name={m.name}
          />
        ))}
      </bk-select>
    );
  }

  private renderInterval(row: IMetricItem) {
    return (
      <bk-select
        class='slider-select'
        v-model={row.interval}
        clearable={false}
      >
        {this.cycleOption.map(opt => (
          <bk-option
            id={opt.id}
            key={opt.id}
            name={`${opt.name}s`}
          />
        ))}
      </bk-select>
    );
  }

  private renderFunction(row: IMetricItem) {
    return (
      <FunctionMenu
        // class='slider-select'
        list={this.metricFunctions}
      >
        {row.function?.id || '-'}
      </FunctionMenu>
    );
  }

  private renderOperations(props: { $index: number }) {
    return (
      <div class='operations'>
        <i
          class='bk-icon icon-plus-circle-shape'
          onClick={() => this.handleAddRow(props.$index)}
        />
        <i
          class='bk-icon icon-minus-circle-shape'
          onClick={() => this.handleRemoveRow(props.$index)}
        />
      </div>
    );
  }

  // 行操作处理
  private handleAddRow(index: number) {
    this.localTable.splice(index + 1, 0, {});
  }

  private handleRemoveRow(index: number) {
    this.localTable.splice(index, 1);
  }

  private handleSwitchChange(row: IMetricItem, field: string) {
    console.log(`Switch ${field} changed for row ${row.id}:`, row[field]);
  }

  private showMetricDetail(metric: IMetricItem) {
    console.log('Show metric detail:', metric);
  }
}
