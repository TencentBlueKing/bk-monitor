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

const { i18n: I18N } = window;

import dayjs from 'dayjs';

// import EmptyStatus from '../../../components/empty-status/empty-status';
import TableSkeleton from '../../../components/skeleton/table-skeleton';

import './indicator-table.scss';

@Component
export default class IndicatorTable extends tsc<any, any> {
  table = {
    data: [
      {
        id: '123',
      },
    ],
    loading: false,
    select: [],
  };
  pageCount = 10;

  loading = false;

  fieldSettingData: any = {};
  flag = false;
  tableInstance = {
    total: 0,
    data: [],
    keyword: '',
    page: 1,
    pageSize: 10,
    pageList: [10, 20, 50, 100],
    getTableData: () => [],
    setDefaultStore: () => { },
    getItemDescription: () => [],
  };

  header = {
    value: 0,
    dropdownShow: false,
    list: [
      // { id: 0, name: I18N.t('修改告警组') },
      { id: 1, name: I18N.t('修改触发条件') },
      { id: 5, name: I18N.t('修改恢复条件') },
      // { id: 2, name: I18N.t('修改通知间隔') },
      { id: 3, name: I18N.t('修改无数据告警') },
      // { id: 4, name: I18N.t('修改告警恢复通知') },
      { id: 6, name: I18N.t('启/停策略') },
      { id: 7, name: I18N.t('删除策略') },
      // { id: 9, name: I18N.t('修改告警模版') },
      { id: 8, name: I18N.t('增删目标') },
      { id: 10, name: I18N.t('修改标签') },
      // { id: 11, name: I18N.t('修改处理套餐') }
      { id: 21, name: I18N.t('修改算法') },
      { id: 12, name: I18N.t('修改生效时间段') },
      { id: 13, name: I18N.t('修改处理套餐') },
      { id: 14, name: I18N.t('修改告警组') },
      { id: 15, name: I18N.t('修改通知场景') },
      { id: 20, name: I18N.t('修改通知升级') },
      { id: 16, name: I18N.t('修改通知间隔') },
      { id: 17, name: I18N.t('修改通知模板') },
      { id: 18, name: I18N.t('修改告警风暴开关') },
      { id: 19, name: I18N.t('As Code') },
      { id: 22, name: I18N.t('导入/导出') },
    ],
    keyword: '',
    keywordObj: [], // 搜索框绑定值
    condition: [], // 搜索条件接口参数
    conditionList: [], // 搜索可选项
    handleSearch: () => { },
  };

  get isFta() {
    return false;
  }

  emptyType = 'empty'; // 空状态

  created() {
    this.fieldSettingData = {
      id: {
        checked: true,
        disable: true,
        name: 'ID',
        id: 'id',
      },
      strategyName: {
        checked: true,
        disable: true,
        name: this.$t('策略名'),
        id: 'strategyName',
      },
      dataOrigin: {
        checked: false,
        disable: false,
        name: this.$t('数据来源'),
        id: 'dataOrigin',
      },
      target: {
        checked: !this.isFta,
        disable: this.isFta,
        name: this.$t('监控目标'),
        id: 'target',
      },
      labels: {
        checked: true,
        disable: false,
        name: this.$t('标签'),
        id: 'labels',
      },
      noticeGroupList: {
        checked: true,
        disable: false,
        name: this.$t('告警组'),
        id: 'noticeGroupList',
      },
      updator: {
        checked: false,
        disable: false,
        name: this.$t('更新记录'),
        id: 'updator',
      },
      enabled: {
        checked: true,
        disable: true,
        name: this.$t('启/停'),
        id: 'enabled',
      },
      dataTypeLabelName: {
        checked: false,
        disable: false,
        name: this.$t('策略类型'),
        id: 'dataTypeLabelName',
      },
      intervalNotifyMode: {
        checked: false,
        disable: false,
        name: this.$t('通知间隔类型'),
        id: 'intervalNotifyMode',
      },
      dataMode: {
        checked: false,
        disable: false,
        name: this.$t('查询类型'),
        id: 'dataMode',
      },
      notifyInterval: {
        checked: false,
        disable: false,
        name: this.$t('通知间隔'),
        id: 'notifyInterval',
      },
      trigger: {
        checked: false,
        disable: false,
        name: this.$t('触发条件'),
        id: 'trigger',
      },
      recovery: {
        checked: false,
        disable: false,
        name: this.$t('恢复条件'),
        id: 'recovery',
      },
      needPoll: {
        checked: false,
        disable: false,
        name: this.$t('告警风暴'),
        id: 'needPoll',
      },
      noDataEnabled: {
        checked: false,
        disable: false,
        name: this.$t('无数据'),
        id: 'noDataEnabled',
      },
      signals: {
        checked: false,
        disable: false,
        name: this.$t('通知场景'),
        id: 'signals',
      },
      levels: {
        checked: false,
        disable: false,
        name: this.$t('级别'),
        id: 'levels',
      },
      detectionTypes: {
        checked: false,
        disable: false,
        name: this.$t('检测规则类型'),
        id: 'detectionTypes',
      },
      mealNames: {
        checked: false,
        disable: false,
        name: this.$t('处理套餐'),
        id: 'mealNames',
      },
      configSource: {
        checked: false,
        disable: false,
        name: this.$t('配置来源'),
        id: 'configSource',
      },
      app: {
        checked: false,
        disable: false,
        name: this.$t('配置分组'),
        id: 'app',
      },
      operator: {
        checked: true,
        disable: true,
        name: this.$t('操作'),
        id: 'operator',
      },
    };
  }

  getTableComponent() {
    const idSlot = {
      default: props => <span onClick={() => (this.flag = !this.flag)}>{props.row.id}</span>,
    };
    const strategyNameSlot = {
      /* 策略名称 */
      default: props => (
        <div class='col-name'>
          <div class='col-name-desc'>
            <span
              class='col-name-desc-text'
              v-bk-tooltips={{
                content: props.row.strategyName,
                boundary: 'window',
                delay: 200,
                allowHTML: false,
              }}
            >
              <router-link
                class='name-text-link'
                to={{
                  name: 'strategy-config-detail',
                  params: {
                    title: props.row.strategyName,
                    id: props.row.id,
                  },
                }}
              >
                {props.row.strategyName}
              </router-link>
            </span>
            {[
              props.row.isInvalid ? (
                <i
                  key={1}
                  class='icon-monitor icon-shixiao'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${props.row.invalidType}`,
                    allowHTML: false,
                  }}
                />
              ) : undefined,
              props.row.abnormalAlertCount > 0 && !props.row.isInvalid ? (
                <span
                  key={2}
                  class='alert-tag red'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('当前有{n}个未恢复事件', { n: props.row.abnormalAlertCount })}`,
                    allowHTML: false,
                  }}
                // onClick={modifiers.stop(() => this.handleToEventCenter(props.row))}
                >
                  <i class='icon-monitor icon-mc-chart-alert' />
                  <span class='alert-count'>{props.row.abnormalAlertCount}</span>
                </span>
              ) : undefined,
              props.row.shieldAlertCount ? (
                <span
                  key={3}
                  class='alert-tag grey'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('当前有{n}个已屏蔽事件', { n: props.row.shieldAlertCount })}`,
                    allowHTML: false,
                  }}
                // onClick={modifiers.stop(() => this.handleToEventCenter(props.row, 'SHIELDED_ABNORMAL'))}
                >
                  <i class='icon-monitor icon-menu-shield' />
                  <span class='alert-count'>{props.row.shieldAlertCount}</span>
                </span>
              ) : undefined,
              props.row.shieldInfo?.shield_ids?.length ? (
                <span
                  key={4}
                  class='alert-tag wuxian'
                  v-bk-tooltips={{
                    placements: ['right'],
                    boundary: 'window',
                    content: `${this.$t('整个策略已被屏蔽')}`,
                  }}
                // onClick={() => this.handleToAlarmShield(props.row.shieldInfo.shield_ids)}
                >
                  <i class='icon-monitor icon-menu-shield' />
                  {/* <SvgIcon
                    class='wu-xian-text'
                    iconName={'wuqiong'}
                  /> */}
                </span>
              ) : undefined,
            ]}
          </div>
          <div class='col-name-type'>{props.row.scenarioDisplayName}</div>
        </div>
      ),
    };
    const dataOriginSlot = {
      /* 数据来源 */ default: props => <span>{props.row.dataOrigin}</span>,
    };
    const targetSlot = {
      default: props => (
        <div class='col-name'>
          <div class='col-name-label'>{props.row.target || this.$t('默认全部')}</div>
        </div>
      ),
    };
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
            {props.row[type].map((item, index) => (
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
    const labelsSlot = {
      /* 标签 */
      default: props => (
        <div class='col-classifiy'>
          {props.row.labels.length > 0 ? (
            <div
              ref={`table-labels-${props.$index}`}
              class='col-classifiy-wrap'
            >
              {props.row.labels.map((item, index) => (
                <span
                  key={`${item}-${index}`}
                  class='classifiy-label gray'
                  v-bk-overflow-tips
                >
                  <span class='text-overflow'>{item}</span>
                </span>
              ))}
              {props.row.overflowLabel ? (
                <span
                  class='classifiy-overflow gray'
                  v-bk-tooltips={{
                    placements: ['top-start'],
                    boundary: 'window',
                    content: () => props.row.labels.join('、 '),
                    delay: 200,
                    allowHTML: false,
                    extCls: 'ext-cls',
                  }}
                >
                  +{props.row.overflowLabelCount}
                </span>
              ) : undefined}
            </div>
          ) : (
            <div>--</div>
          )}
        </div>
      ),
    };
    const signalsSlot = {
      /* 通知场景 */ default: props => overflowGroupDom(props, 'signals'),
    };
    const levelsSlot = {
      /* 级别 */ default: props => overflowGroupDom(props, 'levels'),
    };
    const detectionTypesSlot = {
      /* 检测规则类型 */ default: props => overflowGroupDom(props, 'detectionTypes'),
    };
    const mealNamesSlot = {
      /* 处理套餐 */
      default: props => {
        const tip = props.row.mealTips.length
          ? `<span>
          ${props.row.mealTips.map(item => `<div>${item}</div>`).join('')}
        </span>`
          : '';
        return overflowGroupDom(props, 'mealNames', tip);
      },
    };
    const updatorSlot = {
      /* 更新记录 */
      default: props => (
        <div class='col-name'>
          <div class='col-name-label'>{props.row.updator || '--'}</div>
          <div>{dayjs.tz(props.row.updateTime).format('YYYY-MM-DD HH:mm:ss') || '--'}</div>
        </div>
      ),
    };
    const enabledDom = (props, type: 'enabled' | 'needPoll' | 'noDataEnabled' /* 通用开关样式 */) => (
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
    const enabledSlot = {
      /* 启停 */ default: props => enabledDom(props, 'enabled'),
    };
    const needPollSlot = {
      /* 告警风暴 */ default: props => enabledDom(props, 'needPoll'),
    };
    const noDataEnabledSlot = {
      /* 无数据启停 */ default: props => enabledDom(props, 'noDataEnabled'),
    };
    const recoverySlot = {
      /* 恢复条件 */
      default: props => (
        <span
          v-bk-tooltips={{
            placements: ['top-start'],
            boundary: 'boundary',
            // content: () =>
            //   this.$t('连续{0}个周期内不满足触发条件{1}', [
            //     props.row.recovery,
            //     !isRecoveryDisable(props.row.queryConfigs) && isStatusSetterNoData(props.row.recoveryStatusSetter)
            //       ? this.$t('或无数据')
            //       : '',
            //   ]),
            disabled: props.row.recovery === '--' /* 兼容关联告警 */,
            delay: 200,
            allowHTML: false,
          }}
        >
          {props.row.recovery}
        </span>
      ),
    };
    const triggerSlot = {
      /* 触发条件 */
      default: props => (
        <span
          v-bk-tooltips={{
            placements: ['top-start'],
            boundary: 'boundary',
            content: () =>
              props.row.triggerConfig
                ? this.$t(/* 兼容关联告警 */ '在{0}个周期内{1}满足{2}次检测算法，触发告警通知', [
                  props.row.triggerConfig.check_window,
                  this.$t('累计'),
                  props.row.triggerConfig.count,
                ])
                : '',
            disabled: !props.row.triggerConfig,
            delay: 200,
            allowHTML: false,
          }}
        >
          {props.row.trigger}
        </span>
      ),
    };
    const configSourceSlot = {
      /* 配置来源 */ default: props => props.row.configSource || '--',
    };
    const appSlot = {
      /* 配置分组 */ default: props => props.row.app || '--',
    };
    const {
      id,
      strategyName,
      dataOrigin,
      target,
      updator,
      enabled,
      dataTypeLabelName,
      intervalNotifyMode,
      dataMode,
      notifyInterval,
      trigger,
      recovery,
      needPoll,
      noDataEnabled,
      signals,
      levels,
      detectionTypes,
      mealNames,
      configSource,
      app,
    } = this.fieldSettingData;
    return (
      <bk-table
        ref='strategyTable'
        class='strategy-table'
        v-bkloading={{ isLoading: this.table.loading }}
        empty-text={this.$t('无数据')}
        // on={{
        //   'hook:mounted': this.handleTableMountedOrActivated,
        //   'hook:activated': this.handleTableMountedOrActivated,
        // }}
        // on-header-dragend={this.handleHeaderDragend}
        // on-selection-change={this.handleSelectionChange}
        {...{
          props: {
            data: this.table.data,
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
        <bk-table-column
          width='50'
          align='center'
          type='selection'
        />
        {id.checked && (
          <bk-table-column
            key='id'
            width='75'
            label='ID'
            prop='id'
            scopedSlots={idSlot}
          />
        )}
        {strategyName.checked && (
          <bk-table-column
            key='strategyName'
            label={this.$t('策略名')}
            min-width='200'
            scopedSlots={strategyNameSlot}
          />
        )}
        {dataOrigin.checked && (
          <bk-table-column
            key='dataOrigin'
            width='110'
            label={this.$t('数据来源')}
            scopedSlots={dataOriginSlot}
          />
        )}
        {target.checked && (
          <bk-table-column
            key='target'
            width='150'
            label={this.$t('监控目标')}
            scopedSlots={targetSlot}
          />
        )}
        {updator.checked && (
          <bk-table-column
            key='updator'
            width='150'
            label={this.$t('更新记录')}
            scopedSlots={updatorSlot}
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
        {dataTypeLabelName.checked && (
          <bk-table-column
            key='dataTypeLabelName'
            width='80'
            label={this.$t('策略类型')}
            scopedSlots={{ default: props => props.row.dataTypeLabelName }}
          />
        )}
        {intervalNotifyMode.checked && (
          <bk-table-column
            key='intervalNotifyMode'
            width='105'
            label={this.$t('通知间隔类型')}
            scopedSlots={{ default: props => props.row.intervalNotifyMode }}
          />
        )}
        {dataMode.checked && (
          <bk-table-column
            key='dataMode'
            width='105'
            label={this.$t('查询类型')}
            scopedSlots={{ default: props => props.row.dataMode }}
          />
        )}
        {notifyInterval.checked && (
          <bk-table-column
            key='notifyInterval'
            width='105'
            label={this.$t('通知间隔')}
            scopedSlots={{ default: props => `${props.row.notifyInterval}${this.$t('分钟')}` }}
          />
        )}
        {trigger.checked && (
          <bk-table-column
            key='trigger'
            width='105'
            label={this.$t('触发条件')}
            scopedSlots={triggerSlot}
          />
        )}
        {recovery.checked && (
          <bk-table-column
            key='recovery'
            width='105'
            label={this.$t('恢复条件')}
            scopedSlots={recoverySlot}
          />
        )}
        {needPoll.checked && (
          <bk-table-column
            key='needPoll'
            width='80'
            label={this.$t('告警风暴')}
            scopedSlots={needPollSlot}
          />
        )}
        {noDataEnabled.checked && (
          <bk-table-column
            key='noDataEnabled'
            width='80'
            label={this.$t('无数据')}
            scopedSlots={noDataEnabledSlot}
          />
        )}
        {signals.checked && (
          <bk-table-column
            key='signals'
            width='150'
            label={this.$t('通知场景')}
            scopedSlots={signalsSlot}
          />
        )}
        {levels.checked && (
          <bk-table-column
            key='levels'
            width='150'
            label={this.$t('级别')}
            scopedSlots={levelsSlot}
          />
        )}
        {detectionTypes.checked && (
          <bk-table-column
            key='detectionTypes'
            width='150'
            label={this.$t('检测规则类型')}
            scopedSlots={detectionTypesSlot}
          />
        )}
        {mealNames.checked && (
          <bk-table-column
            key='mealNames'
            width='150'
            label={this.$t('处理套餐')}
            scopedSlots={mealNamesSlot}
          />
        )}
        {configSource.checked && (
          <bk-table-column
            key='configSource'
            width='100'
            label={this.$t('配置来源')}
            scopedSlots={configSourceSlot}
          />
        )}
        {app.checked && (
          <bk-table-column
            key='app'
            width='100'
            label={this.$t('配置分组')}
            scopedSlots={appSlot}
          />
        )}
      </bk-table>
    );
  }
  render() {
    return (
      <div class='content-right'>
        <div class='indicator-table-header'>
          {/* <bk-badge
            class='badge'
            // v-show={!this.showFilterPanel}
            theme='success'
            // visible={this.header.keywordObj.length !== 0}
            dot
          >
            <span
              class='folding'
              onClick={() => { }}
            >
              <i class='icon-monitor icon-double-up' />
            </span>
          </bk-badge> */}
          <bk-button
            class='header-btn'
            // v-authority={{ active: !this.authority.MANAGE_AUTH }}
            theme='primary'
            onClick={() => { }}
          >
            {this.$t('编辑')}
          </bk-button>
          <bk-dropdown-menu
            class='header-select'
            // disabled={!this.table.select.length}
            trigger='click'
          // on-hide={() => (this.header.dropdownShow = false)}
          // on-show={() => (this.header.dropdownShow = true)}
          >
            <div
              class={['header-select-btn', { 'btn-disabled': !this.table.select.length }]}
              slot='dropdown-trigger'
            >
              <span class='btn-name'> {this.$t('批量操作')} </span>
              <i class={['icon-monitor', this.header.dropdownShow ? 'icon-arrow-up' : 'icon-arrow-down']} />
            </div>
            <ul
              class='header-select-list'
              slot='dropdown-content'
            >
              {/* 批量操作监控目标需要选择相同类型的监控对象 */}
              {this.header.list.map((option, index) => (
                <li
                  key={index}
                  // class={['list-item', { disabled: this.isBatchItemDisabled(option) }]}
                  v-bk-tooltips={{
                    placement: 'right',
                    boundary: 'window',
                    // disabled: !this.isBatchItemDisabled(option),
                    // content: () => this.batchItemDisabledTip(option),
                    delay: 200,
                    allowHTML: false,
                  }}
                  onClick={() => { }}
                >
                  {option.name}
                </li>
              ))}
            </ul>
          </bk-dropdown-menu>
          自动发现
        </div>
        <div class='strategy-config-wrap'>
          <div class='config-wrap-setting'>
            {/* <bk-popover
              width='515'
              ext-cls='strategy-table-setting'
              offset='0, 20'
              placement='bottom'
              theme='light strategy-setting'
              trigger='click'
            >
              <div class='setting-btn'>
                <i class='icon-monitor icon-menu-set' />
              </div>
              <div
                class='tool-popover'
                slot='content'
              >
                <div class='tool-popover-title'>
                  {this.$t('字段显示设置')}
                  <bk-checkbox
                    class='all-selection'
                  // value={this.fieldAllSelected}
                  // onChange={this.handleFieldAllSelected}
                  >
                    {this.$t('全选')}
                  </bk-checkbox>
                </div>
                <ul class='tool-popover-content'>
                  {Object.keys(this.fieldSettingData).map(key => (
                    <li
                      key={this.fieldSettingData[key].id}
                      class='tool-popover-content-item'
                    >
                      <bk-checkbox
                        disabled={this.fieldSettingData[key].disable}
                        value={this.fieldSettingData[key].checked}
                      // onChange={() => this.handleCheckColChange(this.fieldSettingData[key])}
                      >
                        {this.fieldSettingData[key].name}
                      </bk-checkbox>
                    </li>
                  ))}
                </ul>
              </div>
            </bk-popover> */}
          </div>
          {/* {this.authLoading || this.table.loading || this.loading ? ( */}
          {this.loading ? (
            <TableSkeleton type={2} />
          ) : (
            [
              this.getTableComponent(),
              this.table.data?.length ? (
                <bk-pagination
                  key='table-pagination'
                  class='strategy-pagination list-pagination'
                  v-show={this.tableInstance.total}
                  align='right'
                  count={this.pageCount}
                  current={this.tableInstance.page}
                  limit={this.tableInstance.pageSize}
                  limit-list={this.tableInstance.pageList}
                  size='small'
                  pagination-able
                  show-total-count
                // on-change={this.handlePageChange}
                // on-limit-change={this.handleLimitChange}
                />
              ) : undefined,
            ]
          )}
          <div class={['detail', this.flag ? 'detail-active' : '']}>{/* TODO */}</div>
        </div>
      </div>
    );
  }
}
