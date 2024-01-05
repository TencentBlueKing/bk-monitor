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
import { Component, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { throttle } from 'throttle-debounce';

import WhereDisplay from '../../../../fta-solutions/pages/event/event-detail/where-display';
import { addShield, editShield } from '../../../../monitor-api/modules/shield';
import { getMetricListV2, getStrategyListV2 } from '../../../../monitor-api/modules/strategies';
import { Debounce, random } from '../../../../monitor-common/utils/utils';
import ShieldDateConfig from '../alarm-shield-components/alarm-shield-date.vue';
import AlarmShieldNotice from '../alarm-shield-components/alarm-shield-notice.vue';
import SimpleConditionInput from '../components/simple-condition-input';

import './alarm-shield-dimension.scss';

interface IProps {
  shieldData?: any;
}
@Component
export default class AlarmShieldDimension extends tsc<IProps> {
  /* 编辑时后台返回的数据 */
  @Prop({ default: () => null, type: Object }) shieldData: any;
  @Ref('selectList') selectListRef: HTMLDivElement;
  @Model('changeCommonDateData', {
    type: Object
  })
  commonDateData!: Object;
  isEdit = false;
  isClone = false;
  biz = {
    list: [],
    value: ''
  };
  strategyId = '';
  strategyItem = null;
  allStrategy = {
    list: [],
    current: 1,
    isEnd: false
  };
  strategyList = [];
  strategyLoading = false;
  strategyPagination = {
    current: 1,
    limit: 10,
    isEnd: false
  };
  metricList = [];

  // 获取变量值的参数
  metricMeta = null;
  // 维度列表
  dimensionList = [];
  // 条件数据
  conditionList = [];
  conditionKey = random(8);
  allNames = {};
  conditionErrMsg = '';
  // 屏蔽原因
  desc = '';
  loading = false;

  throttledScroll: Function = () => {};

  @Watch('shieldData', { immediate: true, deep: true })
  handleShieldData(data) {
    this.isEdit = this.$route.name === 'alarm-shield-edit';
    this.isClone = this.$route.name === 'alarm-shield-clone';
    if (data.id) {
      /* 回填业务 */
      this.biz.value = data.bk_biz_id;
      /* 回填维度条件 */
      if (!this.isClone) {
        this.conditionList = data.dimension_config.dimension_conditions.map(item => ({
          ...item,
          dimensionName: item.name || item.key
        }));
        this.conditionList.forEach(item => {
          this.allNames[item.key] = item.name || item.key;
        });
      }
      this.conditionKey = random(8);
      /* 回填屏蔽周期 */
      const cycleConfig = data.cycle_config;
      const shieldDate: any = {};
      const cycleMap: { 1: string; 2: string; 3: string; 4: string } = { 1: 'single', 2: 'day', 3: 'week', 4: 'month' };
      const type = cycleMap[cycleConfig.type];
      shieldDate.typeEn = type;
      shieldDate[type] = {
        list: [...cycleConfig.day_list, ...cycleConfig.week_list],
        range: [cycleConfig.begin_time, cycleConfig.end_time]
      };
      shieldDate.dateRange = [data.begin_time, data.end_time];
      if (cycleConfig.type === 1) {
        shieldDate[type].range = [data.begin_time, data.end_time];
        shieldDate.dateRange = [];
      }
      const RNoticeDate: any = this.$refs.noticeDate;
      RNoticeDate.setDate(shieldDate);
      /* 屏蔽内容 */
      this.desc = data.description;
      /* 通知设置 */
      const noticeShow = data.shield_notice;
      if (noticeShow) {
        const shieldNoticeData = {
          notificationMethod: data.notice_config.notice_way,
          noticeNumber: data.notice_config.notice_time,
          member: {
            value: data.notice_config.notice_receiver.map(item => item.id)
          }
        };
        const RNotice: any = this.$refs.shieldNotice;
        RNotice.setNoticeData(shieldNoticeData);
      }
    }
  }

  created() {
    this.throttledScroll = throttle(300, false, this.handleScroll);
  }

  async activated() {
    /* 初始化策略信息 */
    this.strategyId = '';
    this.strategyItem = null;
    this.strategyList = [];
    this.strategyPagination = {
      current: 1,
      limit: 10,
      isEnd: false
    };
    this.loading = true;
    /* 初始化业务信息 */
    this.biz.list = this.$store.getters.bizList;
    this.biz.value = this.$store.getters.bizId;
    /* 获取策略列表 */
    this.strategyList = await this.getStrategyList();
    this.allStrategy.list = [...this.strategyList];
    this.loading = false;
  }
  /* 获取策略列表数据 */
  async getStrategyList(serach = '') {
    return await getStrategyListV2({
      conditions: serach
        ? [
            {
              key: 'strategy_name',
              value: [serach]
            }
          ]
        : [],
      order_by: '-update_time',
      page: this.strategyPagination.current,
      page_size: this.strategyPagination.limit,
      type: 'monitor'
    })
      .then(res => res.strategy_config_list)
      .catch(() => []);
  }
  /* 策略列表滚动分页 */
  async handleScroll(e: any) {
    const { scrollHeight, scrollTop, clientHeight } = e.target;
    const isEnd = scrollHeight - scrollTop === clientHeight && scrollTop !== 0;
    if (isEnd && !this.strategyPagination.isEnd) {
      this.strategyPagination.current += 1;
      this.strategyLoading = true;
      const list = await this.getStrategyList();
      if (list.length) {
        this.strategyList.push(...list);
      } else {
        this.strategyPagination.isEnd = true;
      }
      this.allStrategy.list = [...this.strategyList];
      this.allStrategy.current = this.strategyPagination.current;
      this.allStrategy.isEnd = this.strategyPagination.isEnd;
      this.strategyLoading = false;
    }
  }
  /* 弹出列表 */
  handleToggle(v: boolean) {
    if (v) {
      this.strategyList = [...this.allStrategy.list];
      this.strategyPagination.current = this.allStrategy.current;
      this.strategyPagination.isEnd = this.allStrategy.isEnd;
    }
    this.$nextTick(() => {
      if (v) {
        this.selectListRef.addEventListener('scroll', this.throttledScroll as any);
      } else {
        this.selectListRef.removeEventListener('scroll', this.throttledScroll as any);
      }
    });
  }

  /* 选择策略 */
  async handleStrategy(strategyId) {
    this.strategyItem = this.strategyList.find(item => item.id === strategyId);
    const {
      items: [{ query_configs: queryConfigs }]
    } = this.strategyItem;
    if (queryConfigs?.length) {
      const { metric_list: metricList = [] } = await getMetricListV2({
        page: 1,
        page_size: queryConfigs.length,
        // result_table_label: scenario, // 不传result_table_label，避免关联告警出现不同监控对象时报错
        conditions: [{ key: 'metric_id', value: queryConfigs.map(item => item.metric_id) }]
      }).catch(() => ({}));
      this.metricList = metricList;
      const [metricItem] = metricList;
      if (metricItem) {
        this.metricMeta = {
          dataSourceLabel: metricItem.data_source_label,
          dataTypeLabel: metricItem.data_type_label,
          metricField: metricItem.metric_field,
          resultTableId: metricItem.result_table_id,
          indexSetId: metricItem.index_set_id
        };
      } else {
        this.metricMeta = null;
      }
      this.dimensionList = !!this.metricList.length
        ? this.metricList.reduce((pre, cur) => {
            const dimensionList = pre
              .concat(cur.dimensions.filter(item => typeof item.is_dimension === 'undefined' || item.is_dimension))
              .filter((item, index, arr) => arr.map(item => item.id).indexOf(item.id, 0) === index);
            return dimensionList;
          }, [])
        : [];
      this.conditionKey = random(8);
    }
  }

  /* 搜索策略 */
  @Debounce(300)
  async searchStrategy(v: string) {
    this.strategyLoading = true;
    this.strategyPagination.current = 1;
    this.strategyPagination.isEnd = false;
    this.strategyList = await this.getStrategyList(v);
    this.strategyLoading = false;
    return this.metricList;
  }

  /* 维度条件校验 */
  conditionValidator() {
    const isValidator =
      !!this.conditionList.length && this.conditionList.every(item => !!item.key && !!item.value?.[0]);
    if (!isValidator) {
      this.conditionErrMsg = window.i18n.t('注意: 必填字段不能为空') as string;
    }
    return isValidator;
  }

  /* 保存 */
  handleSubmit() {
    if (!this.conditionValidator()) return;
    const result = this.$refs.noticeDate.getDateData();
    if (!result) return;
    const cycleDate = result[result.typeEn];
    const isSingle = result.typeEn === 'single';
    const noticeData = this.$refs.shieldNotice.getNoticeConfig();
    if (!noticeData) return;
    const params: any = {
      category: 'dimension',
      begin_time: isSingle ? cycleDate.range[0] : result.dateRange[0],
      end_time: isSingle ? cycleDate.range[1] : result.dateRange[1],
      cycle_config: {
        begin_time: isSingle ? '' : cycleDate.range[0],
        end_time: isSingle ? '' : cycleDate.range[1],
        day_list: result.typeEn === 'month' ? result.month.list : [],
        week_list: result.typeEn === 'week' ? result.week.list : [],
        type: result.type
      },
      shield_notice: typeof noticeData !== 'boolean',
      notice_config: {},
      description: this.desc,
      dimension_config: {
        dimension_conditions: this.conditionList.map(item => ({
          condition: item.condition,
          key: item.key,
          method: item.method,
          value: item.value,
          name: item.dimensionName
        })),
        strategy_id: this.strategyId
      }
    };
    if (params.shield_notice) {
      params.notice_config = {
        notice_time: noticeData.notice_time,
        notice_way: noticeData.notice_way,
        notice_receiver: noticeData.notice_receiver
      };
    }
    if (this.isEdit) {
      params.id = this.shieldData.id;
    }
    const ajax = this.isEdit ? editShield : addShield;
    let text = this.$t('创建屏蔽成功');
    if (this.isEdit) {
      text = this.isEdit && this.$t('编辑屏蔽成功');
    } else if (this.isClone) {
      text = this.isClone && this.$t('克隆屏蔽成功');
    }
    ajax(params)
      .then(() => {
        this.$router.push({ name: 'alarm-shield', params: { refresh: 'true' } });
        this.$bkMessage({ theme: 'success', message: text, ellipsisLine: 0 });
      })
      .catch(() => {})
      .finally(() => {
        this.$emit('update:loading', false);
      });
  }
  /* 取消 */
  handleCancel() {
    this.$router.back();
  }

  render() {
    return (
      <div
        class='alarm-shield-dimension'
        v-bkloading={{
          isLoading: this.loading
        }}
      >
        <div class='set-shield-config-item'>
          <div class='item-label item-required'>{window.i18n.t('所属')}</div>
          <div class='item-container'>
            <bk-select
              class='container-select'
              readonly
              v-model={this.biz.value}
              clearable={false}
            >
              {this.biz.list.map(item => (
                <bk-option
                  key={item.id}
                  id={item.id}
                  name={item.text}
                ></bk-option>
              ))}
            </bk-select>
          </div>
        </div>
        <div class='set-shield-config-item top'>
          <div class='item-label item-required'>
            {this.isEdit ? window.i18n.t('屏蔽范围') : window.i18n.t('维度选择')}
          </div>
          <div class='item-container'>
            {this.isEdit ? (
              <div class='scope-content'>
                <bk-table
                  data={[{}]}
                  maxHeight={450}
                  size={'large'}
                >
                  <bk-table-column
                    label={window.i18n.t('维度条件')}
                    scopedSlots={{
                      default: () => (
                        <WhereDisplay
                          value={this.conditionList as any}
                          readonly={true}
                          allNames={this.allNames}
                          key={this.conditionKey}
                        ></WhereDisplay>
                      )
                    }}
                  ></bk-table-column>
                </bk-table>
              </div>
            ) : (
              [
                <bk-select
                  class='container-select small'
                  scroll-height={216}
                  ext-popover-cls='shield-dimension-select-list-wrap'
                  v-model={this.strategyId}
                  clearable={false}
                  searchable
                  remote-method={this.searchStrategy}
                  placeholder={window.i18n.t('选择策略')}
                  onSelected={this.handleStrategy}
                  onToggle={this.handleToggle}
                >
                  <div v-bkloading={{ isLoading: this.strategyLoading }}>
                    <div
                      class='select-list-wrap'
                      ref='selectList'
                    >
                      {this.strategyList.map(item => (
                        <bk-option
                          key={item.id}
                          id={item.id}
                          name={item.name}
                        ></bk-option>
                      ))}
                    </div>
                  </div>
                </bk-select>,
                this.strategyId ? (
                  <div class='container-condition'>
                    <SimpleConditionInput
                      key={this.conditionKey}
                      conditionList={this.conditionList}
                      dimensionsList={this.dimensionList as any}
                      metricMeta={this.metricMeta}
                      onChange={v => {
                        this.conditionList = v as any;
                        this.conditionErrMsg = '';
                      }}
                    ></SimpleConditionInput>
                  </div>
                ) : undefined,
                this.conditionErrMsg ? <div class='err-msg'>{this.conditionErrMsg}</div> : undefined
              ]
            )}
          </div>
        </div>
        <ShieldDateConfig
          ref='noticeDate'
          v-model={this.commonDateData}
          isClone={this.isClone}
        ></ShieldDateConfig>
        <div class='set-shield-config-item'>
          <div class='item-label'>{window.i18n.t('屏蔽内容')}</div>
          <div class='item-container'>
            <bk-input
              class='content-desc'
              type='textarea'
              v-model={this.desc}
              row={3}
              maxlength={100}
            ></bk-input>
          </div>
        </div>
        <AlarmShieldNotice ref='shieldNotice'></AlarmShieldNotice>
        <div class='set-shield-config-item'>
          <div class='item-label'></div>
          <div class='item-container mb20'>
            <bk-button
              theme='primary'
              onClick={this.handleSubmit}
            >
              {' '}
              {window.i18n.t('提交')}{' '}
            </bk-button>
            <bk-button
              onClick={this.handleCancel}
              class='ml10'
            >
              {' '}
              {window.i18n.t('取消')}{' '}
            </bk-button>
          </div>
        </div>
      </div>
    );
  }
}
