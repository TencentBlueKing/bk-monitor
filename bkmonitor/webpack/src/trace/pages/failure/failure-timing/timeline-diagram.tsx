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
import {
  type PropType,
  type Ref,
  computed,
  defineComponent,
  inject,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';

import { Message, Popover } from 'bkui-vue';
import { timeDay } from 'd3-time';
import dayjs from 'dayjs';
import { feedbackIncidentRoot, incidentRecordOperation } from 'monitor-api/modules/incident';
import { getCookie } from 'monitor-common/utils';
import { random } from 'monitor-common/utils/utils.js';
import { useI18n } from 'vue-i18n';

import AlarmConfirm from '../alarm-detail/alarm-confirm';
import AlarmDispatch from '../alarm-detail/alarm-dispatch';
import ManualProcess from '../alarm-detail/manual-process';
import QuickShield from '../alarm-detail/quick-shield';
import { dialogConfig, EVENT_SEVERITY, TREE_SHOW_ICON_LIST } from '../constant';
import { renderMap } from '../failure-process/process';
import FeedbackCauseDialog from '../failure-topo/feedback-cause-dialog';
import { useIncidentInject } from '../utils';
import TimelineZoom from './timeline-zoom';

import type { IAggregationRoot, IAlert, IIncident, IIncidentOperation } from '../types';

import './timeline-diagram.scss';
interface GroupResult {
  list: Operation[];
  more: boolean;
}
interface IncidentOperationsRecord {
  [key: string]: IIncidentOperation[];
}
interface IStatusEnum {
  [key: string]: string;
}

interface Operation {
  [key: string]: any;
  create_time: number;
}
// const iconList = {
//   alert_confirm: 'gaojing1',
//   alert_invalid: 'gaojing1',
//   manual_update: 'mc-fault',
//   incident_create: 'mc-fault',
//   feedback: 'mc-fault'
// };
export default defineComponent({
  name: 'TimelineDiagram',
  props: {
    alertAggregateData: {
      type: Array as PropType<IAlert[]>,
      default: () => [],
    },
    scrollTop: {
      type: Number,
      default: 0,
    },
    chooseOperation: {
      type: Object as () => IIncidentOperation,
      default: () => ({}),
    },
  },
  emits: ['goAlertDetail', 'refresh', 'changeTab'],
  setup(props, { emit }) {
    const timeMainRef = ref<HTMLDivElement>();
    const { t } = useI18n();
    const clientWidth = ref<number>(0);
    const clientHeight = ref<number>(0);
    const timelineRef = ref<HTMLDivElement>();
    const hourWidth = ref<number>(0);
    const maxCircleTotal = ref<number>(3);
    const treeData = ref<IAggregationRoot[]>([]);
    const tickArr = ref<string[]>([]);
    const showTickArr = ref<string[]>([]);
    const currentSpan = ref<IAlert>();
    const statusEnum = ref<IStatusEnum[]>([]);
    const timeData = ref<IncidentOperationsRecord>({});
    const operationsList = inject<Ref>('operationsList');
    const operationTypeMap = inject<Ref>('operationTypeMap');
    /** 坐标轴时间间隔 */
    const timeInterval = ref<number>(1);
    const isHour = ref<boolean>(false);
    const mainWidth = ref<number>();
    const mainLeft = ref<number>(0);
    const percentage = ref<number>(0);
    const tickStep = ref<number>(0);
    const beginTick = ref<number>(0);
    /** 每个刻度之间的时间间隔 */
    const segmentDuration = ref<number>(0);
    const timeLineMainRef = ref<HTMLDivElement>();
    const showToolMenu = ref<boolean>(false);
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const incidentId = useIncidentInject();
    const tickPopoverRefs = ref<HTMLDivElement[]>([]);
    const dialog = ref(dialogConfig);
    const currentIds = ref<number[]>([]);
    const currentBizIds = ref<number[]>([]);
    const isDragging = ref<boolean>(false);
    const mouseRatio = ref<number>();
    const keyIdList = ref<string[]>([]);
    const processPopoverRefs = ref<HTMLDivElement[]>([]);
    const actionList = ref([
      {
        id: 'alert_confirm',
        name: t('告警确认'),
        icon: 'icon-duihao',
        onClick: e => actionClickFn(e, handleAlertConfirm),
      },
      {
        id: 'manual_handling',
        name: t('手动处理'),
        icon: 'icon-chuli',
        onClick: e => actionClickFn(e, handleManualProcess),
      },
      {
        id: 'quick_block',
        name: t('快捷屏蔽'),
        icon: 'icon-mc-notice-shield',
        onClick: e => actionClickFn(e, handleQuickShield),
      },
      {
        id: 'alarm_dispatch',
        name: t('告警分派'),
        icon: 'icon-fenpai',
        onClick: e => actionClickFn(e, handleAlarmDispatch),
      },
      {
        id: 'feedback_new_root_cause',
        name: t('反馈根因'),
        icon: 'icon-fankuixingenyin',
        onClick: e => actionClickFn(e, handleRootCauseConfirm),
      },
    ]);
    const timeLineZoomRef = ref(null);
    const ratio = ref<number>(0);
    const processRef = ref<HTMLDivElement>();
    const activeName = inject<Ref>('activeName');
    const feedbackIncidentRootApi = (isCancel, data) => {
      const { bk_biz_id, id } = data;
      const params = {
        id: incidentId.value,
        incident_id: incidentDetail.value?.incident_id,
        bk_biz_id,
        feedback: {
          incident_root: data.entity.entity_id,
          content: '',
        },
        is_cancel: isCancel,
      };
      feedbackIncidentRoot(params).then(() => {
        Message({
          theme: 'success',
          message: t('取消反馈成功'),
        });
        incidentRecordOperation({
          id,
          incident_id: incidentDetail.value?.incident_id,
          bk_biz_id,
          operation_type: 'feedback',
          extra_info: {
            feedback_incident_root: '',
            is_cancel: isCancel,
          },
        }).then(res => {
          res && setTimeout(() => emit('refresh'), 2000);
        });
      });
    };
    /** 设置各种操作弹框需要的数据 */
    const setDialogData = data => {
      currentIds.value = [data.id];
      currentBizIds.value = [data.bk_biz_id];
    };
    const handleRootCauseConfirm = v => {
      if (v.is_feedback_root) {
        feedbackIncidentRootApi(true, v);
        return;
      }
      setDialogData(v);
      dialog.value.rootCauseConfirm.show = true;
    };
    const handleAlarmDispatch = v => {
      setDialogData(v);
      handleAlarmDispatchShowChange(true);
    };
    const handleManualProcess = v => {
      setDialogData(v);
      manualProcessShowChange(true);
    };

    const handleQuickShield = v => {
      setDialogData(v);
      dialog.value.quickShield.show = true;
      dialog.value.quickShield.details = [
        {
          severity: v.severity,
          dimension: v.dimension_message,
          trigger: v.description,
          strategy: {
            id: v?.strategy_id as unknown as string,
            name: v?.strategy_name,
          },
        },
      ];
    };

    const operationsListData = computed(() => {
      return operationsList.value || [];
    });
    const operationTypeMapData = computed(() => {
      return operationTypeMap.value || [];
    });
    const treeDataList = computed(() => {
      return props.alertAggregateData;
    });
    const tickWidth = ref(0);
    const formatTime = (time: any, str = 'YYYY-MM-DD HH:mm:ss') => {
      return dayjs(time).format(str);
    };
    const setEndTime = time => {
      return time || Math.floor(new Date().getTime() / 1000);
    };
    /** 处理告警树数据 */
    const handleData = (scopedData, parent = { isOpen: false }) => {
      scopedData.map(item => {
        if (item.level_name === 'status' && !Object.keys(statusEnum.value).includes(item.id)) {
          statusEnum.value[item.id] = item.name;
        }
        const isHasChild = item.children?.length > 0;
        const info = {
          isShow: item.level_name === 'status' ? true : parent.isOpen,
          isDraw: !(isHasChild && item?.isOpen),
        };
        treeData.value.push(Object.assign(item, info));
        if (item.children?.length > 0) {
          handleData(item.children, item);
        }
      });
    };
    /** 步长等相关计算 */
    const calculatedEnum = () => {
      calculatedVariables();
      getTickStep();
    };
    /** 宽高度 */
    const resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        clientWidth.value = entry.contentRect.width;
        mainWidth.value = clientWidth.value + percentage.value * clientWidth.value * 2;
        clientHeight.value = entry.contentRect.height;
        calculatedEnum();
      }
    });
    /** 计算刻度宽度 */
    const calculatedVariables = () => {
      tickWidth.value = Number((mainWidth.value / showTickArr.value.length).toFixed(3));
      hourWidth.value = Number((tickWidth.value / timeInterval.value / 24).toFixed(3));
      maxCircleTotal.value = Math.floor(tickWidth.value / 35);
    };
    /** 动态计算坐标轴刻度 */
    const handleTick = (ind = 10) => {
      const startTime = addDays(tickArr.value[0], 0.1);
      const endTime = addDays(tickArr.value[tickArr.value.length - 1], 1);
      const calculateDays = calculateBetweenDays(startTime, endTime);
      isHour.value = calculateDays / ind <= 1;
      showTickArr.value = splitTimeRangeIntoTwelve(startTime, endTime, ind);
    };

    const getTickStep = () => {
      const len = showTickArr.value.length;
      beginTick.value = new Date(showTickArr.value[0]).getTime() / 1000;
      const endTick = new Date(showTickArr.value[len - 1]).getTime() / 1000;
      const count = endTick - beginTick.value;
      tickStep.value = mainWidth.value / count;
    };
    /** 获取开始的时间点和小时跨度 */
    const getDateAndHour = (time: number) => {
      const date = time ? formatTime(time * 1000) : formatTime(new Date());
      const startDay = (date || '').split(' ')[0];
      if (tickArr.value.findIndex(ele => ele === startDay) === -1) {
        tickArr.value.push(startDay);
      }
      const startDate = new Date(date);
      const startsHour = startDate.getHours();
      return {
        date,
        day: startDay,
        hour: startsHour,
        minute: startDate.getMinutes(),
      };
    };
    /** 获取柱状的位置 */
    const getTickBarLocation = data => {
      const begin = getBeginTick(data.date);
      if (begin !== -1) {
        const step = getDateTime(showTickArr.value[1]) - getDateTime(showTickArr.value[0]);
        const cur = getDateTime(data.date) - getDateTime(showTickArr.value[begin]);
        const num = (tickWidth.value / step) * cur;
        const beginX = begin * tickWidth.value + num + tickWidth.value / 2;
        return beginX;
      }
      return clientWidth.value;
    };
    /** 计算时序图中柱状的起始位置和宽度 */
    const handleChildPosition = data => {
      const { begin_time, end_time } = data;
      const start = getDateAndHour(begin_time);
      const end = getDateAndHour(setEndTime(end_time));
      const beginX = getTickBarLocation(start);
      const stopX = getTickBarLocation(end);
      const width = stopX - beginX;
      return { width, beginX, stopX };
    };
    /** 计算时间刻度 */
    function splitTimeRangeIntoTwelve(start, end, ind = 12) {
      const startDate = new Date(start);
      const endDate = new Date(end);
      const totalDuration = endDate.getTime() - startDate.getTime();
      segmentDuration.value = totalDuration / ind;
      const timePoints = [];
      for (let i = 0; i <= ind; i++) {
        const segmentTime = new Date(startDate.getTime() + segmentDuration.value * i);
        timePoints.push(segmentTime);
      }

      return timePoints;
    }

    /** 计算坐标轴 */
    /** 计算时间间隔 */
    const calculateBetweenDays = (date1, date2) => {
      const day = timeDay.count(new Date(date1), new Date(date2));
      return day;
    };
    const getDateTime = time => {
      return new Date(time).getTime();
    };
    /** 获取开始的时间刻度 */
    const getBeginTick = data => {
      return showTickArr.value.findIndex((item, ind) => {
        const date = getDateTime(data);
        return date >= getDateTime(item) && date <= getDateTime(showTickArr.value[ind + 1]);
      });
    };
    /** 给定的日期添加指定的天数 */
    const addDays = (date, hours) => {
      const result = new Date(date);
      result.setHours(result.getHours() + hours);
      return result;
    };
    const setTickArr = date => {
      const time = formatTime(date * 1000);
      !tickArr.value.includes(time) && tickArr.value.push(time);
    };
    /** 计算时间更接近于哪个刻度 */
    const categorizeDataByNearestTime = (timeArray, dataList) => {
      // 将时间字符串数组转换为Date对象数组
      const times = timeArray.map(time => time.getTime());
      const result = timeArray.reduce((acc, time) => {
        acc[time.getTime()] = [];
        return acc;
      }, {});
      // biome-ignore lint/complexity/noForEach: <explanation>
      dataList.forEach(data => {
        const dataTime = data.create_time * 1000;
        const nearestTime = times.reduce((nearest, currentTime) => {
          /** 两个时刻刻度的中间值 */
          const midTime = (nearest + currentTime) / 2;
          return dataTime > midTime ? currentTime : nearest;
        });
        if (result[nearestTime] !== undefined) {
          result[nearestTime].push(data);
        }
      });
      return result;
    };

    watch(
      () => currentSpan.value,
      val => {
        const isFeedBackRoot = val?.is_feedback_root;
        const name = !isFeedBackRoot ? t('反馈根因') : t('取消反馈根因');
        const icon = !isFeedBackRoot ? 'icon-fankuixingenyin' : 'icon-mc-cancel-feedback';
        const item = actionList.value.find(item => item.id === 'feedback_new_root_cause');
        Object.assign(item, {
          name,
          icon,
        });
      }
    );

    watch(
      () => props.scrollTop,
      val => {
        timeMainRef.value.scrollTo({
          top: val,
        });
      }
    );
    watch(
      () => treeDataList.value,
      val => {
        if (val) {
          treeData.value = [];
          handleData(val);
        }
      },
      { deep: true, immediate: true }
    );

    watch(
      () => operationsListData.value,
      val => {
        val.map(item => {
          setTickArr(item.create_time);
          setTickArr(setEndTime(item.end_time));
        });
      },
      { immediate: true }
    );

    watch(
      () => tickArr.value,
      val => {
        tickArr.value = val.sort((a: string, b: string) => {
          const aTime: any = new Date(a);
          const bTime: any = new Date(b);
          return aTime - bTime;
        });
        const len = tickArr.value.length - 1;
        len > 0 && handleTick();
      },
      { immediate: true, deep: true }
    );
    watch(
      () => showTickArr.value,
      val => {
        if (val.length > 2) {
          timeInterval.value = calculateBetweenDays(val[0], val[1]);
        }
        calculatedEnum();
        timeData.value = categorizeDataByNearestTime(val, operationsListData.value);
      },
      { immediate: true }
    );
    const handlePopover = val => {
      keyIdList.value.map(item => processPopoverRefs.value[`process${item}`]?.hide());
      circleOnClick([val]);
      const key = keyIdList.value.filter(item => item.indexOf(val.id) !== -1);
      setTimeout(() => processPopoverRefs.value[`process${key[0]}`]?.show(), 100);
    };
    watch(
      () => props.chooseOperation,
      val => {
        handlePopover(val);
        if (percentage.value !== 0) {
          nextTick(() => {
            const activeElements: any = processRef.value.querySelectorAll('.active');
            if (activeElements.length > 0) {
              const num = -activeElements[0].offsetLeft + 100;
              const max = timelineRef.value.offsetWidth - timeLineMainRef.value.offsetWidth;
              mainLeft.value = num > max ? num : max;
              ratio.value = mainLeft.value / max;
            }
          });
        }
      }
    );
    watch(
      () => activeName.value,
      () => {
        setTimeout(() => handlePopover(props.chooseOperation), 100);
      },
      { immediate: true }
    );
    onMounted(() => {
      resizeObserver.observe(timelineRef.value);
    });
    onBeforeUnmount(() => {
      resizeObserver?.unobserve(timelineRef.value);
    });

    const getSeverity = severity => {
      const info = Object.values(EVENT_SEVERITY)[severity - 1];
      return (
        <span class='severity-info'>
          <i class={`icon-monitor icon-${info.icon} ${info.key}`} />
          {info.label}
        </span>
      );
    };
    const alertNameFn = (alert, child, ind, alertIds) => {
      const name = alert?.alert_name;
      const len = child.length;
      return (
        <span class='alert-name'>
          {/* biome-ignore lint/a11y/noLabelWithoutControl: <explanation> */}
          <label
            class='blue'
            title={name}
            onClick={() => {
              tickPopoverRefs.value[`tick${ind}`]?.hide();
              showToolMenu.value = false;
              window.__BK_WEWEB_DATA__?.showDetailSlider?.(JSON.parse(JSON.stringify({ ...currentSpan.value })));
            }}
          >
            {name}{' '}
          </label>
          {len > 1 && (
            // biome-ignore lint/a11y/noLabelWithoutControl: <explanation>
            <label>
              {t('等共 ')}
              <b
                class='blue'
                onClick={() => {
                  const alertObj = {
                    ids: t(`告警ID: ${alertIds.join(' OR 告警ID: ')}`),
                    label: t(`${name} 等共 ${len} 个告警`),
                  };
                  emit('goAlertDetail', alertObj);
                }}
              >
                {len}
              </b>{' '}
              {t('个告警')}
            </label>
          )}
        </span>
      );
    };

    const renderInfo = (item, ind) => {
      const { alert_example, is_root, level_name, is_feedback_root, alert_ids, children, status, is_ack } = item;
      const infoConfig = {
        // alert_name: {label: t('告警名称'), renderFn: (alert) => alertNameFn(alert, alert_ids, ind)},
        severity: { label: t('级别'), renderFn: severity => getSeverity(severity) },
        bk_biz_name: { label: t('业务名称') },
        category_display: { label: t('分类') },
        metric: { label: t('告警指标') },
        status: {
          label: t('告警状态'),
          renderFn: status => (
            <span class={`info-status ${status}`}>
              <i class={`icon-monitor icon-${TREE_SHOW_ICON_LIST.status[status]}`} />
              {statusEnum.value[status]}
            </span>
          ),
        },
        begin_time: { label: t('告警开始时间'), renderFn: time => formatTime(time * 1000) },
        end_time: {
          label: t('告警结束时间'),
          renderFn: time => (time ? formatTime(time * 1000) : formatTime(new Date())),
        },
        assignee: { label: t('负责人') },
        dimension_message: { label: t('维度信息') },
        description: { label: t('告警内容') },
      };
      const isConfirmDisabled = is_ack || ['RECOVERED', 'CLOSED'].includes(status);
      const isEn = getCookie('blueking_language') === 'en';
      return (
        <div class='tool-div'>
          <div class='tool-text'>
            <i class={`icon-monitor item-icon icon-${level_name === 'alert_name' ? 'gaojing1' : 'Pod'}`} />
            {/* biome-ignore lint/a11y/noLabelWithoutControl: <explanation> */}
            <label class='tool-name'>{alertNameFn(alert_example, children, ind, alert_ids)}</label>
            {(is_root || is_feedback_root) && (
              <span class={['root', { 'feedback-root': is_feedback_root }]}>{t('根因')}</span>
            )}
            <i
              class='more-icon'
              onClick={() => {
                showToolMenu.value = !showToolMenu.value;
              }}
            >
              <i class='icon-monitor icon-mc-more' />
            </i>
            {showToolMenu.value && (
              <div class='more-list'>
                {actionList.value.map(item => (
                  <div
                    key={item.id}
                    class={[
                      'list-item',
                      {
                        disabled:
                          (item.id === 'feedback_new_root_cause' && is_root) ||
                          (item.id === 'alert_confirm' && isConfirmDisabled),
                      },
                    ]}
                    onClick={() => {
                      const isFeedDisabled = item.id === 'feedback_new_root_cause' && is_root;
                      const isConfirmDis = item.id === 'alert_confirm' && isConfirmDisabled;
                      if (isFeedDisabled || isConfirmDis) {
                        return;
                      }
                      tickPopoverRefs.value[`tick${ind}`]?.hide();
                      item.onClick(currentSpan.value);
                    }}
                  >
                    <i
                      style='margin-right: 4px;'
                      class={['icon-monitor', item.icon]}
                    />
                    {item.name}
                  </div>
                ))}
              </div>
            )}
          </div>
          {!!alert_example &&
            Object.keys(infoConfig).map(key => {
              const info = infoConfig[key];
              return (
                <div
                  key={key}
                  class='tool-text'
                >
                  {/* biome-ignore lint/a11y/noLabelWithoutControl: <explanation> */}
                  <label
                    style={{ 'min-width': isEn ? '98px' : '90px' }}
                    class='tool-label'
                  >
                    {info.label}：
                  </label>
                  <span class='tool-info'>
                    {info?.renderFn ? info.renderFn(alert_example[key]) : alert_example[key] || '--'}
                  </span>
                </div>
              );
            })}
        </div>
      );
    };
    /** 根据指定key值分类处理数据 */
    const groupBy = (dataArray, key) => {
      const result = {};
      // biome-ignore lint/complexity/noForEach: <explanation>
      dataArray.forEach(item => {
        const keyValue = item[key];
        // 检查该key是否已存在于结果对象中，如果不存在，则初始化为空数组
        if (!result[keyValue]) {
          result[keyValue] = [];
        }
        result[keyValue].push(item);
      });
      return result;
    };
    /** 根据提供的时间差值，将在差值内的数据进行合并 */
    const mergeEntriesBasedOnKeyDifference = (obj, specifiedDifference) => {
      // 提取对象键，并转换为数字进行排序
      const keys = Object.keys(obj)
        .map(Number)
        .sort((a, b) => a - b);
      // 初始化结果数组和当前合并数组
      const result = [];
      let currentMerge = [];
      for (let i = 0; i < keys.length; i++) {
        // 将当前键对应的值添加到当前合并数组中
        currentMerge.push(...obj[keys[i].toString()]);
        // 检查当前键是否为最后一个键或者下一个键与当前的差值大于指定的差值
        if (i === keys.length - 1 || keys[i + 1] - keys[i] > specifiedDifference) {
          // 将当前合并数组添加到结果中，并重置当前合并数组
          result.push(currentMerge);
          currentMerge = [];
        }
      }
      return result;
    };
    /** 点击选中 */
    const circleOnClick = data => {
      operationsList.value.filter(item => {
        const isActive = data.findIndex(ele => ele.id === item.id) !== -1;
        return Object.assign(item, { isActive });
      });
    };
    const handleCallback = type => {
      if (type === 'incident_create') {
        emit('changeTab');
      }
      keyIdList.value.map(item => processPopoverRefs.value[`process${item}`]?.hide());
    };
    const renderPopoverContent = ele => (
      <div class='operations-tips'>
        <span class='tips-item'>{formatTime(ele.create_time * 1000)}</span>
        <span class='tips-type'>{t(operationTypeMapData.value[ele.operation_type]) || '--'}</span>
        <span class='tips-item'>
          {renderMap[ele.operation_type]?.(ele, incidentId.value, incidentDetail.value?.bk_biz_id, () =>
            handleCallback(ele.operation_type)
          ) || '--'}
        </span>
      </div>
    );
    /** 绘制流转的圆 */
    const renderCircle = (isMore, ele, index: number) => {
      const step = mainWidth.value / (segmentDuration.value * showTickArr.value.length);
      const daysDiff = ele[0].create_time * 1000 - Number(showTickArr.value[index]);
      const offset = daysDiff * step;
      const distance = offset + tickWidth.value * index + tickWidth.value / 2;
      const number = ele.length;
      const isNumber = number > 1 || isMore;
      const edgeValue = distance - index * tickWidth.value;
      const edgeEnum = 5.5;
      const icon = (
        <i
          class={[
            'icon-monitor item-icon',
            ele[0].operation_class === 'system'
              ? ele[0].operation_type.startsWith('alert')
                ? 'icon-gaojing1'
                : 'icon-mc-fault'
              : 'icon-mc-user-one',
          ]}
        />
      );
      return (
        <span
          style={{ left: `${edgeValue < edgeEnum ? distance + edgeEnum : distance}px` }}
          class={[
            'tick-item-circle',
            { active: isNumber ? ele.findIndex(item => item.isActive) !== -1 : ele[0]?.isActive },
          ]}
          onClick={() => circleOnClick(ele)}
        >
          {isNumber ? number : icon}
        </span>
      );
    };
    /** 绘制流转的圆popover */
    const renderPopover = (isMore, ele, index) => {
      const len = ele.length;
      const setItemRef = (el, key) => {
        el && (processPopoverRefs.value[key] = el);
      };
      const keyId = ele.map(item => item.id).join('');
      const isHas = keyIdList.value.find(item => item === keyId);
      !isHas && keyIdList.value.push(keyId);
      return (
        <Popover
          ref={el => setItemRef(el, `process${keyId}`)}
          extCls={`operations-popover${len > 1 ? '-more' : ''}`}
          v-slots={{
            content: () => {
              if (len > 1 || isMore) {
                const showTipsList = ele.slice(0, 5);
                return (
                  <div>
                    {showTipsList.map(item => renderPopoverContent(item))}
                    {len > 5 && len - 5 !== 0 && <div class='operations-more'>...</div>}
                  </div>
                );
              }
              return renderPopoverContent(ele[0]);
            },
          }}
          arrow={false}
          maxWidth={360}
          offset={{ mainAxis: len > 1 ? -18 : -6, alignmentAxis: len > 1 ? 12 : 22 }}
          placement='right-start'
          theme='light'
          trigger='click'
          zIndex={1025}
        >
          {renderCircle(isMore, ele, index)}
        </Popover>
      );
    };
    const groupAndMerge = (list: Operation[], interval: number): GroupResult => {
      const groupList = groupBy(list, 'create_time');
      const children = mergeEntriesBasedOnKeyDifference(groupList, interval);
      const isMore = children.length > maxCircleTotal.value;

      return {
        list: children.slice(0, maxCircleTotal.value),
        more: isMore,
      };
    };
    /** 渲染故障流转 */
    const renderOperation = () => {
      const interval = computed(() => Math.floor((segmentDuration.value / tickWidth.value) * 25) / 1000);
      const content = [];
      Object.entries(timeData.value || {}).forEach(([, operations = []], index) => {
        if ((operations || []).length !== 0) {
          const sortedOperations = (operations || []).sort((a, b) => a.create_time - b.create_time);
          const { list: groupList, more: isMore } = groupAndMerge(sortedOperations, interval.value);

          content.push(...groupList.map(group => renderPopover(false, group, index)));
          if (isMore) {
            const moreList = groupList.slice(maxCircleTotal.value - 1).flat();
            content.push(renderPopover(true, moreList, index));
          }
        }
      });
      return content;
    };

    /** 等比例缩放时间 */
    const zoomChange = (val: number, percent) => {
      mainWidth.value = clientWidth.value + percent * clientWidth.value * 2;
      percentage.value = percent;
      mainLeft.value = (clientWidth.value - mainWidth.value) / 2;
      calculatedEnum();
      handleTick(Math.floor(mainWidth.value / 130));
    };
    const zoomMove = (ratio: number) => {
      const maxTransformX = timelineRef.value.offsetWidth - timeLineMainRef.value.offsetWidth;
      mainLeft.value = maxTransformX * ratio;
    };
    const handleAlertConfirm = v => {
      setDialogData(v);
      dialog.value.alarmConfirm.show = true;
    };
    const handleFeedbackChange = (val: boolean) => {
      dialog.value.rootCauseConfirm.show = val;
    };
    const actionClickFn = (e: MouseEvent, fn) => {
      showToolMenu.value = false;
      fn?.(currentSpan.value);
    };
    const quickShieldChange = (v: boolean) => {
      dialog.value.quickShield.show = v;
    };
    /**
     * @description: 手动处理
     * @param {*} v
     * @return {*}
     */
    const manualProcessShowChange = (v: boolean) => {
      dialog.value.manualProcess.show = v;
    };
    /* 手动处理轮询状态 */
    const handleDebugStatus = (actionIds: number[]) => {
      dialog.value.manualProcess.actionIds = actionIds;
      dialog.value.manualProcess.debugKey = random(8);
    };
    const handleMealInfo = (mealInfo: { name: string }) => {
      dialog.value.manualProcess.mealInfo = mealInfo;
    };
    const handleAlarmDispatchShowChange = v => {
      dialog.value.alarmDispatch.show = v;
    };
    const alarmConfirmChange = v => {
      dialog.value.alarmConfirm.show = v;
    };
    const refresh = () => {
      emit('refresh');
    };
    function getTransformX(elem) {
      const style: any = window.getComputedStyle(elem);
      const matrix = style.transform || style.webkitTransform || style.mozTransform;
      if (matrix === 'none' || !matrix) return 0;
      const values = matrix.match(/matrix.*\((.+)\)/)[1].split(', ');
      return Number.parseFloat(values[4]);
    }
    /** 时序图位置变化处理方法  */
    const onTimeLineMouseHandle = (deltaX: number) => {
      const selection: any = timeLineMainRef.value;
      const startTransform = getTransformX(selection);
      const newTransformX = startTransform + deltaX;
      const maxTransformX = selection.offsetWidth - selection.parentNode.offsetWidth;
      const newPos = Math.max(-maxTransformX, Math.min(maxTransformX, newTransformX));
      const ratio = newPos / maxTransformX;
      mainLeft.value = newPos > 0 ? 0 : newPos;
      mouseRatio.value = Number(Math.abs(ratio).toFixed(3));
    };
    const onTimeLineMainMouseDown = (event: MouseEvent) => {
      if (percentage.value === 0) {
        return;
      }
      timeLineMainRef.value.style.cursor = 'grabbing';
      isDragging.value = true;
      const startX = event.clientX;

      const onMouseMove = (e: MouseEvent) => {
        if (!isDragging.value) return;
        const deltaX = e.clientX - startX;
        onTimeLineMouseHandle(deltaX);
      };
      const onMouseUp = () => {
        timeLineMainRef.value.style.cursor = percentage.value > 0 ? 'grab' : 'default';
        isDragging.value = false;
        timeLineMainRef.value.removeEventListener('mousemove', onMouseMove);
        timeLineMainRef.value.removeEventListener('mouseup', onMouseUp);
      };
      timeLineMainRef.value.addEventListener('mousemove', onMouseMove);
      timeLineMainRef.value.addEventListener('mouseup', onMouseUp);
    };
    // 滚轮事件处理，缩放时序图
    const handleWheel = e => {
      e.stopPropagation();
      e.preventDefault();

      const selection = timeLineMainRef.value as HTMLElement;
      const offsetWidth = selection.offsetWidth;
      const rect = selection.getBoundingClientRect();
      const parentWidth = (selection.parentNode as HTMLElement).offsetWidth;
      const delta = e.deltaY;
      const mouseX = e.clientX - rect.left;
      const startTransform = getTransformX(selection);
      const maxTransformX = offsetWidth - parentWidth;
      const ratioBeforeZoom = startTransform / maxTransformX;

      // 联动缩放
      timeLineZoomRef.value.handleUpdateZoom(delta > 0 ? -2 : 2);

      // 需要根据当前鼠标停留位置，重新计算缩放后的最大偏移量
      const newMaxTransformX = Math.max(0, offsetWidth - parentWidth);

      const newMouseX = (mouseX / rect.width) * offsetWidth;
      const offsetChange = mouseX - newMouseX;

      // 计算新的偏移量
      const newTransformX = newMaxTransformX * ratioBeforeZoom;

      const newPos = Math.max(-newMaxTransformX, Math.min(0, newTransformX + offsetChange));

      // 更新偏移量，缩放倍率为0不在执行新的值，避免超出边界
      mainLeft.value = percentage.value === 0 ? 0 : newPos;

      // 更新鼠标比例
      const ratio = newMaxTransformX === 0 ? 0 : newPos / newMaxTransformX;
      mouseRatio.value = Number(Math.abs(ratio).toFixed(3));
      timeLineMainRef.value.style.cursor = percentage.value > 0 ? 'grab' : 'default';
    };
    return {
      t,
      currentSpan,
      treeData,
      timeData,
      tickWidth,
      treeDataList,
      timelineRef,
      handleChildPosition,
      maxCircleTotal,
      renderInfo,
      formatTime,
      tickArr,
      handleData,
      operationsList,
      renderOperation,
      handleTick,
      showTickArr,
      timeMainRef,
      zoomChange,
      isHour,
      zoomMove,
      mainWidth,
      mainLeft,
      timeLineMainRef,
      dialog,
      handleFeedbackChange,
      showToolMenu,
      quickShieldChange,
      manualProcessShowChange,
      handleDebugStatus,
      handleMealInfo,
      handleWheel,
      handleAlarmDispatchShowChange,
      alarmConfirmChange,
      tickPopoverRefs,
      currentIds,
      currentBizIds,
      incidentId,
      incidentDetail,
      actionList,
      refresh,
      percentage,
      processRef,
      ratio,
      onTimeLineMainMouseDown,
      mouseRatio,
      timeLineZoomRef,
    };
  },
  render() {
    const renderTreeContent = () => {
      return this.treeData.map((item, ind) => {
        const { level_name, is_root, is_feedback_root, isOpen, isDraw, alert_example } = item;
        const hasRoot = is_root || is_feedback_root;
        let content = null;
        if (level_name !== 'status' && isDraw) {
          const info = this.handleChildPosition(item);
          // const style = [item.alert_example?.status, { root: is_root, 'feedback-root': is_feedback_root }];
          const style = [{ root: is_root, 'feedback-root': is_feedback_root }];
          content = (
            <span
              style={{
                width: `${info.width || 2}px`,
                marginLeft: `${info.beginX}px`,
              }}
              class={['node-span', item.alert_example?.status]}
              onClick={() => {
                const curr: any = {
                  ...alert_example,
                  ...{ is_feedback_root, is_root, incident_id: this.incidentDetail?.incident_id },
                };
                this.currentSpan = curr;
              }}
            >
              {hasRoot ? <span class={['root-text', ...style]}>{this.t('根因')}</span> : ''}
            </span>
          );
        }
        const setItemRef = (el, key) => {
          el && (this.tickPopoverRefs[key] = el);
        };
        const treeItem = (item, ind) => {
          if (item.isDraw) {
            return (
              <Popover
                ref={el => setItemRef(el, `tick${ind}`)}
                extCls='tick-popover'
                v-slots={{
                  content: this.renderInfo(item, ind),
                }}
                arrow={false}
                maxWidth={600}
                offset={{ mainAxis: -10, alignmentAxis: -10 }}
                placement='right-start'
                theme='light'
                trigger='click'
                onAfterHidden={() => (this.showToolMenu = false)}
              >
                {content}
              </Popover>
            );
          }
          return '';
        };
        return (
          item.isShow && <div class='tree-item'>{level_name === 'status' && !isOpen ? '' : treeItem(item, ind)}</div>
        );
      });
    };
    return (
      <div
        ref='timelineRef'
        class='timeline-diagram'
      >
        <div
          ref='timeLineMainRef'
          style={{
            width: `${this.mainWidth}px`,
            transform: `translateX(${this.mainLeft}px)`,
          }}
          class='timeline-diagram-main'
          onMousedown={this.onTimeLineMainMouseDown}
          onWheel={this.handleWheel}
        >
          <ul class='time-tick'>
            {(this.showTickArr || []).map(item => {
              const time = !this.isHour ? this.formatTime(item).split(' ')[0] : this.formatTime(item, 'YY-MM-DD HH:mm');
              return (
                <li
                  key={item}
                  style={{ width: `${this.tickWidth}px` }}
                  class='time-view-tick'
                >
                  <span class='tick-name'>{time}</span>
                  <span class='tick-line' />
                </li>
              );
            })}
          </ul>
          <div class='time-view'>
            {(this.showTickArr || []).map(item => (
              <span
                key={item}
                style={{ width: `${this.tickWidth}px` }}
                class='time-view-tick'
              >
                <span class='tick-line' />
              </span>
            ))}
            <div
              ref='processRef'
              class='time-view-process'
            >
              {this.renderOperation()}
            </div>
          </div>
          <div class='time-main'>
            <div
              ref='timeMainRef'
              class='tree-container bk-scroll-y'
            >
              {renderTreeContent()}
            </div>
          </div>
        </div>
        <TimelineZoom
          ref='timeLineZoomRef'
          mouseRatio={this.mouseRatio}
          ratio={this.ratio}
          showTickArr={this.showTickArr}
          treeData={this.treeDataList}
          onMove={this.zoomMove}
          onZoom={this.zoomChange}
        />
        <FeedbackCauseDialog
          data={this.currentSpan}
          visible={this.dialog.rootCauseConfirm.show}
          onRefresh={this.refresh}
          onUpdate:isShow={this.handleFeedbackChange}
        />
        <QuickShield
          bizIds={this.currentBizIds}
          data={this.currentSpan}
          details={this.dialog.quickShield.details}
          ids={this.currentIds}
          show={this.dialog.quickShield.show}
          onChange={this.quickShieldChange}
          onRefresh={this.refresh}
        />
        <ManualProcess
          alertIds={this.currentIds}
          bizIds={this.currentBizIds}
          data={this.currentSpan}
          show={this.dialog.manualProcess.show}
          onDebugStatus={this.handleDebugStatus}
          onMealInfo={this.handleMealInfo}
          onRefresh={this.refresh}
          onShowChange={this.manualProcessShowChange}
        />
        <AlarmDispatch
          alertIds={this.currentIds}
          bizIds={this.currentBizIds}
          data={this.currentSpan}
          show={this.dialog.alarmDispatch.show}
          onRefresh={this.refresh}
          onShow={this.handleAlarmDispatchShowChange}
        />
        <AlarmConfirm
          bizIds={this.currentBizIds}
          data={this.currentSpan}
          ids={this.currentIds}
          show={this.dialog.alarmConfirm.show}
          onChange={this.alarmConfirmChange}
          onRefresh={this.refresh}
        />
      </div>
    );
  },
});
