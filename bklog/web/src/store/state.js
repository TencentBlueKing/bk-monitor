/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import {
  IndexFieldInfo,
  IndexItem,
  IndexSetQueryResult,
  getStorageOptions,
  indexSetClusteringData,
  urlArgs,
} from './default-values.ts';
import { BK_LOG_STORAGE } from './store.type.ts';

const stateTpl = {
  userMeta: {
    chname: '',
    language: '',
    operator: '',
    time_zone: '',
    username: '',
  }, // /meta/mine
  pageLoading: true,
  authDialogData: null,
  // 是否将unix时间戳格式化
  isFormatDate: true,
  // 当前运行环境
  runVersion: '',
  // 系统当前登录用户
  user: {},
  // 是否作为iframe被嵌套
  iframeQuery: {},
  // 当前项目及Id
  space: {},
  spaceUid: urlArgs.spaceUid ?? '',
  indexId: urlArgs.index_id ?? '',
  indexItem: { ...IndexItem },
  /** 联合查询ID列表 */
  unionIndexList: [...(urlArgs.unionList || [])],
  /** 联合查询元素列表 */
  unionIndexItemList: [],

  // 收藏列表
  favoriteList: [],

  /** 索引集对应的字段列表信息 */
  // @ts-ignore
  indexFieldInfo: { ...structuredClone(IndexFieldInfo) },
  indexSetQueryResult: { ...IndexSetQueryResult },
  indexSetFieldConfig: { clustering_config: { ...indexSetClusteringData } },
  indexSetFieldConfigList: {
    is_loading: false,
    data: [],
  },
  indexSetOperatorConfig: {
    /** 当前日志来源是否展示  用于字段更新后还保持显示状态 */
    isShowSourceField: false,
  },
  // 业务Id
  bkBizId: urlArgs.bizId ?? '',
  // 默认业务ID
  defaultBizId: '',

  // 我的项目列表
  mySpaceList: [],
  spaceListLoaded: false,
  currentMenu: {},
  topMenu: [],
  menuList: [],
  visibleFields: [],
  // 数据接入权限
  menuProject: [],
  // 全局配置
  globalsData: {},
  activeTopMenu: {},
  activeManageNav: {},
  activeManageSubNav: {},
  showFieldsConfigPopoverNum: 0,
  showRouterLeaveTip: false,
  // 新人指引
  userGuideData: {},
  curCustomReport: null,
  // demo 业务链接
  demoUid: '',
  spaceBgColor: '', // 空间颜色
  isEnLanguage: false,
  chartSizeNum: 0, // 自定义上报详情拖拽后 表格chart需要自适应新宽度
  isExternal: false, // 外部版
  /** 是否展示全局脱敏弹窗 */
  isShowGlobalDialog: false,
  /** 当前全局设置弹窗的活跃id */
  globalActiveLabel: 'masking-setting', // masking-setting
  /** 全局设置列表 */
  globalSettingList: [],
  /** 日志灰度 */
  maskingToggle: {
    toggleString: 'off',
    toggleList: [],
  },
  /** 外部版路由菜单 */
  externalMenu: [],
  isAppFirstLoad: true,
  /** 是否清空了显示字段，展示全量字段 */
  isNotVisibleFieldsShow: false,
  showAlert: false, // 是否展示跑马灯
  storeIsShowClusterStep: false,
  retrieveDropdownDataVersion: 0,
  fieldAggsItemsVersion: 0,
  operatorDictionaryVersion: 0,
  fieldMetaVersion: 0,
  fieldWidthVersion: 0,
  notTextTypeFields: [],
  isSetDefaultTableColumn: false,
  tookTime: 0,
  searchTotal: 0,
  clearSearchValueNum: 0,
  // 存放接口报错信息的对象
  apiErrorInfo: {},
  clusterParams: null,
  storage: {
    ...getStorageOptions({
      [BK_LOG_STORAGE.BK_BIZ_ID]: urlArgs.bizId,
      [BK_LOG_STORAGE.BK_SPACE_UID]: urlArgs.spaceUid,
    }),
  },
  features: {
    isAiAssistantActive: false,
  },
  localSort: false,
  dateTimeSort: false,
  dateTimeSortList: [],
  spaceUidMap: new Map(),
  bizIdMap: new Map(),
  aiMode: {
    active: false,
    filterList: [],
  },
};

export const createStoreState = () => structuredClone(stateTpl);
export default stateTpl;
