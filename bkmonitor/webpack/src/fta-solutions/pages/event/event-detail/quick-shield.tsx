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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { bulkAddAlertShield } from 'monitor-api/modules/shield';
import VerifyInput from 'monitor-pc/components/verify-input/verify-input.vue';
import MonitorDialog from 'monitor-ui/monitor-dialog/monitor-dialog.vue';

import DimensionTransfer from './dimension-transfer';
import ShieldTreeCompnent from './shield-tree-compnent';

import type { IDimensionItem, IBkTopoNodeItem } from '../typings/event';

import './quick-shield.scss';

const { i18n } = window;

export interface IDetail {
  alertId: string;
  dimension?: IDimensionItem[];
  bkTopoNode?: IBkTopoNodeItem[];
  isModified?: boolean;
  severity: number;
  trigger?: string;
  strategy?: {
    id?: number;
    name?: string;
  };
  bkHostId?: number | string;
  shieldRadioData?: IshieldRadioDataItem[]
  shieldCheckedId?: string;
  hideDimensionTagIndex?: number;
  hideBkTopoNodeTagIndex?: number;
}

interface IshieldRadioDataItem {
  id: string;
  name: string;
}

interface DimensionConfig {
  alert_ids: string[];
  dimensions?: { [key: string]: string[] };
  bk_topo_node?: { [key: string]: IBkTopoNodeItem[] };
}

interface IQuickShieldProps {
  authority?: Record<string, boolean>;
  bizIds?: number[];
  details: IDetail[];
  ids?: Array<string>;
  show: boolean;
  handleShowAuthorityDetail?: (action: any) => void;
}

@Component({
  name: 'QuickShield',
})
export default class EventQuickShield extends tsc<IQuickShieldProps> {
  @Prop({ type: Object, default: () => ({}) }) authority: IQuickShieldProps['authority'];
  @Prop({ type: Function, default: null }) handleShowAuthorityDetail: IQuickShieldProps['handleShowAuthorityDetail'];
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Array, default: () => [] }) details: IDetail[];
  @Prop({ type: Array, default: () => [] }) ids: Array<string>;
  /* 事件中心暂不允许跨业务操作， 此数组只有一个业务 */
  @Prop({ type: Array, default: () => [] }) bizIds: number[];

  loading = false;
  rule = { customTime: false };
  timeList = [
    { name: `0.5${i18n.t('小时')}`, id: 18 },
    { name: `1${i18n.t('小时')}`, id: 36 },
    { name: `3${i18n.t('小时')}`, id: 108 },
    { name: `12${i18n.t('小时')}`, id: 432 },
    { name: `1${i18n.t('天')}`, id: 864 },
    { name: `7${i18n.t('天')}`, id: 6048 },
  ];
  timeValue = 18;
  nextDayTime: number | string = 10; // 次日时间，默认次日10点
  customTime: any = ['', ''];
  options = {
    disabledDate(date) {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      // 用户手动修改的时间不在可选时间内，回撤修改操作
      if (Array.isArray(date)) {
        return date.some(item => item.getTime() < today.getTime() || item.getTime() > today.getTime() + 8.64e7 * 181);
      }
      return date.getTime() < today.getTime() || date.getTime() > today.getTime() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
    },
  };
  levelMap = ['', i18n.t('致命'), i18n.t('提醒'), i18n.t('预警')];
  desc = '';

  backupDetails: IDetail[] = [];

  editIndex = -1; // 当前编辑的索引

  dimensionSelectShow = false;
  transferDimensionList: IDimensionItem[] = [];
  transferTargetList: string[] = [];

  shieldTreeDialogShow = false;

  // 每个告警屏蔽选择的选项（只在bkHostId存在时才使用）
  shieldRadioData = [{
    id: 'dimensions',
    name: i18n.t('维度屏蔽') as string,
  }, {
    id: 'bkTopoNode',
    name: i18n.t('范围屏蔽') as string,
  }]
  // 每个告警屏蔽选择的值（只在bkHostId存在时才可能改变，默认dimensions兼容无bkHostId的情况）
  shieldCheckedId = 'dimensions'

  @Watch('ids', { immediate: true, deep: true })
  handleShow(newIds, oldIds) {
    if (`${JSON.stringify(newIds)}` !== `${JSON.stringify(oldIds)}`) {
      this.handleDialogShow();
    }
  }

  @Watch('details', { immediate: true })
  handleDetailsChange() {
    const { shieldRadioData, shieldCheckedId } = this;
    const data = structuredClone(this.details || []);
    this.backupDetails = data.map(detail => {
      return {
        ...detail,
        shieldRadioData: structuredClone(shieldRadioData), // 屏蔽选择单选内容
        shieldCheckedId, // 屏蔽选择单选框选中的值
        hideDimensionTagIndex: -1, // 开始隐藏维度屏蔽tag的索引
        hideBkTopoNodeTagIndex: -1, // 开始隐藏范围屏蔽tag的索引
        modified: false,
      };
    });
    this.overviewCount();
  }

  handleDialogShow() {
    // this.loading = true
    this.timeValue = 18;
    this.nextDayTime = 10;
    this.desc = '';
    this.customTime = '';
  }

  handleformat(time, fmte) {
    let fmt = fmte;
    const obj = {
      'M+': time.getMonth() + 1, // 月份
      'd+': time.getDate(), // 日
      'h+': time.getHours(), // 小时
      'm+': time.getMinutes(), // 分
      's+': time.getSeconds(), // 秒
      'q+': Math.floor((time.getMonth() + 3) / 3), // 季度
      S: time.getMilliseconds(), // 毫秒
    };
    if (/(y+)/.test(fmt)) fmt = fmt.replace(RegExp.$1, `${time.getFullYear()}`.substr(4 - RegExp.$1.length));

    for (const key in obj) {
      if (new RegExp(`(${key})`).test(fmt)) {
        fmt = fmt.replace(RegExp.$1, RegExp.$1.length === 1 ? obj[key] : `00${obj[key]}`.substr(`${obj[key]}`.length));
      }
    }
    return fmt;
  }
  getTime() {
    let begin: Date = null;
    let end: Date = null;
    if (this.timeValue === 0) {
      const [beginTime, endTime] = this.customTime;
      if (beginTime === '' || endTime === '') {
        this.rule.customTime = true;
        return false;
      }
      begin = this.handleformat(beginTime, 'yyyy-MM-dd hh:mm:ss');
      end = this.handleformat(endTime, 'yyyy-MM-dd hh:mm:ss');
    } else {
      begin = new Date();
      const nowS = begin.getTime();
      end = new Date(nowS + this.timeValue * 100000);
      if (this.timeValue === -1) {
        // 次日时间点
        if (this.nextDayTime === '') {
          this.rule.customTime = true;
          return false;
        }
        end = new Date();
        end.setDate(end.getDate() + 1);
        end.setHours(this.nextDayTime as number, 0, 0, 0);
      }
      begin = this.handleformat(begin, 'yyyy-MM-dd hh:mm:ss');
      end = this.handleformat(end, 'yyyy-MM-dd hh:mm:ss');
    }
    return { begin, end };
  }
  handleSubmit() {
    const time = this.getTime();
    if (time) {
      this.loading = true;
      const params = {
        bk_biz_id: this.bizIds?.[0] || this.$store.getters.bizId,
        category: 'alert',
        begin_time: time.begin,
        end_time: time.end,
        dimension_config: { alert_ids: this.ids?.map(id => id.toString()) },
        shield_notice: false,
        description: this.desc,
        cycle_config: {
          begin_time: '',
          type: 1,
          day_list: [],
          week_list: [],
          end_time: '',
        },
      };
      dayjs.locale('en');
      let toTime = `${dayjs(time.begin).to(dayjs(time.end), true)}`;
      const tims = [
        ['day', 'd'],
        ['days', 'd'],
        ['hours', 'h'],
        ['hour', 'h'],
        ['minutes', 'm'],
        ['minute', 'm'],
        ['years', 'y'],
        ['year', 'y'],
      ];
      tims.forEach(item => {
        toTime = toTime.replace(item[0], item[1]);
      });

      // 当修改维度信息且单选框选择的是维度屏蔽时，调整入参
      // 默认选中维度屏蔽，所以不需要判断是否有bkHostid
      const changedDetails = this.backupDetails.filter(item => item.isModified && item.shieldCheckedId === 'dimensions');
      if (changedDetails.length) {
        (params.dimension_config as DimensionConfig).dimensions = changedDetails.reduce((pre, item) => {
          if (item.isModified) {
            pre[item.alertId.toString()] = item.dimension
              .filter(dim => dim.key && (dim.display_value || dim.value))
              .map(dim => dim.key);
          }
          return pre;
        }, {});
      }
      
      // 屏蔽范围不存在回显，有值且单选框选择了范围屏蔽则推上去；使用alertId做key，兼容单个与批量操作(与上方维度信息类似方式）
      const topoNodeDataArr = this.backupDetails.filter(
        item => item.bkTopoNode && item.bkTopoNode.length > 0 && item.shieldCheckedId === 'bkTopoNode'
      );
      if (topoNodeDataArr.length) {
        (params.dimension_config as DimensionConfig).bk_topo_node = topoNodeDataArr.reduce((pre, item) => {
          pre[item.alertId.toString()] = item.bkTopoNode.map(item => ({
            bk_obj_id: item.bk_obj_id,
            bk_inst_id: item.bk_inst_id,
          }))
          return pre;
        }, {});
      }
      
      bulkAddAlertShield(params)
        .then(() => {
          this.handleSucces(true);
          this.handleTimeChange(toTime);
          this.handleShowChange(false);
          this.$bkMessage({ theme: 'success', message: this.$t('创建告警屏蔽成功') });
        })
        .finally(() => {
          this.loading = false;
        });
    }
  }

  @Emit('succes')
  handleSucces(v) {
    return v;
  }

  @Emit('change')
  handleShowChange(v) {
    this.rule.customTime = false;
    return v;
  }
  @Emit('time-change')
  handleTimeChange(val: string) {
    return val;
  }

  handleScopeChange(e, type) {
    e.stopPropagation();
    this.timeValue = type;
    const [beginTime, endTime] = this.customTime;
    // 自定义时间异常状态
    if (type === 0 && (beginTime === '' || endTime === '')) return;
    // 至次日时间异常状态
    if (type === -1 && this.nextDayTime === '') return;
    // 校验状态通过
    this.rule.customTime = false;
  }

  handleToStrategy(id: number) {
    const url = location.href.replace(location.hash, `#/strategy-config/detail/${id}`);
    window.open(url);
  }

  // 删除维度信息
  // handleTagClose(detail: IDetail, index: number) {
  //   detail.dimension.splice(index, 1);
  //   detail.isModified = true;
  // }

  // 点击重置icon
  // handleReset(detailIndex: number) {
  //   const resetDetail = structuredClone(this.details[detailIndex]);
  //   this.backupDetails.splice(detailIndex, 1, {
  //     ...resetDetail,
  //     isModified: false,
  //   });
  // }

  // 编辑维度信息
  handleDimensionSelect(detail, idx) {
    if (detail.shieldCheckedId !== 'dimensions') return;
    // 初始化穿梭框数据
    this.transferDimensionList = this.details[idx].dimension;
    // 选中的数据
    this.transferTargetList = detail.dimension.map(dimension => dimension.key);
    this.editIndex = idx;
    this.dimensionSelectShow = true;
  }

  handleTransferConfirm(selectedDimensionArr: IDimensionItem[]) {
    const { backupDetails, editIndex: idx } = this;
    // 增删维度信息
    backupDetails[idx].dimension = this.details[idx].dimension.filter(dimensionItem =>
      selectedDimensionArr.some(targetItem => targetItem.key === dimensionItem.key)
    );
    // 设置编辑状态
    backupDetails[idx].isModified = false;
    // 穿梭框抛出的维度信息与最初不一致时，设置为已修改
    if (this.details[idx].dimension.length !== selectedDimensionArr.length) {
      backupDetails[idx].isModified = true;
    }
    this.dimensionSelectShow = false;
    this.handleResetTransferData();
  }

  handleTransferCancel() {
    this.dimensionSelectShow = false;
    this.handleResetTransferData();
  }

  handleResetTransferData() {
    this.transferDimensionList = [];
    this.transferTargetList = [];
    this.editIndex = -1;
  }

  /**
   * 编辑屏蔽范围
   * @param data 当前操作的屏蔽内容数据
   * @param idx 当前操作的屏蔽内容数据索引
   */
  handleShieldEdit(detail, idx) {
    if (detail.shieldCheckedId !== 'bkTopoNode') return;
    this.editIndex = idx;
    this.shieldTreeDialogShow = true;
  }

  /**
   * 屏蔽范围选择确认事件
   * @param checkedIds 已满足后端格式的节点数据集合（node_name用于前端展示，提交后端时删除）
   */
  handleShieldConfirm(checkedIds: IBkTopoNodeItem[]) {
    const { backupDetails, editIndex: idx } = this;
    backupDetails[idx].bkTopoNode = checkedIds;
    this.shieldTreeDialogShow = false;
    this.editIndex = -1;
    backupDetails[idx].hideBkTopoNodeTagIndex = -1;
    // tag是否溢出样式
    this.$nextTick(()=>{
      const nodeTagWrap = this.$el.querySelector(`.toponode-sel-${idx}`) as any;
      this.targetOverviewCount(nodeTagWrap, idx);
    })
  }

  // 取消屏蔽范围选择弹窗
  handleShieldCancel() {
    this.shieldTreeDialogShow = false;
    this.editIndex = -1;
  }

  // 计算维度与范围屏蔽超出的tag索引，用于展示被省略的tag数量和tooltip
  // 维度信息回显即为最大展示tag，只需要在第一次渲染时计算
  overviewCount() {
    this.$nextTick(() => {
      for (let i = 0; i < this.backupDetails.length; i++) {
        const dimensionTagWrap = this.$el.querySelector(`.dimension-sel-${i}`) as any;
        // const nodeTagWrap = this.$el.querySelector(`.toponode-sel-${i}`) as any;
        if (!!dimensionTagWrap) {
          this.targetOverviewCount(dimensionTagWrap, i);
        }
        // 屏蔽范围没有回显，只在用户操作增删时才需要计算（屏蔽范围的点击确认事件）
        // if (!!nodeTagWrap) {
        //   this.targetOverviewCount(nodeTagWrap, i);
        // }
      }
    });
  }

  // 单独计算指定告警内的维度屏蔽或告警屏蔽溢出
  targetOverviewCount(target, index) {
    if (target) {
      const targetIndex = target.className.includes('dimension-sel') ? 'hideDimensionTagIndex' : 'hideBkTopoNodeTagIndex';
      let hasHide = false;
      let idx = -1;
      for (const el of Array.from(target.children)) {
        if (el.className.includes('bk-tag')) {
          idx += 1;
          if ((el as any).offsetTop > 22) {
            hasHide = true;
            break;
          }
        }
      }
      if (hasHide && idx > 1) {
        const preItem = target.children[idx - 1] as any;
        if (preItem.offsetLeft + preItem.offsetWidth + 6 > target.offsetWidth - 53) {
          this.backupDetails[index][targetIndex] = idx - 1;
          return;
        }
      }
      this.backupDetails[index][targetIndex] = hasHide ? idx : -1;
    }
  }

  getInfoCompnent() {
    return this.backupDetails.map((detail, idx) => (
      <div
        key={idx}
        class='item-content'
      >
        {!!detail.strategy?.id && (
          <div class='column-item'>
            <div class='column-label'> {`${this.$t('策略名称')}：`} </div>
            <div class='column-content'>
              {detail.strategy.name}
              <i
                class='icon-monitor icon-mc-wailian'
                onClick={() => this.handleToStrategy(detail.strategy.id)}
              />
            </div>
          </div>
        )}
        {/* <div class='column-item'>
          <div class='column-label'> {`${this.$t('告警级别')}：`} </div>
          <div class='column-content'>{this.levelMap[detail.severity]}</div>
        </div> */}
        
        {/* <div class='column-item'>
          <div class={`column-label ${detail?.bkTopoNode?.length ? 'is-special' : ''}`}> {`${this.$t('屏蔽范围')}：`} </div>
          <div class='column-content'>
            {detail?.bkTopoNode?.length ? detail.bkTopoNode.map(node => (
              <bk-tag
                key={`${node.bk_inst_id}_${node.bk_obj_id}`}
                ext-cls='tag-theme'
                type='stroke'
              >
                {node.node_name}
              </bk-tag>
            )) : '-'}
            {detail?.bkHostId && (
              <span
                class='dimension-edit'
                v-bk-tooltips={{ content: `${this.$t('编辑')}` }}
                onClick={() => this.handleShieldEdit(detail, idx)}
              >
                <i class='icon-monitor icon-bianji' />
              </span>
            )}
          </div>
        </div> */}
        {/* 告警没有bkHostId时，无法进行范围屏蔽，此时按照旧样式仅展示维度屏蔽。如果有bkHostId，则按照新版样式进行单选 */}
        {detail?.bkHostId ? (
          <div class='column-item column-item-select'>
            <div class='column-label'>{`${this.$t('屏蔽选择')}：`} </div>
            <div class='column-content'>
              <bk-radio-group v-model={detail.shieldCheckedId}>
                {detail.shieldRadioData.map(item => (
                  <bk-radio
                    class='shield-radio-item'
                    key={item.id}
                    value={item.id}
                  >
                    {`${item.name}:`}
                    {/* 维度屏蔽 */}
                    {item.id === 'dimensions' && (
                      <div class={`shield-radio-content dimension-sel-${idx}`}>
                        {detail.dimension?.map((dem, dimensionIndex) => [
                          detail.hideDimensionTagIndex === dimensionIndex ? (
                            <span
                              key={'count'}
                              class='hide-count'
                              v-bk-tooltips={{
                                content: detail.dimension
                                  .slice(dimensionIndex)
                                  .map(d => `${d.display_key || d.key}(${d.display_value || d.value})`)
                                  .join('、'),
                                delay: 300,
                                theme: 'light',
                              }}
                            >
                              <span>{`+${detail.dimension.length - dimensionIndex}`}</span>
                            </span>
                          ) : undefined,
                          <bk-tag
                            key={dem.key + dimensionIndex}
                            ext-cls='tag-theme'
                            type='stroke'
                            // closable
                            // on-close={() => this.handleTagClose(detail, dimensionIndex)}
                          >
                            {`${dem.display_key || dem.key}(${dem.display_value || dem.value})`}
                          </bk-tag>,
                        ])}

                        {this.details[idx].dimension.length > 0 ? (
                          <span
                            class={['dimension-edit is-absolute', {'is-hidden' : detail.shieldCheckedId !== 'dimensions'}]}
                            v-bk-tooltips={{ content: `${this.$t('编辑')}` }}
                            onClick={() => this.handleDimensionSelect(detail, idx)}
                          >
                            <i class='icon-monitor icon-bianji' />
                          </span>
                        ) : (
                          '-'
                        )}
                      </div>
                    )}
                    {/* 范围屏蔽 */}
                    {item.id === 'bkTopoNode' && (
                      <div class={`shield-radio-content toponode-sel-${idx}`}>
                        {detail?.bkTopoNode?.length
                          ? detail.bkTopoNode.map((node, nodeIdx) => [
                              detail.hideBkTopoNodeTagIndex === nodeIdx ? (
                                <span
                                  key={'count'}
                                  class='hide-count'
                                  v-bk-tooltips={{
                                    content: detail.bkTopoNode
                                      .slice(nodeIdx)
                                      .map(n => n.node_name)
                                      .join('、'),
                                    delay: 300,
                                    theme: 'light',
                                  }}
                                >
                                  <span>{`+${detail.bkTopoNode.length - nodeIdx}`}</span>
                                </span>
                              ) : undefined,
                              <bk-tag
                                key={`${node.bk_inst_id}_${node.bk_obj_id}`}
                                ext-cls='tag-theme'
                                type='stroke'
                              >
                                {node.node_name}
                              </bk-tag>,
                            ])
                          : undefined}
                          <span
                            class={['dimension-edit is-absolute', { 'is-hidden': detail.shieldCheckedId !== 'bkTopoNode' }]}
                            v-bk-tooltips={{ content: `${this.$t('编辑')}` }}
                            onClick={() => this.handleShieldEdit(detail, idx)}
                          >
                            <i class='icon-monitor icon-bianji' />
                          </span>
                      </div>
                    )}
                  </bk-radio>
                ))}
              </bk-radio-group>
            </div>
          </div>
        ) : (
          <div class='column-item'>
            <div class={`column-label ${this.details[idx].dimension.length ? 'is-special' : ''}`}>
              {`${this.$t('维度屏蔽')}：`}
            </div>
            <div class='column-content'>
              {detail.dimension?.map((dem, dimensionIndex) => (
                <bk-tag
                  key={dem.key + dimensionIndex}
                  ext-cls='tag-theme'
                  type='stroke'
                  // closable
                  // on-close={() => this.handleTagClose(detail, dimensionIndex)}
                >
                  {`${dem.display_key || dem.key}(${dem.display_value || dem.value})`}
                </bk-tag>
              ))}
              {this.details[idx].dimension.length > 0 ? (
                <span
                  class='dimension-edit'
                  v-bk-tooltips={{ content: `${this.$t('编辑')}` }}
                  onClick={() => this.handleDimensionSelect(detail, idx)}
                >
                  <i class='icon-monitor icon-bianji' />
                </span>
              ) : (
                '-'
              )}
              {/* {detail.isModified && (
              <span
                class='reset'
                v-bk-tooltips={{ content: `${this.$t('重置')}` }}
                onClick={() => this.handleReset(idx)}
              >
                <i class='icon-monitor icon-zhongzhi1' />
              </span>
            )} */}
            </div>
          </div>
        )}
        <div
          style='margin-bottom: 18px'
          class='column-item'
        >
          <div class='column-label'> {`${this.$t('触发条件')}：`} </div>
          <div class='column-content'>{detail.trigger}</div>
        </div>
      </div>
    ));
  }

  getContentComponent() {
    return (
      <div
        class='quick-alarm-shield-event'
        v-bkloading={{ isLoading: this.loading }}
      >
        {!this.loading ? (
          <div class='stratrgy-item'>
            <div class='item-label item-before'> {this.$t('屏蔽时间')} </div>
            <VerifyInput
              errorTextTopMargin={80}
              show-validate={this.rule.customTime}
              {...{ on: { 'update: show-validate': val => (this.rule.customTime = val) } }}
              validator={{ content: this.$t('至少选择一种时间') }}
            >
              <div class='item-time'>
                {this.timeList.map((item, index) => (
                  <bk-button
                    key={index}
                    class={['width-item', { 'is-selected': this.timeValue === item.id }]}
                    on-click={e => this.handleScopeChange(e, item.id)}
                  >
                    {item.name}
                  </bk-button>
                ))}
                <bk-button
                  class={['width-item', { 'is-selected': this.timeValue === -1 }]}
                  on-click={e => this.handleScopeChange(e, -1)}
                >
                  {this.$t('至次日')}
                </bk-button>
                <bk-button
                  class={['width-item', { 'is-selected': this.timeValue === 0 }]}
                  on-click={e => this.handleScopeChange(e, 0)}
                >
                  {this.$t('button-自定义')}
                </bk-button>
              </div>
            </VerifyInput>
          </div>
        ) : undefined}
        {this.timeValue <= 0 && (
          <div class={['stratrgy-item', 'custom-time', !this.timeValue ? 'left-custom' : 'left-next-day']}>
            {this.timeValue === -1 && [
              this.$t('至次日'),
              <bk-input
                key='nextDayInput'
                class='custom-input-time'
                v-model={this.nextDayTime}
                behavior='simplicity'
                max={23}
                min={0}
                placeholder='0~23'
                precision={0}
                show-controls={false}
                type='number'
              />,
              this.$t('点'),
            ]}
            {this.timeValue === 0 && [
              this.$t('自定义'),
              <bk-date-picker
                key='customTime'
                ref='time'
                class='custom-select-time'
                v-model={this.customTime}
                behavior='simplicity'
                options={this.options}
                placeholder={this.$t('选择日期时间范围')}
                type={'datetimerange'}
              />,
            ]}
          </div>
        )}
        <div class='stratrgy-item m0'>
          <div class='item-label'> {this.$t('屏蔽内容')} </div>
          <div class='item-tips'>
            <i class='icon-monitor icon-hint' />{' '}
            {this.$t('屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。')}{' '}
          </div>
          {this.getInfoCompnent()}
        </div>
        <div class='stratrgy-item'>
          <div class='item-label'> {this.$t('屏蔽原因')} </div>
          <div class='item-desc'>
            <bk-input
              width={625}
              v-model={this.desc}
              maxlength={100}
              rows={3}
              type='textarea'
            />
          </div>
        </div>
      </div>
    );
  }

  render() {
    return (
      <MonitorDialog
        width={'804'}
        class='quick-shield-dialog'
        header-position={'left'}
        title={this.$t('快捷屏蔽告警')}
        value={this.show}
        on-change={this.handleShowChange}
      >
        {this.getContentComponent()}
        <template slot='footer'>
          <bk-button
            style='margin-right: 10px'
            v-authority={{ active: !this.authority?.ALARM_SHIELD_MANAGE_AUTH }}
            disabled={this.loading}
            theme='primary'
            on-click={() =>
              this.authority?.ALARM_SHIELD_MANAGE_AUTH
                ? this.handleSubmit()
                : this.handleShowAuthorityDetail?.(this.authority?.ALARM_SHIELD_MANAGE_AUTH)
            }
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button on-click={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
        </template>
        {/* 穿梭框 */}
        <bk-dialog
          width={640}
          ext-cls='quick-shield-dialog-wrap'
          v-model={this.dimensionSelectShow}
          header-position='left'
          mask-close={false}
          show-footer={false}
          title={this.$t('选择维度信息')}
        >
          <DimensionTransfer
            fields={this.transferDimensionList}
            show={this.dimensionSelectShow}
            value={this.transferTargetList}
            onCancel={this.handleTransferCancel}
            onConfirm={this.handleTransferConfirm}
          />
        </bk-dialog>
        {/* 选择屏蔽范围弹窗 */}
        <bk-dialog
          width={480}
          ext-cls='quick-shield-dialog-wrap'
          v-model={this.shieldTreeDialogShow}
          header-position='left'
          mask-close={false}
          show-footer={false}
          title={this.$t('选择屏蔽范围')}
        >
          <ShieldTreeCompnent
            show={this.shieldTreeDialogShow}
            bizId={this.bizIds[0]}
            bkHostId={this.details[this.editIndex]?.bkHostId || ''}
            onCancel={this.handleShieldCancel}
            onConfirm={this.handleShieldConfirm}
          />
        </bk-dialog>
      </MonitorDialog>
    );
  }
}
