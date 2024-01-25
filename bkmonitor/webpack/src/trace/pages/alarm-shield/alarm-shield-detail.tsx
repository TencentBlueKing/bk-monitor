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
import { defineComponent, inject, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import { Button, Loading, Sideslider, Table } from 'bkui-vue';

import { getNoticeWay } from '../../../monitor-api/modules/notice_group';
import { frontendShieldDetail } from '../../../monitor-api/modules/shield';
import { getStrategyV2 } from '../../../monitor-api/modules/strategies';
import { random } from '../../../monitor-common/utils';
import HistoryDialog from '../../components/history-dialog/history-dialog';
import { useAppStore } from '../../store/modules/app';
import { IAuthority } from '../../typings/authority';

import FormItem from './components/form-item';
import StrategyDetail from './components/strategy-detail';
import WhereDisplay from './components/where-display';

import './alarm-shield-detail.scss';

const detailFn = () => ({
  biz: '',
  bizName: '',
  status: '',
  cycleConfig: {
    type: 1,
    startTime: '',
    endTime: '',
    dayList: '',
    weekList: ''
  },
  beginTime: '',
  endTime: '',
  description: '',
  shieldNotice: false,
  category: ''
});

const noticeConfigFn = () => ({
  receiver: [],
  way: '',
  time: ''
});

const scopeDataFn = () => ({
  type: '',
  tableData: [],
  biz: ''
});
const strategyDataFn = () => ({
  strategys: [],
  strategyData: null,
  dimensionCondition: {
    conditionKey: random(8),
    dimensionList: [], // 维度列表
    metricMeta: null, // 获取条件候选值得参数
    conditionList: [], // 维度条件数据
    allNames: {} // 维度名合集
  },
  scope: {
    tableData: [],
    type: ''
  }
});

const dimensionDataFn = () => ({
  conditionKey: random(8),
  dimensionList: [], // 维度列表
  metricMeta: null, // 获取条件候选值得参数
  conditionList: [], // 维度条件数据
  allNames: {} // 维度名合集
});

const eventDataFn = () => ({
  strategys: [],
  dimensions: '',
  eventMessage: ''
});

export default defineComponent({
  name: 'AlarmShieldDetail',
  props: {
    show: {
      type: Boolean,
      default: false
    },
    id: {
      type: [Number, String],
      default: ''
    },
    onShowChange: {
      type: Function,
      default: _v => {}
    }
  },
  setup(props) {
    const { t } = useI18n();
    const store = useAppStore();
    const router = useRouter();

    const authority = inject<IAuthority>('authority');

    const statusColorMap = {
      1: {
        text: t('屏蔽中'),
        color: '#63656E'
      },
      2: {
        text: t('已过期'),
        color: '#C4C6CC'
      },
      3: {
        text: t('被解除'),
        color: '#FF9C01'
      }
    };
    const scopeLabelMap = {
      ip: t('主机'),
      instance: t('服务实例'),
      node: t('节点名称'),
      biz: t('业务')
    };
    const cycleMap = ['', t('单次'), t('每天'), t('每周'), t('每月')];
    const weekListMap = ['', t('星期一'), t('星期二'), t('星期三'), t('星期四'), t('星期五'), t('星期六'), t('星期日')];
    const historyList = ref([]);

    /**
     * @description 详情数据
     */
    const detail = ref(detailFn());
    const noticeConfig = ref(noticeConfigFn());

    /* 范围屏蔽数据 */
    const scopeData = ref(scopeDataFn());
    /* 策略屏蔽数据 */
    const strategyData = ref(strategyDataFn());
    /* 维度屏蔽 */
    const dimensionData = ref(dimensionDataFn());
    /* 告警事件屏蔽 */
    const eventData = ref(eventDataFn());

    const loading = ref(false);

    watch(
      () => props.show,
      show => {
        if (show) {
          init();
        } else {
          detail.value = detailFn();
          noticeConfig.value = noticeConfigFn();
          scopeData.value = scopeDataFn();
          strategyData.value = strategyDataFn();
          dimensionData.value = dimensionDataFn();
          eventData.value = eventDataFn();
        }
      }
    );
    /**
     * @description 关闭侧栏
     */
    function handleClosed() {
      props.onShowChange(false);
    }

    /**
     * @description 初始化
     */
    async function init() {
      loading.value = true;
      const data = await frontendShieldDetail({ id: props.id });
      historyList.value = [
        { label: t('创建人'), value: data.create_user || '--' },
        { label: t('创建时间'), value: data.create_time || '--' },
        { label: t('最近更新人'), value: data.update_user || '--' },
        { label: t('修改时间'), value: data.update_time || '--' }
      ];
      const bizItem = store.bizList.filter(item => data.bk_biz_id === item.id);
      const detailData = detailFn();
      detailData.biz = data.bk_biz_id;
      detailData.bizName = bizItem[0].text;
      detailData.status = data.status;
      /* 屏蔽周期 */
      const weekList = data.cycle_config.week_list.map(item => weekListMap[item]);
      detailData.cycleConfig = {
        type: data.cycle_config.type,
        startTime: data.cycle_config.begin_time,
        endTime: data.cycle_config.end_time,
        dayList: data.cycle_config.day_list.join('、'),
        weekList: weekList.join('、')
      };
      detailData.beginTime = data.begin_time;
      detailData.endTime = data.end_time;
      detailData.description = data.description;
      detailData.shieldNotice = data.shield_notice;
      detailData.category = data.category;
      detail.value = { ...detail.value, ...detailData };
      /* 范围屏蔽 */
      const scopeDataTemp = scopeDataFn();
      if (data.category === 'scope') {
        scopeDataTemp.type = data.scope_type;
        if (data.scope_type === 'biz') {
          scopeDataTemp.biz = data.dimension_config.target.join(',');
        } else {
          scopeDataTemp.tableData = data.dimension_config.target.map(item => ({ name: item }));
        }
      }
      scopeData.value = { ...scopeData.value, ...scopeDataTemp };
      /* 策略屏蔽 */
      const strategyDataTemp = strategyDataFn();
      if (data.category === 'strategy') {
        strategyDataTemp.strategys = data.dimension_config.strategies.map(item => ({
          name: item.name,
          id: item.id
        }));
        strategyDataTemp.dimensionCondition.conditionList = data.dimension_config.dimension_conditions.map(item => ({
          ...item,
          dimensionName: item.name || item.key
        }));
        strategyDataTemp.dimensionCondition.conditionList.forEach(item => {
          strategyDataTemp.dimensionCondition.allNames[item.key] = item.name || item.key;
        });
        strategyDataTemp.dimensionCondition.conditionKey = random(8);
        if (data.dimension_config.strategies.length === 1) {
          getStrategyV2({ id: data.dimension_config.strategies[0].id }).then(data => {
            strategyDataTemp.strategyData = data;
          });
        }
        strategyDataTemp.scope.tableData = data.dimension_config?.target?.map(item => ({ name: item })) || [];
        strategyDataTemp.scope.type = data.scope_type;
      }
      strategyData.value = { ...strategyData.value, ...strategyDataTemp };
      /* 维度屏蔽 */
      const dimensionDataTemp = dimensionDataFn();
      if (data.category === 'dimension') {
        dimensionDataTemp.conditionList = data.dimension_config.dimension_conditions.map(item => ({
          ...item,
          dimensionName: item.name || item.key
        }));
        dimensionDataTemp.conditionList.forEach(item => {
          dimensionDataTemp.allNames[item.key] = item.name || item.key;
        });
        dimensionDataTemp.conditionKey = random(8);
      }
      dimensionData.value = { ...dimensionData.value, ...dimensionDataTemp };
      /* 告警事件 */
      const eventDataTemp = eventDataFn();
      if (data.category === 'alert') {
        eventDataTemp.strategys = data.dimension_config.strategies.map(item => ({
          name: item.name,
          id: item.id
        }));
        eventDataTemp.dimensions = data.dimension_config.dimensions;
        eventDataTemp.eventMessage = data.dimension_config.event_message;
      }
      eventData.value = { ...eventData.value, ...eventDataTemp };
      /* 通知设置 */
      if (data.shield_notice) {
        const noticeWay = await getNoticeWay();
        const way = data.notice_config.notice_way.map(item => {
          const res = noticeWay.find(el => el.type === item);
          return res.label;
        });
        const noticeConfigData = noticeConfigFn();
        noticeConfigData.receiver = data.notice_config.notice_receiver;
        noticeConfigData.way = way.join('；');
        noticeConfigData.time = data.notice_config.notice_time;
        noticeConfig.value = { ...noticeConfig.value, ...noticeConfigData };
      }
      loading.value = false;
    }
    /**
     * @description 跳转到策略
     * @param id
     */
    function handleToStrategy(id) {
      const url = `${location.origin}${location.pathname}?bizId=${detail.value.biz}#/strategy-config/edit/${id}`;
      window.open(url);
    }

    function handleToEdit() {
      router.push({
        name: 'alarm-shield-edit',
        params: {
          id: props.id
        }
      });
    }

    return {
      detail,
      store,
      authority,
      t,
      handleClosed,
      handleToEdit,
      historyList,
      statusColorMap,
      scopeData,
      scopeLabelMap,
      strategyData,
      handleToStrategy,
      dimensionData,
      eventData,
      cycleMap,
      noticeConfig,
      loading
    };
  },
  render() {
    return (
      <Sideslider
        extCls={'alarm-shield-detail-side'}
        isShow={this.show}
        quickClose={true}
        width={640}
        onClosed={this.handleClosed}
      >
        {{
          header: () => (
            <div class='alarm-shield-detail-header'>
              <span class='header-left'>{`#${this.id} ${this.t('详情')}`}</span>
              <span class='header-right'>
                <Button
                  class='mr-8'
                  theme='primary'
                  outline
                  onClick={() =>
                    this.authority.auth.MANAGE_AUTH
                      ? this.handleToEdit()
                      : this.authority.showDetail([this.authority.map.MANAGE_AUTH])
                  }
                  v-authority={{ active: !this.authority.auth.MANAGE_AUTH }}
                >
                  {this.t('编辑')}
                </Button>
                <HistoryDialog list={this.historyList}></HistoryDialog>
              </span>
            </div>
          ),
          default: () => (
            <Loading loading={this.loading}>
              <div class='alarm-shield-detail-content'>
                <FormItem label={this.t('所属')}>
                  <span class='detail-text'>{this.detail.bizName}</span>
                </FormItem>
                <FormItem label={this.t('屏蔽状态')}>
                  <span
                    class='detail-text'
                    style={{
                      color: this.statusColorMap[this.detail.status]?.color
                    }}
                  >
                    {this.statusColorMap[this.detail.status]?.text}
                  </span>
                </FormItem>
                {(() => {
                  if (this.detail.category === 'scope') {
                    return (
                      <>
                        <FormItem label={this.t('屏蔽范围')}>
                          <div class='scope-content'>
                            {this.scopeData.type !== 'biz' ? (
                              <div>
                                <Table
                                  data={this.scopeData.tableData}
                                  maxHeight={450}
                                  border={['outer']}
                                  columns={[
                                    {
                                      id: 'name',
                                      label: () => this.scopeLabelMap[this.scopeData.type],
                                      render: ({ row }) => row.name
                                    }
                                  ]}
                                ></Table>
                              </div>
                            ) : (
                              <span>{this.scopeData.biz}</span>
                            )}
                          </div>
                        </FormItem>
                      </>
                    );
                  }
                  if (this.detail.category === 'strategy') {
                    return (
                      <>
                        <FormItem label={this.t('屏蔽策略')}>
                          <span class='detail-text strategy-list'>
                            {this.strategyData.strategys.map((item, index) => (
                              <span
                                key={index}
                                class='strategy-item'
                              >
                                {item.name}
                                <span
                                  class='icon-monitor icon-fenxiang'
                                  onClick={() => this.handleToStrategy(item.id)}
                                ></span>
                                {index + 1 !== this.strategyData.strategys.length && <span>&nbsp;,</span>}
                              </span>
                            ))}
                          </span>
                        </FormItem>
                        {!!this.strategyData.strategyData && (
                          <FormItem label={this.t('告警内容')}>
                            <StrategyDetail
                              class='mt-9'
                              simple={true}
                              strategyData={this.strategyData.strategyData}
                            ></StrategyDetail>
                          </FormItem>
                        )}
                        {!!this.strategyData.dimensionCondition.conditionList.length && (
                          <FormItem label={this.t('维度条件')}>
                            <span class='detail-text'>
                              <WhereDisplay
                                value={this.strategyData.dimensionCondition.conditionList}
                                readonly={true}
                                allNames={this.strategyData.dimensionCondition.allNames}
                                key={this.strategyData.dimensionCondition.conditionKey}
                              ></WhereDisplay>
                            </span>
                          </FormItem>
                        )}
                        <FormItem label={this.t('屏蔽范围')}>
                          {!!this.strategyData.scope.tableData.length ? (
                            <div class='scope-content'>
                              <div>
                                <Table
                                  data={this.strategyData.scope.tableData}
                                  maxHeight={450}
                                  border={['outer']}
                                  columns={[
                                    {
                                      id: 'name',
                                      label: () => this.scopeLabelMap[this.strategyData.scope.type],
                                      render: ({ row }) => row.name
                                    }
                                  ]}
                                ></Table>
                              </div>
                            </div>
                          ) : (
                            <span class='detail-text'>--</span>
                          )}
                        </FormItem>
                      </>
                    );
                  }
                  if (this.detail.category === 'dimension') {
                    return (
                      <FormItem label={this.t('维度条件')}>
                        <span class='detail-text'>
                          <WhereDisplay
                            value={this.dimensionData.conditionList}
                            readonly={true}
                            allNames={this.dimensionData.allNames}
                            key={this.dimensionData.conditionKey}
                          ></WhereDisplay>
                        </span>
                      </FormItem>
                    );
                  }
                  if (this.detail.category === 'alert') {
                    return (
                      <>
                        <FormItem label={this.t('屏蔽策略')}>
                          <span class='detail-text strategy-list'>
                            {this.eventData.strategys.map((item, index) => (
                              <span
                                key={index}
                                class='strategy-item'
                              >
                                {item.name}
                                <span
                                  class='icon-monitor icon-fenxiang'
                                  onClick={() => this.handleToStrategy(item.id)}
                                ></span>
                                {index + 1 !== this.eventData.strategys.length && <span>&nbsp;,</span>}
                              </span>
                            ))}
                          </span>
                        </FormItem>
                        <FormItem label={this.t('告警内容')}>
                          <div class='event-detail-content'>
                            <FormItem label={`${this.t('维度信息')}:`}>
                              <span class='detail-text'>{this.eventData.dimensions}</span>
                            </FormItem>
                            <FormItem label={`${this.t('检测算法')}:`}>
                              <span class='detail-text'>{this.eventData.eventMessage}</span>
                            </FormItem>
                          </div>
                        </FormItem>
                      </>
                    );
                  }
                  return undefined;
                })()}
                <FormItem label={this.t('屏蔽周期')}>
                  <span class='detail-text'>{this.cycleMap[this.detail.cycleConfig?.type]}</span>
                </FormItem>
                <FormItem label={this.t('时间范围')}>
                  {(() => {
                    if (this.detail.cycleConfig.type === 1) {
                      return <span class='detail-text'>{`${this.detail.beginTime} ~ ${this.detail.endTime}`}</span>;
                    }
                    if (this.detail.cycleConfig.type === 2) {
                      return (
                        <span class='detail-text'>
                          {this.t('每天的')}&nbsp;
                          <span class='item-highlight'>{`${this.detail.beginTime} ~ ${this.detail.endTime}`}</span>
                          &nbsp;
                          {this.t('进行告警屏蔽')}
                        </span>
                      );
                    }
                    if (this.detail.cycleConfig.type === 3) {
                      return (
                        <span class='detail-text'>
                          {this.t('每周')}&nbsp;
                          <span class='item-highlight'>{this.detail.cycleConfig.weekList}</span>&nbsp;
                          {this.t('的')}&nbsp;
                          <span class='item-highlight'>{`${this.detail.beginTime} ~ ${this.detail.endTime}`}</span>
                          &nbsp;{this.t('进行告警屏蔽')}
                        </span>
                      );
                    }
                    if (this.detail.cycleConfig.type === 4) {
                      return (
                        <span class='detail-text'>
                          {this.t('每月')}&nbsp;
                          <span class='item-highlight'>{this.detail.cycleConfig.dayList}</span>&nbsp;
                          {this.t('日的')}&nbsp;
                          <span class='item-highlight'>{`${this.detail.cycleConfig.startTime} ~ ${this.detail.cycleConfig.endTime}`}</span>
                          &nbsp;{this.t('进行告警屏蔽')}
                        </span>
                      );
                    }
                    return undefined;
                  })()}
                </FormItem>
                {this.detail.cycleConfig.type !== 1 && (
                  <FormItem label={this.t('日期范围')}>
                    <span class='detail-text mt-9'>{`${this.detail.beginTime} ~ ${this.detail.endTime}`}</span>
                  </FormItem>
                )}
                <FormItem label={this.t('屏蔽原因')}>
                  <span class='detail-text description'>{this.detail.description}</span>
                </FormItem>
                {this.detail.shieldNotice && (
                  <>
                    <FormItem label={this.t('通知对象')}>
                      <span class='detail-text notice-user'>
                        {this.noticeConfig.receiver.map((item, index) => (
                          <div
                            class='personnel-choice'
                            key={index}
                          >
                            {(() => {
                              if (!!item.logo) {
                                return (
                                  <img
                                    src={item.logo}
                                    alt=''
                                  ></img>
                                );
                              }
                              if (!item.logo && item.type === 'group') {
                                return <span class='icon-monitor icon-mc-user-group no-img'></span>;
                              }
                              if (!item.logo && item.type === 'user') {
                                return <span class='icon-monitor icon-mc-user-one no-img'></span>;
                              }
                            })()}
                            <span>{item.display_name}</span>
                          </div>
                        ))}
                      </span>
                    </FormItem>
                    <FormItem label={this.t('通知方式')}>
                      <span class='detail-text'>{this.noticeConfig.way}</span>
                    </FormItem>
                    <FormItem label={this.t('通知时间')}>
                      <span class='detail-text'>
                        <i18n-t keypath={'屏蔽开始/结束前{0}分钟发送通知'}>
                          <span class='item-highlight'>&nbsp;{this.noticeConfig.time}&nbsp;</span>
                        </i18n-t>
                      </span>
                    </FormItem>
                  </>
                )}
              </div>
            </Loading>
          )
        }}
      </Sideslider>
    );
  }
});
