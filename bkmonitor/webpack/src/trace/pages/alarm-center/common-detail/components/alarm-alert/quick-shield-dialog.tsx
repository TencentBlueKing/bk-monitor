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
import { type PropType, defineComponent, inject, nextTick, reactive, shallowRef, useTemplateRef, watch } from 'vue';

import { Button, DatePicker, Dialog, Input, Loading, Message, Radio, Tag } from 'bkui-vue';
import dayjs from 'dayjs';
import { bulkAddAlertShield } from 'monitor-api/modules/shield';
import { useI18n } from 'vue-i18n';

import VerifyInput from '../../../../../components/verify-input/verify-input';
import DimensionTransfer from './dimension-transfer';
import ShieldTreeComponent from './shield-tree-component';

import type { AlarmShieldDetail, IBkTopoNodeItem, IDimension } from '../../../typings';
import type { IAuthority } from '@/typings/authority';

import './quick-shield-dialog.scss';
export default defineComponent({
  name: 'QuickShieldDialog',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    alarmIds: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    alarmBizId: {
      type: Number,
      default: undefined,
    },
    alarmShieldDetail: {
      type: Array as PropType<AlarmShieldDetail[]>,
      default: () => [],
    },
  },
  emits: {
    'update:show': val => typeof val === 'boolean',
    success: val => typeof val === 'boolean',
    timeChange: val => typeof val === 'string',
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const authority = inject<IAuthority>('authority', { auth: {}, map: {}, showDetail: () => {} });
    const loading = shallowRef(false);
    const contentRef = useTemplateRef<HTMLDivElement>('contentRef');
    const timeList = [
      { name: `0.5${t('小时')}`, id: 18 },
      { name: `1${t('小时')}`, id: 36 },
      { name: `3${t('小时')}`, id: 108 },
      { name: `12${t('小时')}`, id: 432 },
      { name: `1${t('天')}`, id: 864 },
      { name: `7${t('天')}`, id: 6048 },
    ];
    const ruleErrMsg = reactive({
      customTime: '',
    });
    /** 屏蔽时间类型 */
    const timeValue = shallowRef(18);
    /** 次日时间，默认次日10点 */
    const nextDayTime = shallowRef<number | string>(10);
    /** 自定义时间 */
    const customTime = shallowRef(['', '']);

    const desc = shallowRef('');

    const backupDetails = shallowRef<AlarmShieldDetail[]>([]);

    const editIndex = shallowRef(-1); // 当前编辑的索引

    const dimensionSelectShow = shallowRef(false);

    const transferDimensionList = shallowRef<IDimension[]>([]);
    const transferTargetList = shallowRef<string[]>([]);
    const shieldTreeDialogShow = shallowRef(false);

    // 每个告警屏蔽选择的选项（只在bkHostId存在时才使用）
    const shieldRadioData = [
      {
        id: 'dimensions',
        name: t('维度屏蔽') as string,
      },
      {
        id: 'bkTopoNode',
        name: t('范围屏蔽') as string,
      },
    ];
    // 每个告警屏蔽选择的值（只在bkHostId存在时才可能改变，默认dimensions兼容无bkHostId的情况）
    const shieldCheckedId = 'dimensions';

    watch(
      () => props.alarmIds,
      (newVal, oldVal) => {
        if (newVal !== oldVal) {
          handleDialogShow();
        }
      }
    );

    // 计算维度与范围屏蔽超出的tag索引，用于展示被省略的tag数量和tooltip
    // 维度信息回显即为最大展示tag，只需要在第一次渲染时计算
    const overviewCount = () => {
      nextTick(() => {
        for (let i = 0; i < backupDetails.value.length; i++) {
          const dimensionTagWrap = contentRef.value.querySelector(`.dimension-sel-${i}`);
          if (dimensionTagWrap) {
            targetOverviewCount(dimensionTagWrap, i);
          }
        }
      });
    };

    watch(
      () => props.show,
      show => {
        if (show) {
          setTimeout(() => {
            overviewCount();
          }, 16);
        }
      }
    );

    watch(
      () => props.alarmShieldDetail,
      () => {
        const data = structuredClone(props.alarmShieldDetail || []);
        backupDetails.value = data.map(detail => {
          return {
            ...detail,
            shieldRadioData: structuredClone(shieldRadioData), // 屏蔽选择单选内容
            shieldCheckedId: shieldCheckedId, // 屏蔽选择单选框选中的值
            hideDimensionTagIndex: -1, // 开始隐藏维度屏蔽tag的索引
            hideBkTopoNodeTagIndex: -1, // 开始隐藏范围屏蔽tag的索引
            modified: false,
          };
        });
      },
      { immediate: true }
    );

    function handleDialogShow() {
      timeValue.value = 18;
      nextDayTime.value = 10;
      desc.value = '';
      customTime.value = [];
    }

    function handleFormat(time, fmte) {
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
          fmt = fmt.replace(
            RegExp.$1,
            RegExp.$1.length === 1 ? obj[key] : `00${obj[key]}`.substr(`${obj[key]}`.length)
          );
        }
      }
      return fmt;
    }

    function getTime() {
      let begin: Date = null;
      let end: Date = null;
      if (timeValue.value === 0) {
        const [beginTime, endTime] = customTime.value;
        if (!beginTime || !endTime) {
          ruleErrMsg.customTime = t('至少选择一种时间');
          return false;
        }
        begin = handleFormat(beginTime, 'yyyy-MM-dd hh:mm:ss');
        end = handleFormat(endTime, 'yyyy-MM-dd hh:mm:ss');
      } else {
        begin = new Date();
        const nowS = begin.getTime();
        end = new Date(nowS + timeValue.value * 100000);
        if (timeValue.value === -1) {
          // 次日时间点
          if (nextDayTime.value === '') {
            ruleErrMsg.customTime = t('至少选择一种时间');
            return false;
          }
          end = new Date();
          end.setDate(end.getDate() + 1);
          end.setHours(nextDayTime.value as number, 0, 0, 0);
        }
        begin = handleFormat(begin, 'yyyy-MM-dd hh:mm:ss');
        end = handleFormat(end, 'yyyy-MM-dd hh:mm:ss');
      }
      return { begin, end };
    }

    function handleSubmit() {
      const time = getTime();
      if (time) {
        loading.value = true;
        const params = {
          bk_biz_id: props.alarmBizId,
          category: 'alert',
          begin_time: time.begin,
          end_time: time.end,
          dimension_config: { alert_ids: props.alarmIds.map(id => id.toString()) },
          shield_notice: false,
          description: desc.value,
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
        const changedDetails = backupDetails.value.filter(
          item => item.isModified && item.shieldCheckedId === 'dimensions'
        );
        if (changedDetails.length) {
          params.dimension_config.dimensions = changedDetails.reduce((pre, item) => {
            if (item.isModified) {
              pre[item.alertId.toString()] = item.dimension
                .filter(dim => dim.key && (dim.display_value || dim.value))
                .map(dim => dim.key);
            }
            return pre;
          }, {});
        }

        // 屏蔽范围不存在回显，有值且单选框选择了范围屏蔽则推上去；使用alertId做key，兼容单个与批量操作(与上方维度信息类似方式）
        const topoNodeDataArr = backupDetails.value.filter(
          item => item.bkTopoNode && item.bkTopoNode.length > 0 && item.shieldCheckedId === 'bkTopoNode'
        );
        if (topoNodeDataArr.length) {
          params.dimension_config.bk_topo_node = topoNodeDataArr.reduce((pre, item) => {
            pre[item.alertId.toString()] = item.bkTopoNode.map(item => ({
              bk_obj_id: item.bk_obj_id,
              bk_inst_id: item.bk_inst_id,
            }));
            return pre;
          }, {});
        }

        bulkAddAlertShield(params)
          .then(() => {
            emit('success', true);
            emit('timeChange', toTime);
            handleShowChange(false);
            Message({ theme: 'success', message: t('创建告警屏蔽成功') });
          })
          .finally(() => {
            loading.value = false;
          });
      }
    }

    /** 禁用日期 */
    const disabledDate = date => {
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      // 用户手动修改的时间不在可选时间内，回撤修改操作
      if (Array.isArray(date)) {
        return date.some(item => item.getTime() < today.getTime() || item.getTime() > today.getTime() + 8.64e7 * 181);
      }
      return date.getTime() < today.getTime() || date.getTime() > today.getTime() + 8.64e7 * 181; // 限制用户只能选择半年以内的日期
    };

    const getContentComponent = () => {
      return (
        <Loading loading={loading.value}>
          <div class='quick-alarm-shield-form'>
            {!loading.value ? (
              <div class={['stratrgy-item shield-time', { error: Boolean(ruleErrMsg.customTime) }]}>
                <div class='item-label item-before'> {t('屏蔽时间')} </div>
                <VerifyInput errMsg={ruleErrMsg.customTime}>
                  <div class='item-time'>
                    {timeList.map((item, index) => (
                      <Button
                        key={index}
                        class={['width-item', { 'is-selected': timeValue.value === item.id }]}
                        onClick={e => handleScopeChange(e, item.id)}
                      >
                        {item.name}
                      </Button>
                    ))}
                    <Button
                      class={['width-item', { 'is-selected': timeValue.value === -1 }]}
                      onClick={e => handleScopeChange(e, -1)}
                    >
                      {t('至次日')}
                    </Button>
                    <Button
                      class={['width-item', { 'is-selected': timeValue.value === 0 }]}
                      onClick={e => handleScopeChange(e, 0)}
                    >
                      {t('button-自定义')}
                    </Button>
                  </div>
                </VerifyInput>
              </div>
            ) : undefined}
            {timeValue.value <= 0 && (
              <div class={['stratrgy-item', 'custom-time', !timeValue.value ? 'left-custom' : 'left-next-day']}>
                {timeValue.value === -1 && [
                  t('至次日'),
                  <Input
                    key='nextDayInput'
                    class='custom-input-time'
                    v-model={nextDayTime.value}
                    behavior='simplicity'
                    max={23}
                    min={0}
                    placeholder='0~23'
                    precision={0}
                    showControl={false}
                    type='number'
                  />,
                  t('点'),
                ]}
                {timeValue.value === 0 && [
                  t('自定义'),
                  <DatePicker
                    key='customTime'
                    ref='time'
                    class='custom-select-time'
                    v-model={customTime.value}
                    behavior='simplicity'
                    disabled-date={disabledDate}
                    placeholder={t('选择日期时间范围')}
                    type={'datetimerange'}
                  />,
                ]}
              </div>
            )}
            <div class='stratrgy-item m0'>
              <div class='item-label'> {t('屏蔽内容')} </div>
              <div class='item-tips'>
                <i class='icon-monitor icon-hint' />{' '}
                {t('屏蔽的是告警内容的这类事件，不仅仅当前的事件还包括后续屏蔽时间内产生的事件。')}{' '}
              </div>
              {getInfoComponent()}
            </div>
            <div class='stratrgy-item'>
              <div class='item-label'> {t('屏蔽原因')} </div>
              <div class='item-desc'>
                <Input
                  v-model={desc.value}
                  maxlength={100}
                  resize={false}
                  rows={3}
                  type='textarea'
                />
              </div>
            </div>
          </div>
        </Loading>
      );
    };

    const getInfoComponent = () => {
      return backupDetails.value.map((detail, idx) => (
        <div
          key={idx}
          class='item-content'
        >
          {!!detail.strategy?.id && (
            <div class='column-item'>
              <div class='column-label'> {`${t('策略名称')}：`} </div>
              <div class='column-content'>
                {detail.strategy.name}
                <i
                  class='icon-monitor icon-mc-wailian'
                  onClick={() => handleToStrategy(detail.strategy.id)}
                />
              </div>
            </div>
          )}
          {/* 告警没有bkHostId时，无法进行范围屏蔽，此时按照旧样式仅展示维度屏蔽。如果有bkHostId，则按照新版样式进行单选 */}
          {detail?.bkHostId ? (
            <div class='column-item column-item-select'>
              <div class='column-label'>{`${t('屏蔽选择')}：`} </div>
              <div class='column-content'>
                <Radio.Group
                  class='shield-radio-group'
                  v-model={detail.shieldCheckedId}
                >
                  {detail.shieldRadioData.map(item => (
                    <Radio
                      key={item.id}
                      class='shield-radio-item'
                      label={item.id}
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
                            <Tag
                              key={dem.key + dimensionIndex}
                              class='tag-theme'
                              type='stroke'
                              // closable
                              // on-close={() => this.handleTagClose(detail, dimensionIndex)}
                            >
                              {`${dem.display_key || dem.key}(${dem.display_value || dem.value})`}
                            </Tag>,
                          ])}

                          {props.alarmShieldDetail[idx].dimension.length > 0 ? (
                            <span
                              class={[
                                'dimension-edit is-absolute',
                                { 'is-hidden': detail.shieldCheckedId !== 'dimensions' },
                              ]}
                              v-bk-tooltips={{ content: `${t('编辑')}` }}
                              onClick={() => handleDimensionSelect(detail, idx)}
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
                                <Tag
                                  key={`${node.bk_inst_id}_${node.bk_obj_id}`}
                                  class='tag-theme'
                                  type='stroke'
                                >
                                  {node.node_name}
                                </Tag>,
                              ])
                            : undefined}
                          <span
                            class={[
                              'dimension-edit is-absolute',
                              { 'is-hidden': detail.shieldCheckedId !== 'bkTopoNode' },
                            ]}
                            v-bk-tooltips={{ content: `${t('编辑')}` }}
                            onClick={() => handleShieldEdit(detail, idx)}
                          >
                            <i class='icon-monitor icon-bianji' />
                          </span>
                        </div>
                      )}
                    </Radio>
                  ))}
                </Radio.Group>
              </div>
            </div>
          ) : (
            <div class='column-item'>
              <div class={`column-label ${props.alarmShieldDetail[idx].dimension.length ? 'is-special' : ''}`}>
                {`${t('维度屏蔽')}：`}
              </div>
              <div class='column-content'>
                {detail.dimension?.map((dem, dimensionIndex) => (
                  <Tag
                    key={dem.key + dimensionIndex}
                    class='tag-theme'
                    type='stroke'
                  >
                    {`${dem.display_key || dem.key}(${dem.display_value || dem.value})`}
                  </Tag>
                ))}
                {props.alarmShieldDetail[idx].dimension.length > 0 ? (
                  <span
                    class='dimension-edit'
                    v-bk-tooltips={{ content: `${t('编辑')}` }}
                    onClick={() => handleDimensionSelect(detail, idx)}
                  >
                    <i class='icon-monitor icon-bianji' />
                  </span>
                ) : (
                  '-'
                )}
              </div>
            </div>
          )}
          <div
            style='margin-bottom: 18px'
            class='column-item'
          >
            <div class='column-label'> {`${t('触发条件')}：`} </div>
            <div class='column-content'>{detail.trigger}</div>
          </div>
        </div>
      ));
    };

    const handleScopeChange = (e, type) => {
      e.stopPropagation();
      timeValue.value = type;
      const [beginTime, endTime] = customTime.value;
      // 自定义时间异常状态
      if (type === 0 && (beginTime === '' || endTime === '')) return;
      // 至次日时间异常状态
      if (type === -1 && nextDayTime.value === '') return;
      // 校验状态通过
      ruleErrMsg.customTime = '';
    };

    const handleToStrategy = (id: number) => {
      const url = location.href.replace(location.hash, `#/strategy-config/detail/${id}`);
      window.open(url);
    };

    // 编辑维度信息
    const handleDimensionSelect = (detail: AlarmShieldDetail, idx: number) => {
      if (detail.shieldCheckedId !== 'dimensions') return;
      // 初始化穿梭框数据
      transferDimensionList.value = props.alarmShieldDetail[idx].dimension;
      // 选中的数据
      transferTargetList.value = detail.dimension.map(dimension => dimension.key);
      editIndex.value = idx;
      dimensionSelectShow.value = true;
    };

    const handleTransferConfirm = (selectedDimensionArr: IDimension[]) => {
      const details = structuredClone(backupDetails.value);
      // 增删维度信息
      details[editIndex.value].dimension = props.alarmShieldDetail[editIndex.value].dimension.filter(dimensionItem =>
        selectedDimensionArr.some(targetItem => targetItem.key === dimensionItem.key)
      );
      // 设置编辑状态
      details[editIndex.value].isModified = false;
      // 穿梭框抛出的维度信息与最初不一致时，设置为已修改
      if (props.alarmShieldDetail[editIndex.value].dimension.length !== selectedDimensionArr.length) {
        details[editIndex.value].isModified = true;
      }
      backupDetails.value = details;
      dimensionSelectShow.value = false;
      handleResetTransferData();
    };

    const handleTransferCancel = () => {
      dimensionSelectShow.value = false;
      handleResetTransferData();
    };

    const handleResetTransferData = () => {
      transferDimensionList.value = [];
      transferTargetList.value = [];
      editIndex.value = -1;
    };

    /**
     * 编辑屏蔽范围
     * @param data 当前操作的屏蔽内容数据
     * @param idx 当前操作的屏蔽内容数据索引
     */
    const handleShieldEdit = (detail: AlarmShieldDetail, idx: number) => {
      if (detail.shieldCheckedId !== 'bkTopoNode') return;
      editIndex.value = idx;
      shieldTreeDialogShow.value = true;
    };

    /**
     * 屏蔽范围选择确认事件
     * @param checkedIds 已满足后端格式的节点数据集合（node_name用于前端展示，提交后端时删除）
     */
    const handleShieldConfirm = (checkedIds: IBkTopoNodeItem[]) => {
      const details = structuredClone(backupDetails.value);
      details[editIndex.value].bkTopoNode = checkedIds;
      shieldTreeDialogShow.value = false;
      details[editIndex.value].hideBkTopoNodeTagIndex = -1;
      backupDetails.value = details;
      editIndex.value = -1;
      // tag是否溢出样式
      nextTick(() => {
        const nodeTagWrap = contentRef.value.querySelector(`.toponode-sel-${editIndex.value}`) as any;
        targetOverviewCount(nodeTagWrap, editIndex.value);
      });
    };

    // 取消屏蔽范围选择弹窗
    const handleShieldCancel = () => {
      shieldTreeDialogShow.value = false;
      editIndex.value = -1;
    };

    // 单独计算指定告警内的维度屏蔽或告警屏蔽溢出
    const targetOverviewCount = (target, index) => {
      if (target) {
        const targetIndex = target.className.includes('dimension-sel')
          ? 'hideDimensionTagIndex'
          : 'hideBkTopoNodeTagIndex';
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
        const details = structuredClone(backupDetails.value);
        if (hasHide && idx > 1) {
          const preItem = target.children[idx - 1] as any;
          if (preItem.offsetLeft + preItem.offsetWidth + 6 > target.offsetWidth - 53) {
            details[index][targetIndex] = idx - 1;
          }
        } else {
          details[index][targetIndex] = hasHide ? idx : -1;
        }
        backupDetails.value = details;
      }
    };

    const handleShowChange = (val: boolean) => {
      emit('update:show', val);
    };

    return {
      t,
      timeValue,
      authority,
      loading,
      dimensionSelectShow,
      editIndex,
      transferDimensionList,
      transferTargetList,
      shieldTreeDialogShow,
      contentRef,
      getContentComponent,
      handleShowChange,
      handleToStrategy,
      handleShieldConfirm,
      handleShieldCancel,
      handleSubmit,
      handleTransferCancel,
      handleTransferConfirm,
    };
  },
  render() {
    return (
      <Dialog
        width={'804'}
        class='trace-alarm-center-quick-shield-dialog'
        v-slots={{
          default: () => (
            <div
              ref='contentRef'
              class='quick-shield-content'
            >
              {this.getContentComponent()}
              {/* 穿梭框 */}
              <Dialog
                width={640}
                class='trace-alarm-center-quick-shield-dialog-wrap'
                v-model:is-show={this.dimensionSelectShow}
                header-position='left'
                quick-close={false}
                title={this.t('选择维度信息')}
              >
                <DimensionTransfer
                  fields={this.transferDimensionList}
                  show={this.dimensionSelectShow}
                  value={this.transferTargetList}
                  onCancel={this.handleTransferCancel}
                  onConfirm={this.handleTransferConfirm}
                />
              </Dialog>
              {/* 选择屏蔽范围弹窗 */}
              <Dialog
                width={480}
                class='trace-alarm-center-quick-shield-dialog-wrap'
                v-model:is-show={this.shieldTreeDialogShow}
                header-position='left'
                quick-close={false}
                title={this.t('选择屏蔽范围')}
              >
                <ShieldTreeComponent
                  bizId={this.alarmBizId}
                  bkHostId={this.alarmShieldDetail[this.editIndex]?.bkHostId || ''}
                  show={this.shieldTreeDialogShow}
                  onCancel={this.handleShieldCancel}
                  onConfirm={this.handleShieldConfirm}
                />
              </Dialog>
            </div>
          ),
          footer: () => (
            <div class='footer-btn'>
              <Button
                style='margin-right: 10px'
                v-authority={{ active: !this.authority?.auth.ALARM_SHIELD_MANAGE_AUTH }}
                disabled={this.loading}
                theme='primary'
                onClick={() =>
                  this.authority?.auth.ALARM_SHIELD_MANAGE_AUTH
                    ? this.handleSubmit()
                    : this.authority.showDetail?.([this.authority.map.ALARM_SHIELD_MANAGE_AUTH])
                }
              >
                {this.t('确定')}
              </Button>
              <Button onClick={() => this.handleShowChange(false)}>{this.t('取消')}</Button>
            </div>
          ),
        }}
        header-position={'left'}
        isShow={this.show}
        title={this.t('快捷屏蔽告警')}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
