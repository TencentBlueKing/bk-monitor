import { defineComponent } from 'vue';

import type { LogItem, UserReportStats } from '../types';

import './index.scss';

/** 详细信息项配置 */
interface DetailItemConfig {
  icon: string;
  label: string;
  /** 从 LogItem 中取值的字段名，与 render 互斥 */
  field?: keyof LogItem;
  /** 自定义渲染右侧内容，优先级高于 field */
  render?: (userInfo: LogItem, reportStats: UserReportStats) => JSX.Element;
}

/** 详细信息项配置 */
const detailConfig: DetailItemConfig[] = [
  { icon: 'bklog-client-log', label: '设备型号', field: 'model' },
  { icon: 'bklog-version', label: '当前版本', field: 'sdk_version' },
  { icon: 'bklog-os', label: '操作系统', field: 'os_version' },
  { icon: 'bklog-wangluo-line', label: '网络状态', render: (_userInfo, _reportStats) => (
      <span class='value'>--</span>
    ),
  },
  {
    icon: 'bklog-business',
    label: '累计上报',
    render: (_userInfo, reportStats) => (
      <span class='value'>
        <span><span class='count'>{reportStats.total_count}</span> {window.$t('次')}</span>
        <span>（{window.$t('检索时间范围下')}
          <span class='count' style={{ margin: '0 2px' }}>{reportStats.range_count}</span>{window.$t('次')}）
        </span>
      </span>
    ),
  },
];

export default defineComponent({
  name: 'UserInfoCard',
  props: {
    /** 用户基本信息，来自 LogItem */
    userInfo: {
      type: Object as () => LogItem,
      default: null,
    },
    /** 用户累计上报统计 */
    userReportStats: {
      type: Object as () => UserReportStats,
      default: null,
    },
  },
  setup(props) {
    /** 渲染单个详情项 */
    const renderDetailItem = (item: DetailItemConfig, userInfo: LogItem, reportStats: UserReportStats) => (
      <div class='detail-item'>
        <i class={`bklog-icon ${item.icon}`}></i>
        <span class='label'>{window.$t(item.label)}：</span>
        {item.render ? item.render(userInfo, reportStats) : <span class='value'>{userInfo[item.field!]}</span>}
      </div>
    );

    return () => {
      const userInfo = props.userInfo;
      const reportStats = props.userReportStats;

      return (
        <div class='user-info-card card-base'>
          {/* 左侧用户图标 */}
          <div class='user-avatar'>
            <i class='bklog-icon bklog-user-yonghu'></i>
          </div>

          {/* 用户基本信息 */}
          <div class='user-basic-info'>
            <div class='user-name'>{window.$t('用户')} {userInfo.openid}</div>
            <div class='device-id'>{userInfo.xid}</div>
          </div>

          {/* 详细信息 */}
          <div class='detail-info'>
            {detailConfig.map(item => renderDetailItem(item, userInfo, reportStats!))}
          </div>
        </div>
      );
    };
  },
});
