import { defineComponent } from 'vue';

import type { LogItem, UserReportStats } from '../types';
import { formatTimeZoneString } from '@/global/utils/time';

import './index.scss';

/** 详细信息项配置 */
interface DetailItemConfig {
  icon: string;
  label: string;
  /** 从 LogItem 中取值的字段名，与 render 互斥 */
  field?: keyof LogItem;
  /** 自定义渲染右侧内容，优先级高于 field */
  // eslint-disable-next-line no-unused-vars
  render?: (userInfo: LogItem | null, reportStats: UserReportStats | null, taskList: LogItem[], timezone: string) => JSX.Element;
}

/** 详细信息项配置 */
const detailConfig: DetailItemConfig[] = [
  { icon: 'bklog-client-log', label: '设备型号', field: 'model' },
  { icon: 'bklog-version', label: '当前版本', field: 'sdk_version' },
  { icon: 'bklog-shijian', label: '最近活跃', render: (_userInfo, _reportStats, taskList, timezone) => {
    const time = taskList.find((item) => {
      const t = item.source === 'task' ? item.processed_at : item.report_time;
      return !!t;
    });
    const activeTime = time
      ? formatTimeZoneString(time.source === 'task' ? time.processed_at! : time.report_time!, timezone)
      : '';
    return <span class='value'>{activeTime || '--'}</span>;
  } },
  { icon: 'bklog-os', label: '操作系统', field: 'os_version' },
  {
    icon: 'bklog-business',
    label: '累计上报',
    render: (_userInfo, reportStats) => (
      <span class='value'>
        {reportStats
          ? [
              <span><span class='count'>{reportStats.total_count}</span> {window.$t('次')}</span>,
              <span>（{window.$t('检索时间范围下')}
                <span class='count' style={{ margin: '0 2px' }}>{reportStats.range_count}</span>{window.$t('次')}）
              </span>,
          ]
          : <span class='count'>--</span>
        }
      </span>
    ),
  },
];

export default defineComponent({
  name: 'UserInfoCard',
  props: {
    /** 用户基本信息，来自 LogItem */
    userInfo: {
      type: Object as () => LogItem | null,
      default: null,
    },
    /** 用户累计上报统计 */
    userReportStats: {
      type: Object as () => UserReportStats | null,
      default: null,
    },
    /** 任务列表，用于取最近活跃时间 */
    taskList: {
      type: Array as () => LogItem[],
      default: () => [],
    },
    /** 时区，用于时间格式化 */
    timezone: {
      type: String,
      default: '',
    },
    /** 是否折叠 */
    collapsed: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    /** 渲染单个详情项 */
    const renderDetailItem = (
      item: DetailItemConfig,
      userInfo: LogItem | null,
      reportStats: UserReportStats | null,
      taskList: LogItem[],
    ) => (
      <div class='detail-item'>
        <i class={`bklog-icon ${item.icon}`}></i>
        <span class='label'>{window.$t(item.label)}：</span>
        {item.render
          ? item.render(userInfo, reportStats, taskList, props.timezone)
          : <span class='value'>{(userInfo?.[item.field!] ?? '') || '--'}</span>}
      </div>
    );

    return () => {
      const userInfo = props.userInfo;
      const reportStats = props.userReportStats;
      const list = props.taskList;

      return (
        <div class={['user-info-card', 'card-base', { 'is-collapsed': props.collapsed }]}>
          {/* 左侧用户图标 */}
          <div class='user-avatar'>
            <i class='bklog-icon bklog-user-yonghu'></i>
          </div>

          {/* 用户基本信息 */}
          <div class='user-basic-info'>
            <div class='user-name'>{window.$t('用户')} {userInfo?.openid || ''}</div>
            <div class='device-id overflow-hidden-text' v-bk-overflow-tips>
              {userInfo?.xid || ''}
            </div>
          </div>

          {/* 详细信息 */}
          <div class='detail-info'>
            {detailConfig.map(item => renderDetailItem(item, userInfo, reportStats, list))}
          </div>
        </div>
      );
    };
  },
});
