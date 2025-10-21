import { shallowRef, watchEffect } from "vue"
import { AlarmType } from "../typings"
import { onScopeDispose } from "vue"
import { fetchAlarmDetail,fetchListAlertFeedback } from "../services/alarm-detail"

export function useAlarmDetail() {
  /** 详情展示 */
  const detailShow = shallowRef(false)
  /** 详情类型 */
  const detailType = shallowRef(AlarmType.ALERT)
  /** 详情id索引 */
  const currentDetailIndex = shallowRef(0)
  /** 选择的详情id */
  const currentDetailId = shallowRef('')
  /** 详情数据 */
  const detailData = shallowRef({
    id: '', // 告警id
    bk_biz_id: 0, // 业务id
    alert_name: '', // 告警名称
    first_anomaly_time: 0, // 首次异常事件
    begin_time: 0, // 事件产生事件
    create_time: 0, // 告警产生时间
    is_ack: false, // 是否确认
    is_shielded: false, // 是否屏蔽
    is_handled: false, // 是否已处理
    dimension: [], // 维度信息
    severity: 0, // 严重程度
    status: '',
    description: '', //
    alert_info: {
      count: 0,
      empty_receiver_count: 0,
      failed_count: 0,
      partial_count: 0,
      shielded_count: 0,
      success_count: 0,
    },
    duration: '',
    dimension_message: '',
    overview: {}, // 处理状态数据
    assignee: [],
  })
  /** 详情loading */
  const detailLoading = shallowRef(false)
  /** 是否反馈 */
  const isFeedback = shallowRef(false)

  const getAlertDetailData = async (id: string) => {
    if (!id) return
    detailLoading.value = true;
    const data = await fetchAlarmDetail(id).catch(() => false).finally(() => {
      detailLoading.value = false;
    })
    if (data) {
      detailData.value = data
    }
  }

  const getAlertFeedback = async () => {
    const data = await fetchListAlertFeedback(detailData.value.id, detailData.value.bk_biz_id).catch(() => [])
    isFeedback.value = data.length > 0
  }

  watchEffect(async () => {
    if (detailShow.value) {
      switch (detailType.value) {
        case AlarmType.ALERT:
          await getAlertDetailData(currentDetailId.value)
          await getAlertFeedback()
          break;
        case AlarmType.ACTION:
          break;
        case AlarmType.INCIDENT:
          break;
      }
    }
  })

  onScopeDispose(() => {
    detailShow.value = false
    currentDetailId.value = ''
    detailType.value = AlarmType.ALERT
    detailData.value = null
    detailLoading.value = false

  });

  return {
    detailShow,
    currentDetailId,
    detailType,
    isFeedback,
    currentDetailIndex,
    detailData,
    detailLoading,
    getAlertDetailData
  }
}