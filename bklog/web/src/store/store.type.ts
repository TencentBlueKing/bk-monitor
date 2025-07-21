enum BK_LOG_STORAGE {
  /**
   * 表格行是否换行
   */
  TABLE_LINE_IS_WRAP = '_0',

  /**
   * 是否展示json解析
   */
  TABLE_JSON_FORMAT = '_1',

  /**
   * json解析展示层级
   */
  TABLE_JSON_FORMAT_DEPTH = '_2',

  /**
   * 是否展示行号
   */
  TABLE_SHOW_ROW_INDEX = '_3',

  /**
   * 是否展示空字段
   */
  TABLE_ALLOW_EMPTY_FIELD = '_4',

  /**
   * 是否展开长字段
   */
  IS_LIMIT_EXPAND_VIEW = '_5',

  /**
   * 是否展示字段别名
   */
  SHOW_FIELD_ALIAS = '_6',

  /**
   * 文本溢出（省略设置）start | end | center
   */
  TEXT_ELLIPSIS_DIR = '_7',

  /**
   * 日志检索当前使用的检索类型： 0 - ui模式 1 - 语句模式
   */
  SEARCH_TYPE = '_8',

  /**
   * 左侧字段设置缓存配置
   */
  FIELD_SETTING = '_9',

  /**
   * 索引集激活的tab
   * single - 单选
   * union - 多选
   */
  INDEX_SET_ACTIVE_TAB = '_10',

  /**
   * 当前激活的收藏 id
   */
  FAVORITE_ID = 'f_11',

  /**
   * 当前激活的历史记录 id
   */
  HISTORY_ID = 'h_12',

  /**
   * 当前space_uid
   */
  BK_SPACE_UID = '_13',

  /**
   * 当前 bk_biz_id
   */
  BK_BIZ_ID = '_14',

  /**
   * 最后选择索引ID
   */
  LAST_INDEX_SET_ID = '_15',

  /**
   * 常用业务ID列表
   */
  COMMON_SPACE_ID_LIST = '_16',
}

export { BK_LOG_STORAGE };

export const SEARCH_MODE_DIC = ['ui', 'sql'];

export type ConsitionItem = {
  field: string;
  operator: string;
  value: string[];
  relation?: 'AND' | 'OR';
  isInclude?: boolean;
  field_type?: string;
};

export type RouteParams = {
  addition: ConsitionItem[];
  keyword: string;
  start_time: string;
  end_time: string;
  timezone: string;
  unionList: string[];
  datePickerValue: number;
  host_scopes: string[];
  ip_chooser: string[];
  search_mode: string;
  clusterParams: any;
  index_id?: string;
  bizId: string;
  spaceUid: string;
  format: string;
  [BK_LOG_STORAGE.HISTORY_ID]: string;
  [BK_LOG_STORAGE.FAVORITE_ID]: string;
};
