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

import { defineComponent, ref, onMounted, computed, onBeforeUnmount } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { isFeatureToggleOn } from '@/hooks/use-feature-toggle';
import { useRoute } from 'vue-router/composables';
import { InfoBox } from 'bk-magic-vue';
import { useOperation } from '../../hook/useOperation';
import { useCollectList } from '../../hook/useCollectList';
import { showMessage, visibleScopeSelectList } from '../../utils';
import { deepClone, deepEqual } from '@/common/util';
import { resolveCleanTemplateDraft } from '@/views/manage-v2/utils/clean-template';
import FieldList from '../business-comp/step3/field-list';
import ReportLogSlider from '../business-comp/step3/report-log-slider';
import CleanTemplateDialog from '../business-comp/step3/clean-template-dialog';
import CleanResultPreviewDialog from '../business-comp/step3/clean-result-preview-dialog';
import InfoTips from '../common-comp/info-tips';
import BklogPopover from '@/components/bklog-popover';
import GrokModeSwitch from '@/views/manage-v2/grok-manage/components/grok-mode-switch';
import GrokInput from '@/views/manage-v2/grok-manage/components/grok-input';
import { useSpaceSelector } from '../../../hooks/use-space-selector';
import * as authorityMap from '@/common/authority-map';
import $http from '@/api';
import {
  DEFAULT_EXPAND_DEPTH,
  EXT_JSON_EXPAND_DEPTH_TOGGLE,
  getExpandDepthLabel,
  isExpandDepthChanged,
  pickPublicExtJsonConfig,
  shouldSubmitExtJsonConfig,
  toExpandDepthSelect,
  toSubmitExpandDepth,
  UNLIMITED_EXPAND_DEPTH,
  type ExpandDepthSelect,
} from '@/components/collection-access/ext-json-expand-depth';
import { getCleanTypeLabel, getCleanTypeIcon } from '../business-comp/step3/clean-type';
import { isCollectionEditRoute } from './route-utils';

import type { ISelectItem, ISubmitOptions } from '../../type';

import './step3-clean.scss';

type EtlParams = {
  separator?: string;
  separator_regexp?: string;
  is_grok?: boolean;
  path_regexp?: string;
  metadata_fields?: unknown[];
  original_text_tokenize_on_chars?: string;
  enable_retain_content?: boolean;
  record_parse_failure?: boolean;
  [key: string]: unknown;
};

type EtlField = {
  field_name?: string;
  is_time?: boolean;
  option?: {
    time_format?: string;
    time_zone?: number | string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

type EtlConfigInput = {
  clean_type?: string;
  etl_config?: string;
  etl_params?: EtlParams;
  etl_fields?: EtlField[];
};

type TemplateConfigSnapshot = {
  clean_type: string;
  etl_params: EtlParams;
  etl_fields: EtlField[];
};

export default defineComponent({
  name: 'StepClean',
  props: {
    configData: {
      type: Object,
      default: () => ({}),
    },
    scenarioId: {
      type: String,
      default: '',
    },
    isEdit: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否为清洗模板
     */
    isTempField: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否为clone模式
     */
    isClone: {
      type: Boolean,
      default: false,
    },
    /**
     * 是否从清洗列表进入
     */
    isCleanField: {
      type: Boolean,
      default: false,
    },
    /** 创建流程容器提供的采集下发状态 */
    collectStatus: {
      type: String,
      default: '',
    },
  },

  emits: ['next', 'prev', 'cancel', 'change-submit'],

  setup(props, { emit, expose }) {
    const store = useStore();
    const { t } = useLocale();
    const route = useRoute();
    const defaultRegex = '(?P<request_ip>[d.]+)[^[]+[(?P<request_time>[^]]+)]';
    const { cardRender } = useOperation();
    const { goListPage } = useCollectList();
    const showReportLogSlider = ref(false);
    const jsonText = ref({});
    const fieldListRef = ref();
    const grokModeEnabled = ref(true);
    let isUnmounted = false;
    /**
     * 初始表单数据快照，用于对比是否有变更
     */
    const initialFormData = ref(null);
    /** 模板核心配置快照，仅用于判断保存模板时是否需要同步提醒 */
    const initialTemplateConfigSnapshot = ref<TemplateConfigSnapshot | null>(null);

    const templateDialogVisible = ref(false);
    const templateSaveConfirmVisible = ref(false);
    const templateName = ref('');
    const templateDescription = ref('');
    const templateCollectorCount = ref(0);
    const templateIndexSetCount = ref(0);
    /**
     * 应用模板前缓存之前填写的内容，方便后续重置
     */
    const cacheTemplateData = ref();
    /**
     * 清洗模式 - 分隔符 - 选中的分隔符
     */
    const delimiter = ref();

    const basicLoading = ref(false);
    /**
     * 指定日志时间校验报错信息
     */
    const timeCheckErrContent = ref('');
    /**
     * 路径元数据 - 路径样例
     */
    const pathExample = ref();
    const isDebugLoading = ref(false);
    const isPathDebugLoading = ref(false);
    /**
     * 日志样例
     */
    const logOriginal = ref('');
    const copyBuiltField = ref([]);
    const originParticipleState = ref('default');
    const cleaningModeList = [
      {
        label: t('JSON'),
        value: 'bk_log_json',
      },
      {
        label: t('分隔符'),
        value: 'bk_log_delimiter',
      },
      {
        label: t('正则表达式'),
        value: 'bk_log_regexp',
      },
    ];
    /**
     * 分词列表
     */
    const participleList = [
      {
        id: 'default',
        name: t('自然语言分词'),
      },
      {
        id: 'custom',
        name: t('自定义'),
      },
    ];
    const cleaningMode = ref('bk_log_text');
    const enableMetaData = ref(false);
    const loading = ref(false);
    const logOriginalLoading = ref(false);
    const pathExampleLoading = ref(false);
    /**
     * 是否刷新值
     */
    const isValueRefresh = ref(false);
    /** 选择清洗模板弹窗 */
    const cleanTemplateDialogVisible = ref(false);
    /** 清洗结果预览弹窗 */
    const cleanResultPreviewDialogVisible = ref(false);
    /** 当前选中的清洗模板（用于预览弹窗） */
    const currentSelectedTemplate = ref(null);
    /** 正在预览、尚未确认应用的清洗模板 */
    const pendingSelectedTemplate = ref(null);
    /** 当前采集项已经确认关联的清洗模板 ID */
    const cleanTemplateId = ref<number | null>(null);
    const initialCleanTemplateId = ref<number | null>(null);

    const visibleBkBiz = ref([]);
    const cacheVisibleList = ref([]);
    /**
     * 采集项下拉选项
     */
    const cleanCollectorList = ref([]);
    const cleanCollectorId = ref();
    const indexSetSelectLoading = ref(false);

    const builtInFieldsList = ref([]);
    const defaultParticipleStr = ref('@&()=\'",;:<>[]{}/ \\n\\t\\r\\\\');
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const curCollect = computed(() => store.getters['collect/curCollect']);
    const bkBizId = computed(() => store.getters.bkBizId);
    const spaceUid = computed(() => store.getters.spaceUid);
    const mySpaceList = computed(() => store.state.mySpaceList);

    const showCardConfig = computed(() => {
      let list = props.isTempField
        ? cardConfig.value.filter(item => item.key !== 'visibilitySettings')
        : cardConfig.value.filter(item => !['basicInfo', 'visibilitySettings'].includes(item.key));
      // 未开启清洗时不显示"清洗结果"卡片
      if (!isClean.value) {
        list = list.filter(item => item.key !== 'cleanResult');
      }
      return list;
    });
    /**
     * 分隔符
     */
    const globalDataDelimiter = computed<ISelectItem[]>(() => globalsData.value?.data_delimiter || []);
    /**
     * 时间格式
     */
    const fieldDateFormat = computed(() => globalsData.value?.field_date_format || []);
    /**
     * 时区
     */
    const timeZone = computed(() => (globalsData.value?.time_zone || []).toReversed());

    /**
     * 是否为编辑
     */
    const isUpdate = computed(() => isCollectionEditRoute(route.name) && props.isEdit);
    const isEditTemp = computed(() => route.name === 'clean-template-edit');

    const createDefaultEtlParams = () => ({
      retain_original_text: true,
      original_text_is_case_sensitive: false,
      original_text_tokenize_on_chars: '',
      separator_regexp: '',
      separator: '',
      retain_extra_json: false,
      enable_retain_content: true, // 保留失败日志
      path_regexp: '', // 采集路径分割的正则
      metadata_fields: [],
    });

    const formData = ref({
      // 最后一次正确的结果，保存以此数据为准
      table_id: '',
      etl_config: 'bk_log_json',
      etl_params: createDefaultEtlParams(),
      etl_fields: [],
      fields: [],
      visible_type: 'current_biz', // 可见范围单选项
      visible_bk_biz_id: [], // 多个业务
      log_original: '',
      log_reporting_time: true, // 日志上报时间
      field_name: '',
      time_format: '',
      time_zone: '',
    });
    /** 动态字段解析层级下拉值 */
    const expandDepthSelect = ref<ExpandDepthSelect>(DEFAULT_EXPAND_DEPTH);
    const sessionLastExpandDepth = ref<ExpandDepthSelect | null>(null);
    const originHadExtJsonConfig = ref(false);
    const originRetainExtraJson = ref(false);
    const originExpandDepthSelect = ref<ExpandDepthSelect | null>(null);
    const expandDepthInited = ref(false);
    const isChangingExpandDepth = ref(false);
    const expandDepthExampleVisible = ref(false);
    const expandDepthExampleInput = `{
  "__ext_json": {
    "trace_id": "abc123",
    "service": {
      "name": "order",
      "labels": {
        "region": "shanghai",
        "zone": "ap-1"
      }
    }
  }
}`;
    const copyText = ref({});
    const rowTemplate = ref({
      alias_name: '',
      description: '',
      field_type: 'string',
      is_case_sensitive: false,
      is_analyzed: false,
      is_built_in: false,
      is_delete: false,
      is_dimension: false,
      is_time: false,
      value: '',
      option: {
        time_format: '',
        time_zone: '',
      },
      // 是否是自定义分词
      tokenize_on_chars: '',
      participleState: 'default',
    });

    /** 将接口清洗配置统一转换为表单数据及其派生 UI 状态 */
    const applyEtlConfigToForm = <T extends EtlConfigInput>(data: T): T => {
      const appliedConfig = structuredClone(data);
      const cleanType = appliedConfig.clean_type ?? appliedConfig.etl_config ?? formData.value.etl_config;
      const sourceEtlParams = appliedConfig.etl_params ?? {};
      if (
        typeof sourceEtlParams.enable_retain_content !== 'boolean' &&
        typeof sourceEtlParams.record_parse_failure === 'boolean'
      ) {
        sourceEtlParams.enable_retain_content = sourceEtlParams.record_parse_failure;
      }
      const etlParams = {
        ...createDefaultEtlParams(),
        ...sourceEtlParams,
        metadata_fields: sourceEtlParams.metadata_fields ?? [],
      };
      const etlFields = (appliedConfig.etl_fields ?? []).map(item => ({
        ...rowTemplate.value,
        ...item,
        option: {
          ...rowTemplate.value.option,
          ...item.option,
        },
      }));
      const timeField = etlFields.find(item => item.is_time);

      formData.value = {
        ...formData.value,
        etl_config: cleanType,
        etl_params: etlParams,
        etl_fields: etlFields,
        log_reporting_time: !timeField,
        field_name: timeField?.field_name ?? '',
        time_format: timeField?.option?.time_format ?? '',
        time_zone: timeField?.option?.time_zone ?? '',
      };
      cleaningMode.value = cleanType;
      delimiter.value = etlParams.separator ?? '';
      enableMetaData.value = !!etlParams.path_regexp;
      originParticipleState.value = etlParams.original_text_tokenize_on_chars ? 'custom' : 'default';
      grokModeEnabled.value = etlParams.is_grok ?? true;
      timeCheckErrContent.value = '';
      return appliedConfig;
    };

    const showDebugPathRegexBtn = computed(() => formData.value.etl_params.path_regexp && pathExample.value);

    const isClean = computed(() => cleaningMode.value !== 'bk_log_text');

    const isExtJsonExpandDepthEnabled = computed(() =>
      isFeatureToggleOn(EXT_JSON_EXPAND_DEPTH_TOGGLE, [String(bkBizId.value), String(spaceUid.value)]),
    );

    /** 仅控制「动态字段解析层级」，不影响「JSON 字段动态新增」 */
    const showExpandDepthConfig = computed(
      () =>
        isExtJsonExpandDepthEnabled.value &&
        cleaningMode.value === 'bk_log_json' &&
        !!formData.value.etl_params?.retain_extra_json,
    );

    const expandDepthOptions = computed(() => [
      { id: 1 as const, name: t('1 层'), desc: t('只展开 __ext_json 下第一层字段') },
      { id: 2 as const, name: t('2 层'), desc: t('展开到第二层，推荐') },
      { id: 3 as const, name: t('3 层'), desc: t('展开到第三层') },
      {
        id: UNLIMITED_EXPAND_DEPTH,
        name: t('无限'),
        desc: t('保持完整动态展开，存在字段膨胀风险'),
      },
    ]);

    const expandDepthExampleTitle = computed(() => {
      if (expandDepthSelect.value === UNLIMITED_EXPAND_DEPTH) {
        return t('无限展示');
      }
      return t('{n} 层展示', { n: expandDepthSelect.value });
    });

    const expandDepthExampleResult = computed(() => {
      if (expandDepthSelect.value === 1) {
        return `__ext_json.trace_id          keyword
__ext_json.service           ${t('动态对象字段')}`;
      }
      if (expandDepthSelect.value === 3 || expandDepthSelect.value === UNLIMITED_EXPAND_DEPTH) {
        return `__ext_json.trace_id                 keyword
__ext_json.service.name           keyword
__ext_json.service.labels.region  keyword
__ext_json.service.labels.zone    keyword`;
      }
      return `__ext_json.trace_id          keyword
__ext_json.service.name     keyword
__ext_json.service.labels   ${t('动态对象字段')}`;
    });

    const expandDepthExampleNote = computed(() => {
      if (expandDepthSelect.value === 1) {
        return t('service 内部不再继续生成字段。');
      }
      if (expandDepthSelect.value === 2) {
        return t('labels 内部不再继续生成字段。');
      }
      if (expandDepthSelect.value === UNLIMITED_EXPAND_DEPTH) {
        return t('无限模式下将完整展开动态字段。');
      }
      return t('更深层级的对象将按动态对象字段处理，不再继续展开。');
    });

    const initExpandDepthFromEtlParams = (etlParams: any = {}, { resetOrigin = true } = {}) => {
      const params = etlParams && typeof etlParams === 'object' ? etlParams : {};
      const retainExtraJson = !!params.retain_extra_json;
      const publicConfig = pickPublicExtJsonConfig(params.ext_json_config);
      const hadConfig = !!publicConfig;
      const select = retainExtraJson
        ? toExpandDepthSelect(hadConfig ? publicConfig.expand_depth : null)
        : DEFAULT_EXPAND_DEPTH;

      expandDepthSelect.value = select;
      sessionLastExpandDepth.value = select;
      if (resetOrigin) {
        originHadExtJsonConfig.value = hadConfig;
        originRetainExtraJson.value = retainExtraJson;
        originExpandDepthSelect.value = hadConfig ? select : UNLIMITED_EXPAND_DEPTH;
      }
      expandDepthInited.value = true;
    };

    /** 仅同步层级选择缓存；开关本身仍走原有 retain_extra_json 赋值逻辑 */
    const syncExpandDepthOnRetainExtraJsonChange = (val: boolean) => {
      if (!expandDepthInited.value || !isExtJsonExpandDepthEnabled.value) {
        return;
      }
      if (val) {
        expandDepthSelect.value = sessionLastExpandDepth.value ?? DEFAULT_EXPAND_DEPTH;
      } else {
        sessionLastExpandDepth.value = expandDepthSelect.value;
      }
    };

    const handleExpandDepthSelected = (val: ExpandDepthSelect) => {
      expandDepthSelect.value = val;
      sessionLastExpandDepth.value = val;
    };

    const needConfirmExpandDepthChange = () => {
      if (!isExtJsonExpandDepthEnabled.value || !formData.value.etl_params?.retain_extra_json) {
        return false;
      }
      if (!isUpdate.value && !props.isCleanField) {
        return false;
      }
      return isExpandDepthChanged(
        expandDepthSelect.value,
        originExpandDepthSelect.value,
        originHadExtJsonConfig.value,
        originRetainExtraJson.value,
      );
    };

    const confirmExpandDepthChange = () => {
      if (!needConfirmExpandDepthChange()) {
        return Promise.resolve(true);
      }
      return new Promise<boolean>(resolve => {
        InfoBox({
          type: 'warning',
          title: t('确认调整动态字段解析层级？'),
          okText: t('确认调整'),
          cancelText: t('取消'),
          subTitle: t(
            '调整后系统将创建新的 ES 索引，仅影响配置生效后写入的数据。历史索引不会改变，因此不同时间段可检索的字段可能不完全一致。',
          ),
          confirmFn: () => resolve(true),
          cancelFn: () => resolve(false),
        });
      });
    };
    /** 清洗规则配置方式：manual 手动配置 / template 使用模板 */
    const cleanRuleMode = ref<'manual' | 'template'>('manual');
    /** 当前采集项是否已经绑定清洗模板 */
    const isTemplateBound = computed(() => cleanRuleMode.value === 'template' && cleanTemplateId.value !== null);

    /** 获取保存时需要提交的模板关联 ID */
    const getSubmitCleanTemplateId = () =>
      isClean.value && cleanRuleMode.value === 'template' ? cleanTemplateId.value : null;

    /** 根据采集项返回的模板 ID 恢复关联，并加载当前绑定模板详情 */
    const restoreCleanTemplateAssociation = async (templateId: number | null) => {
      const normalizedTemplateId = templateId ?? null;
      cleanTemplateId.value = normalizedTemplateId;
      cleanRuleMode.value = normalizedTemplateId === null ? 'manual' : 'template';

      if (normalizedTemplateId === null) {
        currentSelectedTemplate.value = null;
        return;
      }
      if (currentSelectedTemplate.value?.clean_template_id === normalizedTemplateId) {
        return;
      }

      currentSelectedTemplate.value = null;
      try {
        const res = await $http.request('clean/templateDetail', {
          params: {
            clean_template_id: normalizedTemplateId,
          },
        });
        if (!isUnmounted && res.data) {
          currentSelectedTemplate.value = res.data;
        }
      } catch (error) {
        console.error(error);
      }
    };

    /**
     * 保存初始表单数据快照
     */
    const saveInitialFormData = () => {
      initialFormData.value = structuredClone({
        ...formData.value,
        expandDepthSelect: expandDepthSelect.value,
      });
      initialCleanTemplateId.value = getSubmitCleanTemplateId();
    };

    /** 构造模板实际提交的清洗参数，保证变更判断与提交口径一致 */
    const buildTemplateEtlParams = (): EtlParams => {
      const etlParams = structuredClone(formData.value.etl_params);
      if (!enableMetaData.value) {
        etlParams.path_regexp = null;
        etlParams.metadata_fields = [];
      }
      // 与采集接入链路保持一致：record_parse_failure 与 enable_retain_content 同值
      etlParams.record_parse_failure = etlParams.enable_retain_content;
      return etlParams;
    };

    /** 提取实际生效的字段配置，排除日志样例值及表格 UI 状态 */
    const buildTemplateEtlFieldsSnapshot = (fields: EtlField[]): EtlField[] =>
      fields.map(field => ({
        field_index: field.field_index,
        field_name: field.field_name,
        alias_name: field.alias_name,
        field_type: field.field_type,
        description: field.description,
        is_analyzed: field.is_analyzed,
        is_dimension: field.is_dimension,
        is_time: field.is_time,
        is_delete: field.is_delete,
        is_built_in: field.is_built_in,
        option: structuredClone(field.option ?? {}),
        is_case_sensitive: field.is_case_sensitive,
        tokenize_on_chars: field.tokenize_on_chars,
      }));

    /** 提取会影响清洗结果的模板核心配置 */
    const getTemplateConfigSnapshot = (): TemplateConfigSnapshot => ({
      clean_type: cleaningMode.value,
      etl_params: buildTemplateEtlParams(),
      etl_fields: buildTemplateEtlFieldsSnapshot(formData.value.etl_fields),
    });

    const saveInitialTemplateConfigSnapshot = () => {
      initialTemplateConfigSnapshot.value = getTemplateConfigSnapshot();
    };

    const hasTemplateCoreConfigChanged = () =>
      initialTemplateConfigSnapshot.value === null ||
      !deepEqual(getTemplateConfigSnapshot(), initialTemplateConfigSnapshot.value);

    /**
     * 判断配置是否有变更
     */
    const hasConfigChanged = () => {
      return (
        !deepEqual({ ...formData.value, expandDepthSelect: expandDepthSelect.value }, initialFormData.value) ||
        getSubmitCleanTemplateId() !== initialCleanTemplateId.value
      );
    };

    const isEditCleanItem = computed(() => route.name === 'clean-edit' || route.name === 'v2-clean-edit');

    // 用于追踪 separator_regexp 的变化，确保响应式更新
    const separatorRegexp = computed(() => formData.value.etl_params.separator_regexp);

    onMounted(() => {
      // 清洗列表进入
      if (props.isCleanField) {
        if (isEditCleanItem.value) {
          cleanCollectorId.value = Number(route.params.collectorId);
        }
        initCleanItem();
        return;
      }
      // 清洗模板进入
      if (props.isTempField) {
        cleaningMode.value = 'bk_log_json';
        initCleanItem();
        isEditTemp.value && initCleanTemp();
        return;
      }
      const id = isUpdate.value ? route.params.collectorId : route.query.collectorId;
      setDetail(id);
    });
    /**
     * 当为清洗列表 - 创建/编辑清洗的时候，获取采集项下拉框内容
     */
    const initCleanItem = () => {
      // 初始化清洗项
      indexSetSelectLoading.value = true;
      const query = {
        bk_biz_id: bkBizId.value,
        have_data_id: 1,
        have_table_id: 1,
      };
      // 获取采集项列表
      $http
        .request('collect/getAllCollectors', { query })
        .then(res => {
          indexSetSelectLoading.value = false;
          const { data } = res;
          cleanCollectorList.value = data || [];
        })
        .catch(() => {
          indexSetSelectLoading.value = false;
        });
    };

    const setTempDetail = data => {
      applyEtlConfigToForm(data);
      formData.value = {
        ...formData.value,
        visible_type: data.visible_type ?? formData.value.visible_type,
        visible_bk_biz_id: data.visible_bk_biz_id ?? [],
      };
      templateName.value = data.name;
      templateDescription.value = data.description ?? '';
      visibleBkBiz.value = data.visible_bk_biz_id;
      templateCollectorCount.value = data.active_collector_count ?? 0;
      templateIndexSetCount.value = data.related_index_set_count ?? 0;
    };

    const initCleanTemp = () => {
      const { templateId } = route.params;
      basicLoading.value = true;
      $http
        .request('clean/templateDetail', {
          params: {
            clean_template_id: templateId,
          },
          query: {
            bk_biz_id: bkBizId.value,
          },
        })
        .then(res => {
          if (res.data) {
            setTempDetail(resolveCleanTemplateDraft(res.data));
            saveInitialTemplateConfigSnapshot();
          }
        })
        .finally(() => {
          if (!isUnmounted) {
            basicLoading.value = false;
          }
        });
    };
    const getCleanStash = async (id: number) => {
      try {
        const res = await $http.request('clean/getCleanStash', {
          params: {
            collector_config_id: id,
          },
        });
        if (res.data) {
          const { etl_params } = res.data;
          applyEtlConfigToForm(res.data);
          formData.value.visible_bk_biz_id = res.data.visible_bk_biz_id ?? [];
          visibleBkBiz.value = res.data.visible_bk_biz_id;
          await restoreCleanTemplateAssociation(res.data.clean_template_id);
          initExpandDepthFromEtlParams(etl_params);
          cacheTemplateData.value = deepClone(formData.value);
          return;
        }
        formData.value.etl_params.retain_original_text = true;
        formData.value.etl_params.enable_retain_content = true;
        cacheTemplateData.value = deepClone(formData.value);
      } catch (error) {
        console.log(error);
      }
    };

    // 新建、编辑采集项时获取更新详情
    onBeforeUnmount(() => {
      isUnmounted = true;
    });

    const setDetail = id => {
      cleanTemplateId.value = null;
      currentSelectedTemplate.value = null;
      pendingSelectedTemplate.value = null;
      cleanRuleMode.value = 'manual';
      /**
       * 初始化导入的配置
       */
      builtInFieldsList.value = (props.configData.etl_fields || []).filter(item => item.is_built_in);
      const eltField = (props.configData.etl_fields || []).filter(item => !item.is_built_in);
      formData.value = {
        ...formData.value,
        ...props.configData,
        etl_fields: eltField,
      };
      // 保存初始表单数据快照
      saveInitialFormData();
      if (!id) {
        return;
      }
      basicLoading.value = true;
      $http
        .request('collect/details', {
          params: { collector_config_id: id },
        })
        .then(async res => {
          if (isUnmounted || !res.data) {
            return;
          }
          if (res.data) {
            // 克隆时不覆盖curCollect，避免把第一步创建的新采集项ID覆盖为旧ID
            if (!props.isClone) {
              store.commit('collect/setCurCollect', res.data);
            }
            const fieldsSource = props.isClone ? res.data.fields : curCollect.value.fields;
            builtInFieldsList.value = (fieldsSource || []).filter(item => item.is_built_in);

            // 从 curCollect 获取详情数据并回填到 formData，与旧版 getDetail 保持一致
            const { etl_config, etl_params: etlParams, fields } = curCollect.value;

            // 处理 fields：清空 value、处理 is_delete、确保 option 存在
            const option = { time_zone: '', time_format: '' };
            const copyFields = fields ? structuredClone(fields) : [];
            copyFields.forEach(row => {
              row.value = '';
              if (row.is_delete) {
                const copyRow = Object.assign(structuredClone(rowTemplate.value), structuredClone(row));
                Object.assign(row, copyRow);
              }
              if (row.option) {
                row.option = Object.assign({}, option, row.option || {});
              } else {
                row.option = Object.assign({}, option);
              }
            });

            // 更新 cleaningMode 和 enableMetaData
            cleaningMode.value = etl_config || 'bk_log_text';
            enableMetaData.value = !!etlParams?.path_regexp;

            // 更新 delimiter 和 originParticipleState
            if (cleaningMode.value === 'bk_log_delimiter') {
              delimiter.value = etlParams?.separator;
            }
            originParticipleState.value = etlParams?.original_text_tokenize_on_chars ? 'custom' : 'default';

            // 合并 etl_params 默认值并更新 formData
            formData.value = {
              ...formData.value,
              etl_config: cleaningMode.value,
              etl_params: Object.assign(
                {
                  retain_original_text: true,
                  separator_regexp: '',
                  separator: '',
                  retain_extra_json: false,
                  original_text_is_case_sensitive: false,
                  original_text_tokenize_on_chars: '',
                  enable_retain_content: true,
                  path_regexp: '',
                  metadata_fields: [],
                },
                etlParams
                  ? {
                      ...structuredClone(etlParams),
                      metadata_fields: etlParams.metadata_fields || [],
                    }
                  : {},
              ),
              etl_fields: copyFields.filter(item => !item.is_built_in),
            };
            initExpandDepthFromEtlParams(formData.value.etl_params);
            await restoreCleanTemplateAssociation(res.data.clean_template_id);
            cacheTemplateData.value = deepClone(formData.value);

            if (props.isEdit || props.isClone || props.isCleanField) {
              getDataLog('init');
              await getCleanStash(id);
              saveInitialFormData();
            }
          }
        })
        .finally(() => {
          basicLoading.value = false;
        });
    };
    /**
     * 路径元数据 - 调试按钮
     */
    const debuggerPathRegex = () => {
      const data = {
        etl_config: 'bk_log_regexp',
        etl_params: {
          separator_regexp: formData.value.etl_params?.path_regexp,
        },
        data: pathExample.value,
      };
      let requestUrl = 'collect/getEtlPreview';
      const urlParams = {};
      isPathDebugLoading.value = true;
      if (props.isTempField) {
        // 模板场景无 collector_config_id，走模板预览接口
        requestUrl = 'clean/getEtlPreview';
        data.bk_biz_id = bkBizId.value;
      } else {
        urlParams.collector_config_id = curCollect.value.collector_config_id;
      }
      const updateData = { params: urlParams, data };
      // 先置空防止接口失败显示旧数据
      formData.value.etl_params.metadata_fields = [];
      $http
        .request(requestUrl, updateData)
        .then(res => {
          const fields = res.data?.fields || [];
          formData.value.etl_params?.metadata_fields.push(...fields);
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          isPathDebugLoading.value = false;
        });
    };

    const judgeNumber = val => {
      const { value } = val;
      if (value === 0) {
        return false;
      }

      return value && value !== ' ' ? isNaN(value) : true;
    };

    /** int 类型最大值 */
    const MAX_INT_VALUE = 2_147_483_647;

    /** 根据清洗结果 value 推断字段类型 */
    const detectFieldType = (value: unknown): string => {
      if (typeof value === 'number') {
        if (Number.isInteger(value)) {
          return value > MAX_INT_VALUE ? 'long' : 'int';
        }
        return 'double';
      }
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        return 'object';
      }
      return 'string';
    };

    /**
     * 清洗模式 - 清洗/调试按钮
     */
    const debugHandler = (type = 'default') => {
      const isRefresh = type === 'refresh';
      const { etl_params } = formData.value;
      const data = {
        etl_config: cleaningMode.value,
        etl_params: {},
        data: logOriginal.value,
      };
      if (cleaningMode.value === 'bk_log_delimiter') {
        data.etl_params.separator = delimiter.value;
      }
      if (cleaningMode.value === 'bk_log_regexp') {
        data.etl_params.separator_regexp = etl_params.separator_regexp;
        data.etl_params.is_grok = grokModeEnabled.value;
        data.bk_biz_id = bkBizId.value;
      }
      let requestUrl = 'clean/getEtlPreview';
      const urlParams = {};
      isDebugLoading.value = !isRefresh;
      isValueRefresh.value = isRefresh;
      // 缓存当前已有字段，用于再次清洗时合并保留旧配置
      const existingFields = structuredClone(formData.value.etl_fields || []);
      /**
       * 非刷新场景下才清空表格数据
       */
      if (!isRefresh) {
        formData.value.etl_fields = [];
      }
      if (props.isTempField) {
        requestUrl = 'clean/getEtlPreview';
      } else {
        urlParams.collector_config_id = curCollect.value.collector_config_id;
        requestUrl = 'collect/getEtlPreview';
      }
      const updateData = { params: urlParams, data };
      $http
        .request(requestUrl, updateData)
        .then(res => {
          const dataFields = res.data.fields;
          const validFieldPattern = /^[A-Za-z_][0-9A-Za-z_]*$/;
          for (const item of dataFields) {
            if (item.field_name && !validFieldPattern.test(item.field_name)) {
              item.field_name = JSON.stringify(item.field_name);
            }
            item.verdict = judgeNumber(item);
          }
          const fields = formData.value.etl_fields;

          /**
           * 创建新字段对象，应用 detectFieldType 推断类型
           */
          const createNewField = (item, index) => ({
            ...structuredClone(rowTemplate.value),
            ...item,
            field_type: detectFieldType(item.value),
            field_index: item.field_index ?? index + 1,
          });

          /**
           * 当只刷新值的时候，只更新对应字段的值
           */
          if (isRefresh) {
            const valueMap = dataFields.reduce((map, item, index) => {
              const key = cleaningMode.value === 'bk_log_delimiter' ? (item.field_index ?? index + 1) : item.field_name;
              map[key] = item.value;
              return map;
            }, {});
            formData.value.etl_fields = fields.map(item => {
              if (item.is_built_in) return item;
              const key = cleaningMode.value === 'bk_log_delimiter' ? item.field_index : item.field_name;
              return {
                ...item,
                value: valueMap[key] ?? '',
              };
            });
            return;
          }

          // 判断是否为首次清洗（无提取方式 || 提取方式变化 || 无已有字段配置）
          const isFirstClean =
            !formData.value.etl_config || formData.value.etl_config !== cleaningMode.value || !existingFields.length;

          if (isFirstClean) {
            // 首次清洗：对每个字段应用 detectFieldType 推断类型
            const list = dataFields.reduce((arr, item, index) => {
              arr.push(createNewField(item, index));
              return arr;
            }, []);
            formData.value.etl_fields = list;
            formData.value.etl_config = cleaningMode.value;
            return;
          }

          // 再次清洗：根据清洗模式合并已有字段配置
          const etlConfig = cleaningMode.value;

          if (etlConfig === 'bk_log_json' || etlConfig === 'bk_log_regexp') {
            // JSON/正则模式：按 field_name 匹配，保留旧字段配置
            const list = dataFields.reduce((arr, item, index) => {
              const existingField = existingFields.find(
                field => !field.is_built_in && field.field_name === item.field_name,
              );
              if (existingField) {
                // 已有字段：保留旧配置，仅覆盖接口返回的值
                arr.push({
                  ...existingField,
                  ...item,
                  field_type: existingField.field_type,
                  field_index: item.field_index ?? index + 1,
                });
              } else {
                // 新增字段：应用类型推断
                arr.push(createNewField(item, index));
              }
              return arr;
            }, []);

            // JSON 模式下：已标记 is_delete 的字段需追加回列表
            if (etlConfig === 'bk_log_json') {
              const deletedFields = existingFields.filter(
                field => field.is_delete && !dataFields.find(item => item.field_name === field.field_name),
              );
              list.push(...deletedFields);
            }

            formData.value.etl_fields = list;
            formData.value.etl_config = cleaningMode.value;
          } else if (etlConfig === 'bk_log_delimiter') {
            // 分隔符模式：按 field_index 匹配已有字段，保留旧配置
            const nonDeletedFields = existingFields.filter(item => item.field_name && !item.is_delete);
            const deletedFields = existingFields.filter(item => item.is_delete);
            const list = [...deletedFields];

            if (nonDeletedFields.length) {
              nonDeletedFields.forEach((item, idx) => {
                const child = dataFields[idx];
                if (child) {
                  // 已有字段：保留旧配置，仅更新 value
                  list.push({
                    ...item,
                    value: child.value,
                  });
                } else {
                  list.push({ ...item, value: '' });
                }
              });
              // 处理 dataFields 中超出已有字段范围的新增字段
              if (dataFields.length > nonDeletedFields.length) {
                dataFields.slice(nonDeletedFields.length).forEach((item, idx) => {
                  list.push(createNewField(item, nonDeletedFields.length + idx));
                });
              }
            } else {
              dataFields.forEach((item, index) => {
                list.push(createNewField(item, index));
              });
            }

            formData.value.etl_fields = list;
            formData.value.etl_config = cleaningMode.value;
          }
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          isDebugLoading.value = false;
          isValueRefresh.value = false;
        });
    };
    /** 根据清洗模式，渲染不同的内容 */
    const renderCleaningMode = () => {
      /**
       * Json
       */
      if (cleaningMode.value === 'bk_log_json') {
        return (
          <bk-button
            class='clean-btn'
            disabled={!logOriginal.value}
            on-click={debugHandler}
          >
            {t('清洗')}
          </bk-button>
        );
      }
      /**
       * 分隔词
       */
      if (cleaningMode.value === 'bk_log_delimiter') {
        return (
          <div class='separator-box select-group'>
            <div class='select-item'>
              <span class='select-title'>{t('分隔符')}</span>
              <bk-select
                class='select-box'
                clearable={false}
                value={delimiter.value}
                on-change={(val: string) => {
                  delimiter.value = val;
                  formData.value.etl_params.separator = val;
                }}
              >
                {globalDataDelimiter.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            </div>
            <bk-button
              class='clean-btn'
              disabled={!logOriginal.value || !delimiter.value}
              on-click={debugHandler}
            >
              {t('调试')}
            </bk-button>
          </div>
        );
      }
      /**
       * 正则表达式
       */
      if (cleaningMode.value === 'bk_log_regexp') {
        return (
          <div class='regex-box-main'>
            <div class='title'>
              {t('正则表达式')}
              <i
                class='bk-icon icon-info-circle tips-icon'
                v-bk-tooltips={{
                  placement: 'right',
                  content: `${t(
                    '正则表达式(golang语法)需要匹配日志全文，如以下DEMO将从日志内容提取请求时间与内容',
                  )}<br />${t(' - 日志内容：[2006-01-02 15:04:05] content')}<br /> ${t(
                    ' - 表达式：',
                  )} \[(?P<request_time>[^]]+)\] (?P<content>.+)`,
                }}
              />
              <GrokModeSwitch
                value={grokModeEnabled.value}
                on-change={(val: boolean) => {
                  grokModeEnabled.value = val;
                }}
              />
            </div>
            <GrokInput
              grokMode={grokModeEnabled.value}
              popoverPosition='cursor'
              placeholder={'(?P<request_ip>[d.]+)[^[]+[(?P<request_time>[^]]+)]'}
              type='textarea'
              value={formData.value.etl_params.separator_regexp}
              on-input={(val: string) => {
                formData.value.etl_params = {
                  ...formData.value.etl_params,
                  separator_regexp: val,
                };
              }}
            />
            <bk-button
              class='clean-btn'
              disabled={!(logOriginal.value && separatorRegexp.value)}
              on-click={debugHandler}
            >
              {t('调试')}
            </bk-button>
          </div>
        );
      }
    };

    /**
     * 获取清洗的相关信息，如日志样例、上报日志（origin字段）
     * @param type
     */
    const getDataLog = (type: string, collectorConfigId?: number) => {
      logOriginalLoading.value = type === 'refresh';
      pathExampleLoading.value = type === 'pathRefresh';
      $http
        .request('source/dataList', {
          params: {
            collector_config_id: collectorConfigId ?? curCollect.value.collector_config_id,
          },
        })
        .then(res => {
          if (res.data?.length) {
            copyText.value = Object.assign(res.data[0].etl, res.data[0].etl.items[0]) || {};
            const data = res.data[0];
            jsonText.value = data.origin || {};
            pathExample.value = jsonText.value.filename;
            logOriginal.value = data.etl.data || '';
            // biome-ignore lint/complexity/noForEach: <explanation>
            copyBuiltField.value.forEach(item => {
              const fieldName = item.field_name;
              if (fieldName) {
                item.value = copyText.value[fieldName];
              }
            });
          }
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          logOriginalLoading.value = false;
          pathExampleLoading.value = false;
        });
    };
    /**
     * 另存为模板确认
     *
     */
    const handleTempConfirm = async (syncToCollectors = false) => {
      if (templateName.value.trim() === '') {
        showMessage(t('请输入模板名称'), 'error');
        loading.value = false;
        return;
      }
      loading.value = true;

      const { etl_fields } = formData.value;
      const templateEtlParams = buildTemplateEtlParams();
      const data = {
        name: templateName.value,
        description: templateDescription.value,
        bk_biz_id: bkBizId.value,
        clean_type: cleaningMode.value,
        etl_params: templateEtlParams,
        etl_fields,
      };
      const urlParams = {};
      if (isEditTemp.value) {
        urlParams.clean_template_id = route.params.templateId;
      }
      const updateData = { params: urlParams, data };
      const requestUrl = isEditTemp.value ? 'clean/updateTemplate' : 'clean/createTemplate';
      try {
        const res = await $http.request(requestUrl, updateData);
        if (!res.result) {
          return;
        }

        let syncFailed = false;
        if (isEditTemp.value && syncToCollectors) {
          try {
            const syncRes = await $http.request('clean/syncCleanTemplateCollectors', {
              params: { clean_template_id: route.params.templateId },
            });
            syncFailed = !Array.isArray(syncRes.data) || syncRes.data.some(item => item.status !== 'SUCCESS');
          } catch {
            syncFailed = true;
          }
        }

        templateDialogVisible.value = false;
        templateSaveConfirmVisible.value = false;
        showMessage(syncFailed ? t('同步失败') : t('保存成功'), syncFailed ? 'error' : 'success');
        if (props.isTempField) {
          emit('change-submit', true);
        }
      } finally {
        loading.value = false;
      }
    };

    const handleTemplateSubmit = () => {
      if (templateName.value.trim() === '') {
        showMessage(t('请输入模板名称'), 'error');
        return;
      }
      handleSubmitValidate(() => {
        if (isEditTemp.value) {
          loading.value = false;
          if (hasTemplateCoreConfigChanged() && templateCollectorCount.value > 0) {
            templateSaveConfirmVisible.value = true;
          } else {
            handleTempConfirm();
          }
          return;
        }
        handleTempConfirm();
      });
    };
    /** 选择清洗模式 */
    const handleChangeCleaningMode = (mode: string) => {
      cleaningMode.value = mode.value;
      if (cleaningMode.value !== 'bk_log_json') {
        formData.value.etl_params.retain_extra_json = false;
      }
    };

    // 对时间格式做校验逻辑
    const requestCheckTime = async () => {
      const { time_format, time_zone, field_name } = formData.value;
      const fieldsData = formData.value.etl_fields;
      const timeValueItem = fieldsData.find(item => field_name === item.field_name);
      let result = false;
      await $http
        .request('collect/getCheckTime', {
          params: {
            collector_config_id: curCollect.value.collector_config_id,
          },
          data: {
            time_format,
            time_zone,
            data: timeValueItem?.value || '',
          },
        })
        .then(() => {
          timeCheckErrContent.value = '';
          result = true;
        })
        .catch(err => {
          timeCheckErrContent.value = err;
          result = false;
        });
      return result;
    };
    /**
     * 在清洗列表进入的时候，选择采集项之后的操作
     * @param id
     * @returns
     */
    const handleCollectorChange = async (id: number) => {
      cleanCollectorId.value = id;
      // 先校验有无采集项管理权限
      const paramData = {
        action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
        resources: [
          {
            type: 'collection',
            id,
          },
        ],
      };
      const res = await store.dispatch('checkAndGetData', paramData);
      if (res.isAllowed === false) {
        return;
      }
      setDetail(id);
    };
    /** 模板场景仅使用采集项获取调试日志，不回填采集项已有的清洗规则 */
    const handleTemplateDebugSourceChange = async (id: number) => {
      cleanCollectorId.value = id;
      const res = await store.dispatch('checkAndGetData', {
        action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
        resources: [
          {
            type: 'collection',
            id,
          },
        ],
      });
      if (res.isAllowed === false) {
        cleanCollectorId.value = undefined;
        return;
      }
      getDataLog('refresh', id);
    };
    // 采集项列表点击申请采集项目管理权限
    const applyProjectAccess = async item => {
      try {
        const res = await store.dispatch('getApplyData', {
          action_ids: [authorityMap.MANAGE_COLLECTION_AUTH],
          resources: [
            {
              type: 'collection',
              id: item.collector_config_id,
            },
          ],
        });
        window.open(res.data.apply_url);
      } catch (err) {
        console.warn(err);
      }
    };
    /** 重新选择清洗模板：重新打开模板选择弹窗 */
    const handleReselectTemplate = () => {
      cleanTemplateDialogVisible.value = true;
    };

    /** 解除清洗模板绑定：清空当前选中的模板，并切换到手动配置清洗规则 */
    const handleUnbindTemplate = () => {
      currentSelectedTemplate.value = null;
      pendingSelectedTemplate.value = null;
      cleanTemplateId.value = null;
      cleanRuleMode.value = 'manual';
    };

    /** 解除绑定 popover 引用，用于手动关闭 */
    const unbindPopoverRef = ref();
    /** 高级设置模板绑定提示引用，用于解绑前关闭提示 */
    const advancedTemplateBoundPopoverRef = ref();

    const handleAdvancedTemplateUnbind = () => {
      advancedTemplateBoundPopoverRef.value?.hide();
      setTimeout(() => handleUnbindTemplate(), 0);
    };

    /** 解除绑定确认弹窗内容 */
    const renderUnbindPopoverContent = () => (
      <div class='unbind-popover-content'>
        <div class='unbind-popover-icon'>
          <i class='bk-icon icon-info' />
        </div>
        <div class='unbind-popover-main'>
          <div class='unbind-popover-title'>{t('确定解除与模板的关联关系？')}</div>
          <div class='unbind-popover-row'>
            <span class='row-label'>{t('模板名称：')}</span>
            <span class='row-value'>{currentSelectedTemplate.value?.name}</span>
          </div>
          <div class='unbind-popover-desc'>{t('解除绑定后，将实例化为手动配置的清洗规则，不再随模板更新。')}</div>
          <div class='unbind-popover-footer'>
            <bk-button
              theme='primary'
              size='small'
              on-click={() => {
                unbindPopoverRef.value?.hide();
                // 延迟执行解绑，确保 popover 先关闭并移除 document click listener
                setTimeout(() => handleUnbindTemplate(), 0);
              }}
            >
              {t('确认解除')}
            </bk-button>
            <bk-button
              size='small'
              on-click={() => unbindPopoverRef.value?.hide()}
            >
              {t('取消')}
            </bk-button>
          </div>
        </div>
      </div>
    );

    const renderCollectorOptions = () =>
      cleanCollectorList.value.map(option => (
        <bk-option
          id={option.collector_config_id}
          key={option.collector_config_id}
          name={option.collector_config_name}
        >
          {!option.permission?.[authorityMap.MANAGE_COLLECTION_AUTH] ? (
            <div class='option-slot-container no-authority'>
              <span class='text'>
                <span>{option.collector_config_name}</span>
                <span style='color: #979ba5'>（{`#${option.collector_config_id}`}）</span>
              </span>
              <span
                class='apply-text'
                on-click={() => applyProjectAccess(option)}
              >
                {t('申请权限')}
              </span>
            </div>
          ) : (
            <div
              class='option-slot-container'
              v-bk-overflow-tips
            >
              <span>{option.collector_config_name}</span>
              <span style='color: #979ba5'>（{`#${option.collector_config_id}`}）</span>
            </div>
          )}
        </bk-option>
      ));

    /** 清洗设置 */
    const renderSetting = () => (
      <div class='clean-setting'>
        {!props.isCleanField && !props.isTempField && (
          <bk-alert
            class='clean-alert'
            title={t('通过字段清洗，可以格式化日志内容方便检索、告警和分析。')}
            type='info'
          />
        )}
        {(props.isCleanField || props.isTempField) && (
          <div class='label-form-box debug-source-row'>
            <span class='label-title'>{t('调试数据来源')}</span>
            <div class='form-box'>
              <bk-select
                class='debug-source-select'
                disabled={props.isCleanField && isEditCleanItem.value}
                loading={indexSetSelectLoading.value}
                placeholder={t('请选择采集项')}
                searchable
                value={cleanCollectorId.value}
                on-change={props.isTempField ? handleTemplateDebugSourceChange : handleCollectorChange}
              >
                {renderCollectorOptions()}
              </bk-select>
            </div>
          </div>
        )}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('日志样例')}</span>
          <div
            class='form-box'
            v-bkloading={{ isLoading: logOriginalLoading.value }}
          >
            <div class='example-box mt-5'>
              <span
                class='form-link'
                on-click={() => {
                  if (props.isTempField && !cleanCollectorId.value) {
                    showMessage(t('请选择采集项'), 'error');
                    return;
                  }
                  showReportLogSlider.value = true;
                }}
              >
                <i class='bklog-icon bklog-audit link-icon' />
                {t('上报日志')}
              </span>
              <span
                class='form-link'
                on-click={() => {
                  if (props.isTempField && !cleanCollectorId.value) {
                    showMessage(t('请选择采集项'), 'error');
                    return;
                  }
                  getDataLog('refresh', props.isTempField ? cleanCollectorId.value : undefined);
                }}
              >
                <i class='bklog-icon bklog-refresh2 link-icon' />
                {t('刷新')}
              </span>
              <InfoTips
                class='ml-12'
                tips={t('作为清洗调试的原始数据')}
              />
            </div>
            <bk-input
              type='textarea'
              value={logOriginal.value}
              on-change={(val: string) => {
                logOriginal.value = val;
              }}
            />
          </div>
        </div>
        {!props.isTempField && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('开启清洗')}</span>
            <div class='form-box mt-5 clean-enable-row'>
              <bk-switcher
                size='large'
                theme='primary'
                value={isClean.value}
                disabled={props.isCleanField && !cleanCollectorId.value}
                on-change={(val: boolean) => {
                  const type = val ? 'bk_log_json' : 'bk_log_text';
                  cleaningMode.value = type;
                  if (!val) {
                    formData.value.etl_params.retain_extra_json = false;
                    // 关闭清洗：解绑已关联的清洗模板
                    handleUnbindTemplate();
                    // 关闭清洗：清空字段列表数据
                    formData.value.etl_fields = [];
                    // 关闭清洗：重置指定日志时间相关字段
                    formData.value.log_reporting_time = true;
                    formData.value.field_name = '';
                    formData.value.time_format = '';
                    formData.value.time_zone = '';
                  }
                }}
              />
              {isClean.value && (
                <div class='bk-button-group clean-rule-mode-group'>
                  <bk-button
                    class={{ 'is-selected': cleanRuleMode.value === 'manual' }}
                    on-click={() => {
                      cleanRuleMode.value = 'manual';
                    }}
                  >
                    {t('手动配置清洗规则')}
                  </bk-button>
                  <bk-button
                    class={{ 'is-selected': cleanRuleMode.value === 'template' }}
                    on-click={() => {
                      cleanRuleMode.value = 'template';
                    }}
                  >
                    {t('使用模板')}
                  </bk-button>
                </div>
              )}
            </div>
          </div>
        )}
        {isClean.value && cleanRuleMode.value === 'manual' && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('清洗模式')}</span>
            <div class='form-box'>
              <div class='bk-button-group'>
                {cleaningModeList.map(mode => (
                  <bk-button
                    key={mode.value}
                    class={{ 'is-selected': mode.value === cleaningMode.value }}
                    on-click={() => handleChangeCleaningMode(mode)}
                  >
                    {mode.label}
                  </bk-button>
                ))}
              </div>
              {renderCleaningMode()}
            </div>
          </div>
        )}
        {isClean.value && cleanRuleMode.value === 'template' && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('清洗模板')}</span>
            <div class='form-box'>
              {currentSelectedTemplate.value ? (
                <div class='bound-template-wrapper'>
                  {/* 已绑定模板卡片 */}
                  <div class='bound-template-card'>
                    {/* 左侧：类型 icon 块 */}
                    <div class='template-card-icon-box'>
                      <i class={getCleanTypeIcon(currentSelectedTemplate.value.clean_type)}></i>
                    </div>
                    {/* 中部：模板名 + 标签 + 描述 */}
                    <div class='template-card-content'>
                      <div class='template-card-header'>
                        <span
                          class='template-card-name'
                          title={currentSelectedTemplate.value.name}
                        >
                          {currentSelectedTemplate.value.name}
                        </span>
                        <span class='template-card-tag'>
                          <i class='bklog-icon bklog-feature-tezheng' />
                          {
                            (currentSelectedTemplate.value.etl_fields ?? []).filter(field => !field.is_delete).length
                          } | {getCleanTypeLabel(currentSelectedTemplate.value.clean_type)}
                        </span>
                      </div>
                      {currentSelectedTemplate.value.description && (
                        <div
                          class='template-card-desc'
                          title={currentSelectedTemplate.value.description}
                        >
                          {currentSelectedTemplate.value.description}
                        </div>
                      )}
                    </div>
                  </div>
                  {/* 卡片外操作按钮 */}
                  <div class='template-card-actions'>
                    <span
                      class='action-link'
                      on-click={handleReselectTemplate}
                    >
                      <i class='bklog-icon bklog-edit' />
                      {t('重新选择')}
                    </span>
                    <BklogPopover
                      ref={unbindPopoverRef}
                      trigger='click'
                      options={
                        {
                          placement: 'bottom-end',
                          theme: 'bklog-light',
                          appendTo: document.body,
                          arrow: false,
                          hideOnClick: false,
                        } as any
                      }
                      content={renderUnbindPopoverContent}
                    >
                      <span class='action-link'>
                        <i class='bklog-icon bklog-jiebang' />
                        {t('解除绑定')}
                      </span>
                    </BklogPopover>
                  </div>
                </div>
              ) : (
                <bk-button
                  theme='primary'
                  icon='plus'
                  outline={true}
                  on-click={() => {
                    cleanTemplateDialogVisible.value = true;
                  }}
                >
                  {t('选择清洗模板')}
                </bk-button>
              )}
            </div>
          </div>
        )}
      </div>
    );
    /** 清洗结果（字段列表） */
    const renderCleanResult = () => (
      <div class='clean-result'>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('字段列表')}</span>
          <div class='form-box'>
            <FieldList
              ref={fieldListRef}
              builtInFieldsList={builtInFieldsList.value}
              data={formData.value.etl_fields || []}
              extractMethod={cleaningMode.value}
              isTemplateSource={isTemplateBound.value}
              loading={isDebugLoading.value || basicLoading.value}
              refresh={isValueRefresh.value}
              originalTextTokenizeOnChars={defaultParticipleStr.value}
              selectEtlConfig={cleaningMode.value}
              on-change={data => {
                formData.value.etl_fields = data;
              }}
              on-refresh={() => debugHandler('refresh')}
              on-unbind-template={handleUnbindTemplate}
            />
          </div>
        </div>
      </div>
    );
    /** 动态字段解析层级：独立渲染，避免影响「JSON 字段动态新增」 */
    const renderExpandDepthConfig = () => (
      <div class='label-form-box expand-depth-form-box'>
        <span class='label-title no-require'>{t('动态字段解析层级（实验）')}</span>
        <div class='form-box expand-depth-config'>
          <bk-select
            class='expand-depth-select'
            clearable={false}
            disabled={isTemplateBound.value}
            value={expandDepthSelect.value}
            on-selected={handleExpandDepthSelected}
            style='width: 300px;'
          >
            {expandDepthOptions.value.map(option => (
              <bk-option
                id={option.id}
                key={option.id}
                name={option.name}
              >
                <div class='expand-depth-option'>
                  <span
                    class='expand-depth-option-name'
                    style='margin-right: 10px;'
                  >
                    {option.name}
                  </span>
                  <span class='expand-depth-option-desc'>{option.desc}</span>
                </div>
              </bk-option>
            ))}
          </bk-select>
          <p class='expand-depth-tips'>{t('解析层级越大，可直接检索的字段越多，但也更容易达到 ES 字段数量上限。')}</p>
          {expandDepthSelect.value === UNLIMITED_EXPAND_DEPTH && (
            <bk-alert
              class='expand-depth-alert'
              type='warning'
              title={t(
                '无限解析可能产生大量动态字段，达到 ES 字段上限后，相关日志可能写入失败。建议仅在字段结构稳定时使用。',
              )}
            />
          )}
          <bk-button
            class='expand-depth-example-btn'
            text
            theme='primary'
            on-click={() => {
              expandDepthExampleVisible.value = true;
            }}
          >
            {t('查看解析示例')}
          </bk-button>
        </div>
      </div>
    );

    /** 高级设置表单内容 */
    const renderAdvancedContent = () => (
      <div class='advanced-setting'>
        <div class='label-form-box'>
          <span class='label-title'>{t('原始日志')}</span>
          <div class='form-box'>
            <bk-radio-group
              value={formData.value.etl_params.retain_original_text}
              on-change={(val: boolean) => {
                formData.value.etl_params.retain_original_text = val;
              }}
            >
              <bk-radio
                class='mr-24'
                disabled={isTemplateBound.value}
                value={true}
              >
                <span
                  v-bk-tooltips={{
                    content: t('确认保留原始日志,会存储在log字段. 其他字段提取内容会进行追加'),
                    disabled: isTemplateBound.value,
                  }}
                >
                  {t('保留')}
                </span>
              </bk-radio>
              <bk-radio
                disabled={isTemplateBound.value}
                value={false}
              >
                <span
                  v-bk-tooltips={{
                    content: t('不保留将丢弃原始日志，仅展示清洗后日志。请通过字段清洗，调试并输出您关心的日志。'),
                    disabled: isTemplateBound.value,
                  }}
                >
                  {t('丢弃')}
                </span>
              </bk-radio>
            </bk-radio-group>
            {formData.value.etl_params.retain_original_text && (
              <div class='select-group'>
                <div class='select-item'>
                  <span class='select-title'>{t('分词符')}</span>
                  <bk-select
                    class='select-box'
                    clearable={false}
                    disabled={isTemplateBound.value}
                    value={originParticipleState.value}
                    on-selected={val => {
                      originParticipleState.value = val;
                      formData.value.etl_params.original_text_tokenize_on_chars =
                        val === 'custom' ? defaultParticipleStr.value : '';
                    }}
                  >
                    {participleList.map(option => (
                      <bk-option
                        id={option.id}
                        key={option.id}
                        name={option.name}
                      />
                    ))}
                  </bk-select>
                </div>
                {originParticipleState.value === 'custom' && (
                  <bk-input
                    class='select-input'
                    disabled={isTemplateBound.value}
                    value={formData.value.etl_params.original_text_tokenize_on_chars}
                    on-input={val => {
                      formData.value.etl_params.original_text_tokenize_on_chars = val;
                    }}
                  />
                )}
                <div class='select-item'>
                  <bk-checkbox
                    class='mr-5'
                    disabled={isTemplateBound.value}
                    value={formData.value.etl_params.original_text_is_case_sensitive}
                    on-change={val => {
                      formData.value.etl_params.original_text_is_case_sensitive = val;
                    }}
                  />
                  {t('大小写敏感')}
                </div>
              </div>
            )}
          </div>
        </div>
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('指定日志时间')}</span>
          <div class='form-box'>
            <bk-radio-group
              value={formData.value.log_reporting_time}
              on-change={val => {
                formData.value.log_reporting_time = val;
              }}
            >
              <bk-radio
                class='mr-24'
                disabled={isTemplateBound.value}
                value={true}
              >
                {t('日志上报时间')}
              </bk-radio>
              <bk-radio
                disabled={isTemplateBound.value}
                value={false}
              >
                {t('指定字段为日志时间')}
              </bk-radio>
            </bk-radio-group>
            {!formData.value.log_reporting_time && (
              <div class='select-group'>
                <div class='select-item'>
                  <span class='select-title'>{t('字段')}</span>
                  <bk-select
                    class='select-box'
                    disabled={isTemplateBound.value}
                    value={formData.value.field_name}
                    on-selected={(val: string) => {
                      formData.value.field_name = val;
                    }}
                  >
                    {formData.value.etl_fields.map(item => (
                      <bk-option
                        id={item.field_name}
                        key={`${item.field_index}${item.field_name}`}
                        name={item.field_name}
                      />
                    ))}
                  </bk-select>
                </div>
                <div class='select-item'>
                  <span class='select-title'>{t('时间格式')}</span>
                  <bk-select
                    class='select-box'
                    disabled={isTemplateBound.value}
                    value={formData.value.time_format}
                    on-selected={val => {
                      formData.value.time_format = val;
                    }}
                  >
                    {fieldDateFormat.value.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={`${item.name} (${item.description})`}
                      />
                    ))}
                  </bk-select>
                </div>
                <div class='select-item'>
                  <span class='select-title'>{t('时区选择')}</span>
                  <bk-select
                    class='select-box'
                    disabled={isTemplateBound.value}
                    value={formData.value.time_zone}
                    on-selected={val => {
                      formData.value.time_zone = val;
                    }}
                  >
                    {timeZone.value.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </bk-select>
                </div>
              </div>
            )}
          </div>
        </div>
        {timeCheckErrContent.value && <p class='format-error'>{timeCheckErrContent.value}</p>}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('失败日志')}</span>
          <bk-radio-group
            class='form-box'
            value={formData.value.etl_params.enable_retain_content}
            on-change={(val: boolean) => {
              formData.value.etl_params.enable_retain_content = val;
            }}
          >
            <bk-radio
              class='mr-24'
              disabled={isTemplateBound.value}
              value={true}
            >
              {t('保留')}
            </bk-radio>
            <bk-radio
              disabled={isTemplateBound.value}
              value={false}
            >
              {t('丢弃')}
            </bk-radio>
          </bk-radio-group>
        </div>
        {cleaningMode.value === 'bk_log_json' && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('JSON 字段动态新增')}</span>
            <div class='form-box mt-5'>
              <bk-switcher
                size='large'
                theme='primary'
                disabled={isTemplateBound.value}
                value={formData.value.etl_params.retain_extra_json}
                on-change={(val: boolean) => {
                  // 整体替换 etl_params，确保 Vue2 能触发 showExpandDepthConfig 更新
                  formData.value.etl_params = {
                    ...formData.value.etl_params,
                    retain_extra_json: val,
                  };
                  syncExpandDepthOnRetainExtraJsonChange(val);
                }}
              />
              <InfoTips
                class='ml-12'
                tips={t(
                  '在日志采集中，若您的日志中产生新的JSON字段，我们会自动采集并合入 __ext_json 字段中，您可以通过 __ext_json.xxx 检索该数据',
                )}
              />
            </div>
          </div>
        )}
        {showExpandDepthConfig.value ? renderExpandDepthConfig() : null}
        <div class='label-form-box'>
          <span class='label-title no-require'>{t('路径元数据')}</span>
          <div class='form-box mt-5'>
            <bk-switcher
              size='large'
              theme='primary'
              disabled={isTemplateBound.value}
              value={enableMetaData.value}
              on-change={(val: boolean) => {
                enableMetaData.value = val;
              }}
            />
            <InfoTips
              class='ml-12'
              tips={t('定义元数据并补充至日志中，可通过元数据进行过滤筛选')}
            />
          </div>
        </div>
        {enableMetaData.value && (
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('路径样例')}</span>
            <div
              class='form-box'
              v-bkloading={{ isLoading: pathExampleLoading.value }}
            >
              <div class='url-demo-box'>
                <bk-input
                  class='input-box'
                  disabled={isTemplateBound.value}
                  value={pathExample.value}
                  on-change={val => {
                    pathExample.value = val;
                  }}
                />
                <i
                  class='bklog-icon bklog-refresh-icon icons'
                  on-click={() => getDataLog('pathRefresh')}
                />
              </div>
            </div>
          </div>
        )}
        {enableMetaData.value && (
          <div class='label-form-box'>
            <span class='label-title'>{t('采集路径分割正则')}</span>
            <div class='form-box'>
              <div class='url-demo-box'>
                <bk-input
                  class='input-box'
                  disabled={isTemplateBound.value}
                  placeholder={defaultRegex}
                  value={formData.value.etl_params.path_regexp}
                  on-input={val => {
                    formData.value.etl_params = {
                      ...formData.value.etl_params,
                      path_regexp: val,
                    };
                  }}
                />
                <bk-button
                  class='debug-btn'
                  disabled={isTemplateBound.value || !showDebugPathRegexBtn.value || isPathDebugLoading.value}
                  on-click={debuggerPathRegex}
                >
                  {t('调试')}
                </bk-button>
              </div>
              <div class='debug-box'>
                {(formData.value.etl_params.metadata_fields || []).map(item => (
                  <div
                    key={item.field_name}
                    class='metadata-fields-item'
                  >
                    <div
                      class='item-name'
                      title={item.field_name}
                    >
                      {item.field_name}
                    </div>
                    <span class='symbol'>:</span>
                    <div
                      class='item-value'
                      title={item.value}
                    >
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    );

    /** 模板绑定时高级设置的统一只读提示 */
    const renderTemplateBoundTipContent = () => (
      <div class='template-bound-tip-content'>
        <span>{t('当前清洗配置处于模板绑定状态，无法修改采集配置。如需修改，请点击')}</span>
        <span
          class='template-unbind-link'
          on-click={handleAdvancedTemplateUnbind}
        >
          {t('解除绑定')}
        </span>
      </div>
    );

    /** 高级设置 */
    const renderAdvanced = () => {
      const advancedContent = renderAdvancedContent();
      if (!isTemplateBound.value) {
        return advancedContent;
      }

      return (
        <BklogPopover
          ref={advancedTemplateBoundPopoverRef}
          trigger='hover'
          hideDelay={600}
          options={
            {
              placement: 'top',
              theme: 'bklog-dark',
              appendTo: document.body,
              offset: [0, 8],
            } as any
          }
          content={renderTemplateBoundTipContent}
        >
          <div class='template-bound-advanced-target'>{advancedContent}</div>
        </BklogPopover>
      );
    };
    /**
     *
     * @returns 可见范围
     */
    const renderVisibility = () => {
      const { virtualscrollSpaceList, isUseMark } = useSpaceSelector(visibleBkBiz);
      isUseMark.value = false;
      return (
        <div class='visibility-settings'>
          <div class='label-form-box'>
            <span class='label-title no-require'>{t('可见范围')}</span>
            <div class='form-box'>
              <bk-radio-group
                value={formData.value.visible_type}
                on-change={(val: string) => {
                  formData.value.visible_type = val;
                  visibleBkBiz.value = val !== 'multi_biz' ? [] : structuredClone(cacheVisibleList.value);
                }}
              >
                {visibleScopeSelectList.map(item => (
                  <bk-radio
                    class='mr-24'
                    value={item.id}
                  >
                    {item.name}
                  </bk-radio>
                ))}
              </bk-radio-group>
            </div>
          </div>
          {formData.value.visible_type === 'multi_biz' && (
            <div class='label-form-box'>
              <span class='label-title no-require'></span>
              <div class='form-box'>
                <bk-select
                  style='width: 500px;'
                  value={visibleBkBiz.value}
                  list={mySpaceList.value}
                  virtual-scroll-render={virtualscrollSpaceList}
                  display-key={'space_full_code_name'}
                  id-key={'bk_biz_id'}
                  display-tag
                  enable-virtual-scroll
                  multiple
                  searchable
                  on-change={val => {
                    console.log(val, 'val');
                    visibleBkBiz.value = val;
                    formData.value.visible_bk_biz_id = val;
                  }}
                />
              </div>
            </div>
          )}
        </div>
      );
    };
    const renderBasicInfo = () => (
      <div class='template-basic-info'>
        <div class='label-form-box'>
          <span class='label-title'>{t('模板名称')}</span>
          <div class='form-box'>
            <bk-input
              placeholder={t('请输入')}
              value={templateName.value}
              on-change={val => {
                templateName.value = val;
              }}
            />
          </div>
        </div>
        <div class='label-form-box template-description-row'>
          <span class='label-title no-require'>{t('模板描述')}</span>
          <div class='form-box'>
            <bk-input
              maxlength={128}
              placeholder={t('请输入')}
              rows={3}
              show-word-limit
              type='textarea'
              value={templateDescription.value}
              on-change={val => {
                templateDescription.value = val;
              }}
            />
          </div>
        </div>
      </div>
    );
    // 显式收集卡片内依赖，避免 Vue2 下嵌套 renderFn 漏追踪导致开关变更后高级设置不刷新
    const cardConfig = computed(() => {
      void cleaningMode.value;
      void formData.value.etl_params?.retain_extra_json;
      void formData.value.log_reporting_time;
      void enableMetaData.value;
      void isExtJsonExpandDepthEnabled.value;
      void expandDepthSelect.value;
      return [
        {
          title: t('基础信息'),
          key: 'basicInfo',
          renderFn: renderBasicInfo,
        },
        {
          title: t('清洗设置'),
          key: 'cleanSetting',
          renderFn: renderSetting,
        },
        {
          title: t('清洗结果'),
          key: 'cleanResult',
          renderFn: renderCleanResult,
        },
        {
          title: t('高级设置'),
          key: 'advancedSetting',
          renderFn: renderAdvanced,
        },
        {
          title: t('可见范围设置'),
          key: 'visibilitySettings',
          renderFn: renderVisibility,
        },
      ];
    });
    /**
     * 按当前「指定日志时间」选项同步 etl_fields 的 is_time / option 状态
     * - 日志上报时间：清除所有字段的 is_time 与 option 中的时间信息
     * - 指定字段为日志时间：仅指定字段保留 is_time 与时间配置
     */
    const syncLogTimeFields = () => {
      if (!formData.value.log_reporting_time) {
        const list = formData.value.etl_fields.map(item => {
          const isTime = item.field_name === formData.value.field_name;
          return {
            ...item,
            is_time: isTime,
            option: {
              time_zone: isTime ? formData.value.time_zone : '',
              time_format: isTime ? formData.value.time_format : '',
            },
          };
        });
        formData.value.etl_fields = list;
      } else {
        // 日志上报时间：清除所有字段的 is_time 和 option 中的时间信息
        formData.value.etl_fields = formData.value.etl_fields.map(item => ({
          ...item,
          is_time: false,
          option: {
            time_zone: '',
            time_format: '',
          },
        }));
      }
    };
    /**
     * 提交前的相关检验
     * @param callback
     * @param failedCallback
     * @returns
     */
    const handleSubmitValidate = async (callback: () => void, failedCallback?: () => void) => {
      loading.value = true;
      // 校验字段表格
      const validatePromises = fieldListRef.value?.validateFieldTable();
      if (validatePromises && validatePromises.length > 0) {
        try {
          await Promise.all(validatePromises);
        } catch {
          loading.value = false;
          failedCallback?.();
          return;
        }
      }
      /**
       * 校验时间格式， 校验通过之后，把指定的时间字段的 is_time 设置为 true
       */
      if (!formData.value.log_reporting_time) {
        const res = await requestCheckTime();
        if (!res) {
          loading.value = false;
          failedCallback?.();
          return;
        }
      }
      syncLogTimeFields();
      const { etl_fields } = formData.value;

      if (isClean.value && etl_fields.length === 0) {
        showMessage(t('请完成相关的清洗配置'), 'error');
        loading.value = false;
        failedCallback?.();
        return;
      }
      callback?.();
    };
    /**
     * 保存按钮
     * @param options 保存选项配置
     * @param options.action 操作类型: 'next'(默认) | 'back' | 'saveOnly'
     * @param options.callback 保存完成后的回调函数
     */
    const handleSubmitSave = async ({ action = 'next', callback }: ISubmitOptions = {}) => {
      handleSubmitValidate(
        async () => {
          isChangingExpandDepth.value =
            isExtJsonExpandDepthEnabled.value &&
            !!formData.value.etl_params?.retain_extra_json &&
            isExpandDepthChanged(
              expandDepthSelect.value,
              originExpandDepthSelect.value,
              originHadExtJsonConfig.value,
              originRetainExtraJson.value,
            );
          const confirmed = await confirmExpandDepthChange();
          if (!confirmed) {
            isChangingExpandDepth.value = false;
            loading.value = false;
            callback?.(false);
            return;
          }

          // 提交前按当前时间选项重新同步 is_time，确保切换「日志上报时间」后提交数据生效
          syncLogTimeFields();

          const { etl_params: etlParams, etl_fields } = formData.value;
          const submitEtlParams = structuredClone(etlParams);
          if (enableMetaData.value) {
            // 为 metadata_fields 每项补充 metadata_type（对齐旧版）
            const metadataFields =
              submitEtlParams.metadata_fields?.map(item => {
                item.metadata_type = 'path';
                return item;
              }) ?? [];
            submitEtlParams.metadata_fields = metadataFields;
          } else {
            submitEtlParams.path_regexp = null;
            submitEtlParams.metadata_fields = [];
          }
          const {
            storage_cluster_id,
            allocation_min_days,
            storage_replies,
            es_shards,
            table_id,
            retention,
            storage_shards_nums,
          } = curCollect.value;
          /**
           * 编辑/创建清洗
           * 未完成的情况下，调用创建清洗配置接口 （storage_cluster_id = -1 或者为空，都代表未完成）
           */
          const isNeedCreate = (isUpdate.value && !!storage_cluster_id) || props.isCleanField;
          const url = isNeedCreate ? 'collect/fieldCollection' : 'clean/updateCleanStash';
          // 构建 payload（对齐旧版逻辑）
          const payload: Record<string, any> = {
            retain_original_text: submitEtlParams.retain_original_text,
            original_text_is_case_sensitive: submitEtlParams.original_text_is_case_sensitive ?? false,
            original_text_tokenize_on_chars: submitEtlParams.original_text_tokenize_on_chars ?? '',
            retain_extra_json: submitEtlParams.retain_extra_json ?? false,
            path_regexp: submitEtlParams.path_regexp,
            enable_retain_content: submitEtlParams.enable_retain_content,
            record_parse_failure: submitEtlParams.enable_retain_content,
            metadata_fields: submitEtlParams.metadata_fields,
          };
          if (
            shouldSubmitExtJsonConfig({
              retainExtraJson: !!payload.retain_extra_json,
              featureEnabled: isExtJsonExpandDepthEnabled.value,
              currentSelect: expandDepthSelect.value,
              originHadConfig: originHadExtJsonConfig.value,
              originRetainExtraJson: originRetainExtraJson.value,
            })
          ) {
            // 仅提交 expand_depth，不覆盖后台隐藏的 overflow_strategy
            payload.ext_json_config = {
              expand_depth: toSubmitExpandDepth(expandDepthSelect.value),
            };
            // 同步到 formData，供存储步骤透传
            formData.value.etl_params = {
              ...formData.value.etl_params,
              ext_json_config: { expand_depth: payload.ext_json_config.expand_depth },
            };
          } else if (formData.value.etl_params.ext_json_config) {
            // 存量无限场景：不主动改写，同时避免把 overflow_strategy 透传到下一步
            const { ext_json_config: _ignored, ...rest } = formData.value.etl_params as any;
            formData.value.etl_params = rest;
          }
          const data = {
            bk_biz_id: bkBizId.value,
            etl_params: {
              separator_regexp: cleaningMode.value === 'bk_log_regexp' ? submitEtlParams.separator_regexp : '',
              separator: submitEtlParams.separator,
              ...payload,
              ...(cleaningMode.value === 'bk_log_regexp' ? { is_grok: grokModeEnabled.value } : {}),
            },
          };
          const fieldsList = cleaningMode.value === 'bk_log_text' ? [] : etl_fields;
          const isDorisEdit = isUpdate.value && curCollect.value.storage_cluster_type === 'doris';
          const requestData = isNeedCreate
            ? {
                ...data,
                clean_template_id: getSubmitCleanTemplateId(),
                fields: fieldsList,
                storage_cluster_id,
                allocation_min_days: allocation_min_days ?? (isDorisEdit ? 0 : undefined),
                storage_replies,
                es_shards: es_shards ?? storage_shards_nums,
                table_id,
                retention: retention ?? (isDorisEdit ? 7 : undefined),
                etl_config: cleaningMode.value,
              }
            : {
                ...data,
                clean_template_id: getSubmitCleanTemplateId(),
                etl_fields: fieldsList,
                clean_type: cleaningMode.value,
              };
          $http
            .request(url, {
              params: {
                collector_config_id: curCollect.value.collector_config_id,
              },
              data: requestData,
            })
            .then(res => {
              loading.value = false;
              if (res?.result) {
                const showedDepthSuccess = isChangingExpandDepth.value && isNeedCreate;
                if (showedDepthSuccess) {
                  const depthLabel = getExpandDepthLabel(expandDepthSelect.value, key => t(key));
                  showMessage(t('动态字段解析层级已生效，新写入数据将按 {n} 解析。', { n: depthLabel }));
                  originHadExtJsonConfig.value = true;
                  originRetainExtraJson.value = true;
                  originExpandDepthSelect.value = expandDepthSelect.value;
                  isChangingExpandDepth.value = false;
                }
                if (action === 'saveOnly') {
                  // 只保存，不跳转
                  if (!showedDepthSuccess) {
                    showMessage(t('保存成功'));
                  }
                  callback?.(true);
                } else if (action === 'back') {
                  if (!showedDepthSuccess) {
                    showMessage(t('保存成功'));
                  }
                  // 保存成功后跳转到列表页
                  goListPage();
                } else {
                  const data = isNeedCreate
                    ? {
                        ...formData.value,
                        ...curCollect.value,
                        clean_template_id: getSubmitCleanTemplateId(),
                        etl_config: cleaningMode.value,
                      }
                    : {
                        ...formData.value,
                        clean_template_id: getSubmitCleanTemplateId(),
                        etl_config: cleaningMode.value,
                      };
                  emit('next', data);
                  if (props.isCleanField) {
                    emit('change-submit', true);
                  }
                }
              } else {
                if (isChangingExpandDepth.value && isNeedCreate) {
                  showMessage(t('配置未生效，创建新索引失败，请重试或联系管理员。'), 'error');
                  isChangingExpandDepth.value = false;
                }
                callback?.(false);
              }
            })
            .catch(() => {
              loading.value = false;
              if (isChangingExpandDepth.value && isNeedCreate) {
                showMessage(t('配置未生效，创建新索引失败，请重试或联系管理员。'), 'error');
                isChangingExpandDepth.value = false;
              }
              callback?.(false);
            });
        },
        () => callback?.(false),
      );
    };

    expose({
      hasConfigChanged,
      handleSubmitSave,
    });

    return () => (
      <div
        class='operation-step3-clean'
        v-bkloading={{ isLoading: basicLoading.value }}
      >
        {cardRender(showCardConfig.value)}
        <CleanTemplateDialog
          visible={cleanTemplateDialogVisible.value}
          bkBizId={bkBizId.value}
          on-close={() => {
            cleanTemplateDialogVisible.value = false;
          }}
          on-preview={template => {
            // "浏览清洗结果"：关闭选择模板弹窗，打开预览弹窗
            pendingSelectedTemplate.value = template;
            cleanTemplateDialogVisible.value = false;
            cleanResultPreviewDialogVisible.value = true;
          }}
        />
        <CleanResultPreviewDialog
          visible={cleanResultPreviewDialogVisible.value}
          bkBizId={bkBizId.value}
          template={pendingSelectedTemplate.value ?? currentSelectedTemplate.value}
          collectorConfigId={curCollect.value?.collector_config_id || ''}
          logExample={logOriginal.value}
          logExampleLoading={logOriginalLoading.value}
          isTempField={props.isTempField}
          originalTextTokenizeOnChars={defaultParticipleStr.value}
          collectStatus={props.collectStatus}
          on-close={() => {
            pendingSelectedTemplate.value = null;
            cleanResultPreviewDialogVisible.value = false;
          }}
          on-refresh={() => {
            getDataLog('refresh');
          }}
          on-confirm={(templateData, logExample, isTemplateConfigModified) => {
            const appliedTemplate = applyEtlConfigToForm(templateData);
            if (isTemplateConfigModified) {
              handleUnbindTemplate();
            } else {
              currentSelectedTemplate.value = appliedTemplate;
              cleanTemplateId.value = appliedTemplate.clean_template_id;
              cleanRuleMode.value = 'template';
            }
            // 同步弹窗中可能被修改的调试样例
            if (typeof logExample === 'string') {
              logOriginal.value = logExample;
            }
            pendingSelectedTemplate.value = null;
            cleanResultPreviewDialogVisible.value = false;
          }}
        />
        <ReportLogSlider
          isShow={showReportLogSlider.value}
          jsonText={jsonText.value}
          on-change={value => {
            showReportLogSlider.value = value;
          }}
        />
        <bk-dialog
          ext-cls='expand-depth-example-dialog'
          header-position='left'
          mask-close={true}
          show-footer={false}
          title={t('解析示例')}
          value={expandDepthExampleVisible.value}
          width={640}
          on-cancel={() => {
            expandDepthExampleVisible.value = false;
          }}
          on-value-change={(val: boolean) => {
            expandDepthExampleVisible.value = val;
          }}
        >
          <div class='expand-depth-example-content'>
            <div class='example-block'>
              <div class='example-label'>{t('输入')}</div>
              <pre class='example-code'>{expandDepthExampleInput}</pre>
            </div>
            <div class='example-block'>
              <div class='example-label'>{expandDepthExampleTitle.value}</div>
              <pre class='example-code'>{expandDepthExampleResult.value}</pre>
              <p class='example-note'>{expandDepthExampleNote.value}</p>
            </div>
          </div>
        </bk-dialog>
        <div class='classify-btns-fixed'>
          {!props.isTempField && !props.isCleanField && (
            <bk-button
              class='mr-8'
              on-click={() => {
                emit('prev', props.configData);
              }}
            >
              {t('上一步')}
            </bk-button>
          )}
          {!props.isTempField && (
            <bk-button
              class='width-88 mr-8'
              theme='primary'
              loading={loading.value}
              on-click={() => handleSubmitSave()}
            >
              {props.isCleanField ? t('保存') : t('下一步')}
            </bk-button>
          )}
          {/* 提交按钮：编辑模式且非清洗列表编辑且非模板编辑且显示"下一步"时显示 */}
          {isUpdate.value && !props.isCleanField && !props.isTempField && !props.isCleanField && (
            <bk-button
              class='width-88 mr-8'
              theme='primary'
              loading={loading.value}
              on-click={() => handleSubmitSave({ action: 'back' })}
            >
              {t('提交')}
            </bk-button>
          )}

          {props.isTempField ? (
            <bk-button
              class='width-88 mr-8'
              theme='primary'
              loading={loading.value}
              on-click={handleTemplateSubmit}
            >
              {isEditTemp.value ? t('保存') : t('提交')}
            </bk-button>
          ) : (
            <bk-button
              class='template-btn'
              disabled={formData.value.etl_fields.length === 0}
              on-click={() => {
                handleSubmitValidate(() => {
                  loading.value = false;
                  templateDialogVisible.value = true;
                });
              }}
            >
              {t('另存为模板')}
            </bk-button>
          )}
          {!props.isTempField && !props.isCleanField && (
            <bk-button
              class='mr-8'
              on-click={async () => {
                formData.value = deepClone(cacheTemplateData.value);
                pendingSelectedTemplate.value = null;
                cleaningMode.value = cacheTemplateData.value.etl_config;
                visibleBkBiz.value = cacheTemplateData.value.visible_bk_biz_id;
                enableMetaData.value = !!cacheTemplateData.value.etl_params.path_regexp;
                await restoreCleanTemplateAssociation(initialCleanTemplateId.value);
              }}
            >
              {t('重置')}
            </bk-button>
          )}
          <bk-button
            on-click={() => {
              emit('cancel');
            }}
          >
            {t('取消')}
          </bk-button>
        </div>
        {/* 另存为模板弹窗 */}
        <bk-dialog
          width='480'
          draggable={false}
          ext-cls='clean-template-save-as-dialog'
          header-position={'left'}
          mask-close={false}
          auto-close={false}
          loading={loading.value}
          title={t('另存为模板')}
          value={templateDialogVisible.value}
          on-confirm={handleTempConfirm}
          on-cancel={() => {
            templateDialogVisible.value = false;
          }}
        >
          <div class='template-content'>
            <span class='template-label'>{t('模板名称')}</span>
            <bk-input
              class='template-input'
              value={templateName.value}
              on-change={val => {
                templateName.value = val;
              }}
            />
            <span class='template-label template-desc-label'>{t('模板描述')}</span>
            <bk-input
              class='template-input'
              type='textarea'
              rows={3}
              maxlength={128}
              show-word-limit
              placeholder={t('请输入')}
              value={templateDescription.value}
              on-change={val => {
                templateDescription.value = val;
              }}
            />
          </div>
        </bk-dialog>
        <bk-dialog
          width='480'
          ext-cls='template-save-confirm-dialog'
          mask-close={false}
          show-footer={false}
          title=''
          value={templateSaveConfirmVisible.value}
          on-cancel={() => {
            templateSaveConfirmVisible.value = false;
          }}
        >
          <div class='template-save-confirm'>
            <div class='confirm-warning-icon'>
              <i class='bk-icon icon-exclamation' />
            </div>
            <div class='confirm-title'>{t('保存模板变更')}</div>
            <div class='confirm-description'>
              <i18n path={t('当前模板已生效到{0}个采集项，关联{1}个索引集')}>
                <strong class='collector-count'>{templateCollectorCount.value}</strong>
                <strong>{templateIndexSetCount.value}</strong>
              </i18n>
              <div>
                {t('选择<同步所有采集项> 后，系统会将最新配置更新到全部关联采集项，可能会影响线上日志字段解析结果。')}
              </div>
            </div>
            <div class='confirm-actions'>
              <bk-button
                theme='primary'
                loading={loading.value}
                on-click={() => handleTempConfirm(true)}
              >
                {t('同步所有采集项')}
              </bk-button>
              <bk-button
                disabled={loading.value}
                on-click={() => handleTempConfirm(false)}
              >
                {t('仅保存模板')}
              </bk-button>
            </div>
          </div>
        </bk-dialog>
      </div>
    );
  },
});
