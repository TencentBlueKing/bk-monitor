import { RadioGroup as TRadioGroup, Radio as TRadio, Switch as TSwitch } from 'tdesign-vue-next';

import { MessagePlugin as TDesignMessage, Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
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

import { defineComponent, ref, computed, watch } from 'vue';
import {
  Drawer as TDrawer,
  Form as TForm,
  FormItem as TFormItem,
  Input as TInput,
  InputNumber as TInputNumber,
  Select as TSelect,
  Option as TOption,
  type FormInstanceFunctions,
} from 'tdesign-vue-next';
import { overlayRegistry } from '@/shared/global/overlay/overlay-registry';

import { messageError } from '@/shared/lib/bkmagic';
import { isFeatureToggleOn } from '@/shared/composables/use-feature-toggle';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import BklogLoading from '@/shared/ui/loading';
import ValidateUserSelector from '@/shared/ui/user-selector/index';

import { useSidebarDiff } from '@/shared/composables/use-sidebar-diff';
import { useSpaceSelector } from '@/shared/composables/use-space-selector';
import ManageHelper from '../../../management/manage-v2/manage-helper.ts';
import EsDialog from './es-dialog.tsx';
import { CLUSTER_TYPES } from './use-cluster-type';

import './es-slider.scss';

interface HotColdNode {
  attr: string;
  value: string;
}
interface HotColdOption extends HotColdNode {
  computedId: string;
  computedName: string;
  computedCounts: number;
  isSelected: boolean;
}
interface BusinessProperty {
  id: string;
  name: string;
  multiable?: boolean;
  remote?: boolean;
}
interface BusinessLabel extends BusinessProperty {
  values: BusinessProperty[];
}
interface RetentionOption {
  id: string;
  name: string;
  disabled?: boolean;
}

export default defineComponent({
  name: 'EsSlider',
  components: {
    EsDialog,
    ValidateUserSelector,
  },
  props: {
    // 是否显示侧滑
    showSlider: {
      type: Boolean,
      default: false,
    },
    // 编辑的集群 ID
    editClusterId: {
      type: Number,
      default: null,
    },
    clusterType: {
      type: String,
      default: CLUSTER_TYPES.ES,
    },
    clusterData: {
      type: Object,
      default: null,
    },
    onHandleCancelSlider: { type: Function },
    onHandleUpdatedTable: { type: Function },
  },
  emits: ['handleCancelSlider', 'handleUpdatedTable'],
  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();

    // 表单与组件引用
    const validateForm = ref<FormInstanceFunctions>();
    const searchSelectRef = ref<any>(null);

    const configDocUrl = ref((window as any).BK_HOT_WARM_CONFIG_URL);
    const archiveDocUrl = ref((window as any).BK_ARCHIVE_DOC_URL); // 日志归档跳转链接
    const isItsm = ref(isFeatureToggleOn('collect_itsm', [String(store.state.bkBizId), String(store.state.spaceUid)])); // 容量评估全局参数

    const confirmLoading = ref(false); // 确认按钮加载状态
    const sliderLoading = ref(false); // 侧边栏加载状态

    // 连通性测试表单
    const formData = ref<any>({
      cluster_name: '', // 集群英文名称
      display_name: '', // 集群名称
      source_type: '', // 来源
      source_name: '',
      domain_name: '', // 地址
      port: '', // 端口
      schema: 'http', // 协议
      auth_info: {
        username: '', // 用户名
        password: '', // 密码
      },
      enable_hot_warm: false, // 是否开启冷热数据
      hot_attr_name: '', // 热节点属性名称
      hot_attr_value: '', // 热节点属性值
      warm_attr_name: '', // 冷节点属性名称
      warm_attr_value: '', // 冷节点属性值
      setup_config: {
        // 过期时间 副本数
        retention_days_max: 14,
        retention_days_default: 7,
        number_of_replicas_max: 3,
        number_of_replicas_default: 1,
        es_shards_default: 1,
        es_shards_max: 3,
      },
      admin: [], // 负责人名单
      description: '', // 集群说明
      enable_archive: false, // 日志存档开关
      enable_assessment: false, // 容量评估开关
      visible_config: {
        // 可见范围配置
        visible_type: 'current_biz', // 可见范围单选项
        bk_biz_labels: {}, // 按照业务属性选择
        visible_bk_biz: [], // 多个业务
      },
    });

    // 基本信息表单
    const basicFormData = ref<any>({
      cluster_name: '', // 集群英文名称
      display_name: '', // 集群名称
      source_type: '', // 来源
      source_name: '',
      domain_name: '', // 地址
      port: '', // 端口
      schema: 'http', // 协议
      auth_info: {
        username: '', // 用户名
        password: '', // 密码
      },
    });

    // 表单校验规则
    const basicRules = ref<any>({
      source_type: [{ required: true, trigger: 'blur' }],
      cluster_name: [
        { required: true, trigger: 'blur' },
        {
          validator: (val: string) => /^[_A-Za-z0-9][_A-Za-z0-9-]{0,49}$/.test(val),
          message: t('支持字母、数字、下划线、连字符，不能以连字符开头'),
          trigger: 'blur',
        },
      ],
      display_name: [{ required: true, trigger: 'blur' }],
      domain_name: [{ required: true, trigger: 'blur' }],
      port: [{ required: true, trigger: 'blur' }],
    });

    const connectLoading = ref(false); // 连通性测试按钮加载状态
    const connectResult = ref(''); // 连通性测试结果
    const connectFailedMessage = ref(''); // 连通性测试失败信息

    const hotColdOriginList = ref<HotColdNode[]>([]); // 新增编辑时的冷热数据
    const hotColdAttrSet = ref<HotColdOption[]>([]); // 相同 attr value 的集合
    const selectedHotId = ref(''); // 热 attr:value
    const selectedColdId = ref(''); // 冷 attr:value
    const showInstanceDialog = ref(false); // 是否显示实例弹窗
    const viewInstanceType = ref(''); // hot、cold 查看热数据/冷数据实例列表
    const visibleScopeSelectList = ref([
      // 可见范围单选列表
      { id: 'current_biz', name: t('当前空间可见') },
      { id: 'multi_biz', name: t('多空间选择') },
      { id: 'all_biz', name: t('全平台') },
      { id: 'biz_attr', name: t('按照空间属性选择') },
    ]);
    const visibleBkBiz = ref<(string | number)[]>([]); // 下拉框选中的值列表
    const visibleList = ref<{ id: string; name: any; is_use: any }[]>([]); // 多业务选择下拉框
    const cacheVisibleList = ref<{ id: string; name: any; is_use: any }[]>([]); // 缓存多业务选择下拉框
    const bkBizLabelsList = ref<BusinessLabel[]>([]); // 按照业务属性选择列表
    const cacheBkBizLabelsList = ref<BusinessLabel[]>([]); // 缓存按照业务属性选择
    const bizParentList = ref<BusinessProperty[]>([]); // 按照业务属性父级列表
    const bizChildrenList = ref<Record<string, BusinessProperty[]>>({}); // 业务属性选择子级键值对象
    const isShowManagement = ref(false); // 是否展示集群管理
    const retentionDaysList = ref<RetentionOption[]>([]); // 默认过期时间列表
    const maxDaysList = ref<RetentionOption[]>([]); // 最大过期时间列表
    const customRetentionDay = ref(''); // 默认过期时间输入框
    const customMaxDay = ref(''); // 最大过期时间输入框
    const bizSelectID = ref(''); // 选中的当前按照业务属性选择
    const bizInputStr = ref(''); // 按照业务属性选择输入值
    const isFirstShow = ref(true); // 是否是第一次渲染
    const selectZIndex = ref(3007);

    const mySpaceList = computed(() => store.state.mySpaceList);
    const userMeta = computed(() => store.state.userMeta);
    const bkBizId = computed(() => store.getters.bkBizId);
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const isEdit = computed(() => props.editClusterId !== null);
    const isDoris = computed(() => props.clusterType === CLUSTER_TYPES.DORIS);
    const isMultiTenant = computed(() => !!store.state.userMeta?.bk_tenant_id);
    const visibleScopeOptions = computed(() => {
      if (isMultiTenant.value) {
        return [...visibleScopeSelectList.value, { id: 'current_tenant', name: t('当前租户可见') }];
      }
      return visibleScopeSelectList.value;
    });

    // 冷热设置不对，禁用提交
    const invalidHotSetting = computed(() => {
      return formData.value.enable_hot_warm && !(formData.value.hot_attr_name && formData.value.warm_attr_value);
    });

    const isRulesCheckSubmit = computed(() => !formData.value.admin.length);
    const isDisableHotSetting = computed(() => hotColdAttrSet.value.length < 2); // 标签数量不足，禁止开启冷热设置

    const scopeValueType = computed(() => formData.value.visible_config.visible_type !== 'multi_biz'); // 可见范围单选判断，禁用下拉框
    const isBizAttr = computed(() => formData.value.visible_config.visible_type === 'biz_attr');
    // 提交按钮是否禁用
    const isDisableClickSubmit = computed(() => {
      if (isDoris.value) {
        const { visible_type: visibleType } = formData.value.visible_config;
        return (
          (visibleType === 'multi_biz' && !visibleBkBiz.value.length) ||
          (visibleType === 'biz_attr' && !bkBizLabelsList.value.length)
        );
      }
      return connectResult.value !== 'success' || invalidHotSetting.value || isRulesCheckSubmit.value;
    });

    // 侧边栏需要对比的formData
    const watchFormData = computed(() => ({ formData: formData.value, basicFormData: basicFormData.value }));

    const { initSidebarFormData, handleCloseSidebar } = useSidebarDiff(watchFormData);
    const { virtualscrollSpaceList } = useSpaceSelector(visibleBkBiz);

    const handleShowSlider = () => {
      selectZIndex.value = overlayRegistry.nextZIndex();
    };

    // 来源变更：非 other 时清空来源名称
    const handleChangeSource = (val: string) => {
      if (val !== 'other') {
        formData.value.source_name = '';
      }
    };

    // 编辑：获取集群信息并回填
    const editDataSource = async () => {
      try {
        sliderLoading.value = true;
        let clusterData = props.clusterData;
        if (!isDoris.value) {
          const res = await ServicesInstance.source.info({
            params: {
              cluster_id: props.editClusterId,
              bk_biz_id: bkBizId.value,
            },
          });
          clusterData = res.data;
        }

        // 回填 basicFormData.value
        Object.assign(basicFormData.value, {
          cluster_name: clusterData.cluster_config.cluster_name,
          display_name: clusterData.cluster_config.display_name,
          source_type: clusterData.cluster_config.custom_option?.source_type || '',
          source_name:
            clusterData.cluster_config.custom_option?.source_type === 'other'
              ? clusterData.cluster_config.custom_option?.source_name
              : '',
          domain_name: clusterData.cluster_config.domain_name,
          port: clusterData.cluster_config.port,
          schema: clusterData.cluster_config.schema,
          auth_info: {
            username: clusterData.auth_info.username,
            password: clusterData.auth_info.password || '******',
          },
        });

        // 先回填业务属性标签，避免设置 visible_config 时 watch 触发清空数据
        // 确保 bizParentList 已经有值，如果没有则等待
        if (!bizParentList.value.length) {
          await getBizPropertyId();
        }
        const visibleConfig = clusterData.cluster_config.custom_option?.visible_config || {};
        bkBizLabelsList.value = Object.entries(visibleConfig.bk_biz_labels || {}).reduce((pre: any[], cur) => {
          const propertyName = bizParentList.value.find((item) => item.id === cur[0]);
          const obj = {
            name: propertyName?.name || cur[0], // 如果找不到名称，使用 ID 作为名称
            id: cur[0],
            values: (Array.isArray(cur[1]) ? cur[1] : []).map((item: string) => ({ id: item, name: item })),
          };
          pre.push(obj);
          return pre;
        }, []);
        cacheBkBizLabelsList.value = JSON.parse(JSON.stringify(bkBizLabelsList.value));

        // 回填多业务选择
        visibleList.value = [];
        cacheVisibleList.value = [];
        for (const val of visibleConfig.visible_bk_biz ?? []) {
          const target = mySpaceList.value.find((project) => project.bk_biz_id === String(val.bk_biz_id));
          if (target) {
            store.commit('patchMySpaceListItem', {
              bkBizId: String(val.bk_biz_id),
              patch: { is_use: val.is_use },
            });
            const targetObj = {
              id: String(val.bk_biz_id),
              name: target.space_full_code_name,
              is_use: val.is_use,
            };
            visibleList.value.push(targetObj);
            cacheVisibleList.value.push(targetObj);
          }
        }

        // 回填 formData.value（最后设置 visible_config，避免 watch 触发时数据还未准备好）
        Object.assign(formData.value, {
          enable_hot_warm: clusterData.cluster_config.enable_hot_warm,
          hot_attr_name: clusterData.cluster_config.custom_option?.hot_warm_config?.hot_attr_name || '',
          hot_attr_value: clusterData.cluster_config.custom_option?.hot_warm_config?.hot_attr_value || '',
          warm_attr_name: clusterData.cluster_config.custom_option?.hot_warm_config?.warm_attr_name || '',
          warm_attr_value: clusterData.cluster_config.custom_option?.hot_warm_config?.warm_attr_value || '',
          setup_config: clusterData.cluster_config.custom_option?.setup_config || {},
          admin: clusterData.cluster_config.custom_option?.admin || [],
          description: clusterData.cluster_config.custom_option?.description || '',
          enable_archive: clusterData.cluster_config.custom_option?.enable_archive,
          enable_assessment: clusterData.cluster_config.custom_option?.enable_assessment,
          // 合并 basicFormData.value 的基础属性
          cluster_name: basicFormData.value.cluster_name,
          display_name: basicFormData.value.display_name,
          source_type: basicFormData.value.source_type,
          source_name: basicFormData.value.source_name,
          domain_name: basicFormData.value.domain_name,
          port: basicFormData.value.port,
          schema: basicFormData.value.schema,
          auth_info: basicFormData.value.auth_info,
        });

        // 最后设置 visible_config，此时 bkBizLabelsList 和 cacheBkBizLabelsList 已经准备好
        formData.value.visible_config = visibleConfig;

        initSidebarFormData();

        // ES 编辑状态下直接进行连通性测试，通过后展开集群管理
        if (!isDoris.value) {
          setTimeout(() => {
            handleTestConnect();
          }, 0);
        }
      } catch (e) {
        console.warn(e);
      } finally {
        sliderLoading.value = false;
      }
    };

    // 连通性测试
    const handleTestConnect = async () => {
      try {
        if ((await validateForm.value?.validate()) !== true) return;
        const postData: any = {
          bk_biz_id: bkBizId.value,
          cluster_name: basicFormData.value.cluster_name,
          display_name: basicFormData.value.display_name,
          domain_name: basicFormData.value.domain_name,
          port: basicFormData.value.port,
          schema: basicFormData.value.schema,
          es_auth_info: {
            username: basicFormData.value.auth_info.username,
            password: basicFormData.value.auth_info.password,
          },
        };
        if (isEdit.value) {
          postData.cluster_id = props.editClusterId;
        }
        if (postData.es_auth_info.password === '******') {
          postData.es_auth_info.password = '';
        }

        connectLoading.value = true;
        await ServicesInstance.source.connectivityDetect({ data: postData }, { catchIsShowMessage: false });
        connectResult.value = 'success';

        // 连通性测试通过之后获取冷热数据
        const attrsRes = await ServicesInstance.source.getNodeAttrs({ data: postData });
        hotColdOriginList.value = attrsRes.data || [];

        // 新建时默认用节点数作为默认/最大分片数
        if (!isEdit.value) {
          formData.value.setup_config.es_shards_default = hotColdOriginList.value.length;
          formData.value.setup_config.es_shards_max = hotColdOriginList.value.length;
        }
      } catch (e: any) {
        console.warn(e);
        connectResult.value = 'failed';
        connectFailedMessage.value = e.message;
        hotColdOriginList.value = [];
      } finally {
        connectLoading.value = false;
        dealWithHotColdData();
      }
    };

    // 冷热开关变更：新建时开启将分片默认设为标签数
    const handleChangeHotWarm = (v: boolean) => {
      if (!isEdit.value && v) {
        formData.value.setup_config.es_shards_default = hotColdAttrSet.value.length;
        formData.value.setup_config.es_shards_max = hotColdAttrSet.value.length;
      }
    };

    // 处理冷热标签原始数据，汇总计数并恢复已选项
    const dealWithHotColdData = () => {
      const set: HotColdOption[] = [];
      for (const item of hotColdOriginList.value) {
        const newItem = { ...item } as HotColdOption;
        newItem.computedId = `${item.attr}:${item.value}`;
        newItem.computedName = `${item.attr}:${item.value}`;
        newItem.computedCounts = 1;
        newItem.isSelected = false;
        const exist = set.find((s) => s.computedId === newItem.computedId);
        if (exist) {
          exist.computedCounts += 1;
        } else {
          set.push(newItem);
        }
      }
      hotColdAttrSet.value = set;
      selectedHotId.value = formData.value.hot_attr_name
        ? `${formData.value.hot_attr_name}:${formData.value.hot_attr_value}`
        : '';
      selectedColdId.value = formData.value.warm_attr_name
        ? `${formData.value.warm_attr_name}:${formData.value.warm_attr_value}`
        : '';
      computeIsSelected();
    };

    // 选择热标签
    const handleHotSelected = (v: string) => {
      selectedHotId.value = v;
      const item = hotColdAttrSet.value.find((i) => i.computedId === v) || {};
      formData.value.hot_attr_name = (item as any).attr || '';
      formData.value.hot_attr_value = (item as any).value || '';
      computeIsSelected();
    };

    // 选择冷标签
    const handleColdSelected = (v: string) => {
      selectedColdId.value = v;
      const item = hotColdAttrSet.value.find((i) => i.computedId === v) || {};
      formData.value.warm_attr_name = (item as any).attr || '';
      formData.value.warm_attr_value = (item as any).value || '';
      computeIsSelected();
    };

    // 根据当前选择标记禁用态
    const computeIsSelected = () => {
      for (const item of hotColdAttrSet.value) {
        item.isSelected = selectedColdId.value === item.computedId || selectedHotId.value === item.computedId;
      }
    };

    // 查看实例列表弹窗
    const handleViewInstanceList = (type: 'cold' | 'hot') => {
      viewInstanceType.value = type;
      showInstanceDialog.value = true;
    };

    // 提交新增/提交编辑
    const handleConfirm = async () => {
      const isCanSubmit = checkSelectItem();
      if (!isCanSubmit) {
        return;
      }
      try {
        if (isDoris.value) {
          const visibleConfig: any = {
            visible_type: formData.value.visible_config.visible_type,
          };
          if (visibleConfig.visible_type === 'multi_biz') {
            visibleConfig.visible_bk_biz = visibleBkBiz.value.map((id) => Number(id));
          }
          if (visibleConfig.visible_type === 'biz_attr') {
            visibleConfig.bk_biz_labels = filterBzID();
          }

          confirmLoading.value = true;
          await ServicesInstance.source.updateVisibleConfig({
            params: { cluster_id: props.editClusterId },
            data: {
              bk_biz_id: Number(bkBizId.value),
              visible_config: visibleConfig,
              setup_config: {
                retention_days_max: Number(formData.value.setup_config.retention_days_max),
                retention_days_default: Number(formData.value.setup_config.retention_days_default),
              },
            },
          });
          TDesignMessage('success', { content: t('保存成功'), duration: 1500 });
          emit('handleUpdatedTable');
          return;
        }

        if ((await validateForm.value?.validate()) !== true) return;
        let url = ServicesInstance.source.create;
        const paramsData: any = { bk_biz_id: bkBizId.value };

        // 合并基础信息到完整表单中
        Object.assign(formData.value, basicFormData.value);
        const postData: any = JSON.parse(JSON.stringify(formData.value));
        postData.bk_biz_id = bkBizId.value;

        // 数字化 setup_config
        for (const key in postData.setup_config) {
          if (Object.hasOwn(postData.setup_config, key)) {
            postData.setup_config[key] = Number(postData.setup_config[key]);
          }
        }

        // 可见范围：多业务
        if (visibleBkBiz.value.length) {
          postData.visible_config.visible_bk_biz = visibleBkBiz.value;
        } else {
          postData.visible_config.visible_bk_biz = [];
        }

        // 可见范围：业务属性
        if (bkBizLabelsList.value.length) {
          postData.visible_config.bk_biz_labels = filterBzID();
        } else {
          postData.visible_config.bk_biz_labels = {};
        }

        // 编辑模式
        if (isEdit.value) {
          url = ServicesInstance.source.update;
          paramsData.cluster_id = props.editClusterId;
          if (postData.auth_info.password === '******') {
            postData.auth_info.password = '';
          }
        }

        let newPostData = JSON.parse(JSON.stringify(postData));
        // 冷热关闭时移除相关字段
        if (!postData.enable_hot_warm) {
          const {
            hot_attr_name: _hotAttrName,
            hot_attr_value: _hotAttrValue,
            warm_attr_name: _warmAttrName,
            warm_attr_value: _warmAttrValue,
            ...reset
          } = postData;
          newPostData = reset;
        }
        // 来源非 other 时移除自定义来源名
        if (postData.source_type !== 'other') {
          const { source_name: _sourceName, ...reset } = newPostData;
          newPostData = reset;
        }

        confirmLoading.value = true;
        await url({ data: newPostData, params: paramsData });
        TDesignMessage('success', { content: t('保存成功'), duration: 1500 });
        emit('handleUpdatedTable');
      } catch (e) {
        console.warn(e);
      } finally {
        confirmLoading.value = false;
      }
    };

    // 可见范围必填校验
    const checkSelectItem = () => {
      let messageType = '';
      const { visible_type: visibleType } = formData.value.visible_config;
      // visibleBkBiz
      if (visibleType === 'multi_biz' && !visibleBkBiz.value.length) {
        messageType = t('可见类型为多业务时，可见业务范围不能为空');
      }
      if (visibleType === 'biz_attr' && !bkBizLabelsList.value.length) {
        messageType = t('可见类型为业务属性时，业务标签不能为空');
      }
      if (messageType) {
        TDesignMessage('error', { content: messageType });
        return false;
      }
      return true;
    };

    // 过滤/去重 按照业务属性选择结果
    const filterBzID = () => {
      const parentSet = new Set<string>();
      const list: Record<string, string[]> = {};
      for (const item of bkBizLabelsList.value) {
        // 若当前元素父级未重复则生成新键名并赋值
        if (parentSet.has(item.id)) {
          // 若当前元素父级重复则去重过滤
          const valuesList = item.values.map((v: any) => v.id);
          const concatList = valuesList.concat(list[item.id]);
          const childSet = new Set<string>([...concatList]);
          list[item.id] = [...childSet];
        } else {
          parentSet.add(item.id);
          list[item.id] = [];
          const valuesList = item.values.map((v: any) => v.id);
          list[item.id] = list[item.id].concat(valuesList);
        }
      }
      return list;
    };

    // 关闭侧边栏
    let closePending = false;
    const handleCancel = async () => {
      if (closePending) return;
      closePending = true;
      try {
        if (await handleCloseSidebar()) emit('handleCancelSlider');
      } finally {
        closePending = false;
      }
    };

    // 更新“过期时间”选择列表（含默认禁用态）
    const updateDaysList = () => {
      const list = [...(globalsData.value.storage_duration_time || [])].filter((item: any) => item.id);
      retentionDaysList.value = list;
      maxDaysList.value = JSON.parse(JSON.stringify(list));
      daySelectAddToDisable();
    };

    // 更新过期时间列表里禁止选中的情况
    const daySelectAddToDisable = () => {
      const { retention_days_default: d, retention_days_max: m } = formData.value.setup_config;
      for (const el of retentionDaysList.value) {
        el.disabled = Number(m) < Number(el.id);
      }
      for (const el of maxDaysList.value) {
        el.disabled = Number(d) > Number(el.id);
      }
    };

    // 判断过期时间输入的值
    const enterCustomDay = (val: string, type: string) => {
      const numberVal = Number.parseInt(val.trim(), 10);
      const stringVal = numberVal.toString();
      const isRetention = type === 'retention';
      if (numberVal) {
        const isExceed = isRetention
          ? formData.value.setup_config.retention_days_max < numberVal
          : formData.value.setup_config.retention_days_default > numberVal;
        if (isExceed) {
          messageError(t('默认天数不能大于最大天数'));
          return;
        }
        if (isRetention) {
          if (!retentionDaysList.value.some((item) => item.id === stringVal)) {
            retentionDaysList.value.push({
              id: stringVal,
              name: stringVal + t('天'),
            });
          }
          formData.value.setup_config.retention_days_default = stringVal;
          customRetentionDay.value = '';
        } else {
          if (!maxDaysList.value.some((item) => item.id === stringVal)) {
            maxDaysList.value.push({
              id: stringVal,
              name: stringVal + t('天'),
            });
          }
          formData.value.setup_config.retention_days_max = stringVal;
          customMaxDay.value = '';
        }
        document.body.click();
      } else {
        isRetention ? (customRetentionDay.value = '') : (customMaxDay.value = '');
        messageError(t('请输入有效数值'));
      }
    };

    // 获取业务属性（父/子）列表
    const getBizPropertyId = async () => {
      // 因搜索框如果直接搜索子级元素则返回值不带父级元素 传参需要父级元素则分开展示
      try {
        const res = await ServicesInstance.source.getProperty();
        // 父级键名
        bizParentList.value = (res.data || []).map((item: any) => ({
          name: item.biz_property_name,
          id: item.biz_property_id,
          multiable: true,
          remote: true,
        }));
        // 生成子级数组
        for (const item of res.data || []) {
          bizChildrenList.value[item.biz_property_id] = (item.biz_property_value || []).map((v: any) => ({
            id: v,
            name: v,
          }));
        }
      } catch (e) {
        console.warn(e);
      }
    };

    const handleRemoteMethod = () =>
      new Promise((resolve) => {
        setTimeout(() => {
          // 空值返回全部，搜索返回部分
          if (bizInputStr.value) {
            resolve(
              (bizChildrenList.value[bizSelectID.value] || []).filter((i: { name: string | string[] }) =>
                i.name.includes(bizInputStr.value),
              ),
            );
          } else {
            resolve(bizChildrenList.value[bizSelectID.value] || []);
          }
        }, 1000);
      });

    const handleMenuSelect = (item: any) => {
      bizSelectID.value = item.id;
      bizInputStr.value = '';
    };

    const handleChildMenuSelect = () => {
      bizInputStr.value = '';
    };

    // 点击搜索框外：清理未确认的输入态
    const handleClickOutside = () => {
      // searchSelect组件若没有点击确认则清除输入框和选中的值
      if (!searchSelectRef.value?.input?.focus) {
        try {
          searchSelectRef.value.input.value = '';
          searchSelectRef.value.menu.active = -1;
          searchSelectRef.value.menu.id = null;
          searchSelectRef.value.updateInput();
          searchSelectRef.value.clearInput();
          searchSelectRef.value.menu.checked = {};
          if (searchSelectRef.value.menuChildInstance) {
            searchSelectRef.value.menuChildInstance.checked = {};
          }
          searchSelectRef.value.menuInstance = null;
        } catch (e) {
          console.log(e);
        }
      }
    };

    const handleInputChange = (e: any) => {
      bizInputStr.value = e?.data ?? '';
    };

    // 监听：侧滑显示/隐藏
    watch(
      () => props.showSlider,
      async (val) => {
        if (val) {
          // 先获取业务属性列表，确保在编辑模式下回填数据时 bizParentList 已经有值
          await getBizPropertyId();

          if (isEdit.value) {
            isShowManagement.value = true;
            editDataSource();
          } else {
            formData.value.admin = [userMeta.value.username];
            initSidebarFormData();
          }
          updateDaysList();
        } else {
          Object.assign(formData.value, {
            cluster_name: '',
            display_name: '',
            source_type: '',
            source_name: '',
            domain_name: '',
            port: '',
            schema: 'http',
            auth_info: { username: '', password: '' },
            enable_hot_warm: false,
            hot_attr_name: '',
            hot_attr_value: '',
            warm_attr_name: '',
            warm_attr_value: '',
            setup_config: {
              retention_days_max: 14,
              retention_days_default: 7,
              number_of_replicas_max: 3,
              number_of_replicas_default: 1,
              es_shards_default: 1,
              es_shards_max: 3,
            },
            admin: [],
            description: '',
            enable_archive: false,
            enable_assessment: false,
            visible_config: {
              visible_type: 'current_biz',
              visible_bk_biz: [],
              bk_biz_labels: {},
            },
          });
          Object.assign(basicFormData.value, {
            cluster_name: '',
            display_name: '',
            source_type: '',
            source_name: '',
            domain_name: '',
            port: '',
            schema: 'http',
            auth_info: { username: '', password: '' },
          });
          visibleBkBiz.value = [];
          visibleList.value = [];
          cacheVisibleList.value = [];
          bkBizLabelsList.value = [];
          cacheBkBizLabelsList.value = [];
          connectResult.value = '';
          connectFailedMessage.value = '';
          isShowManagement.value = false;
          isFirstShow.value = true;
        }
      },
    );

    // 监听：基础信息变更后清空联通结果（避免误用老结果）
    watch(
      () => basicFormData.value,
      () => {
        if (!isFirstShow.value) {
          connectResult.value = '';
        }
        isFirstShow.value = false;
      },
      { deep: true },
    );

    // 监听：默认时间变更
    watch(
      () => formData.value.setup_config.retention_days_default,
      () => daySelectAddToDisable(),
    );

    // 监听：最大时间变更
    watch(
      () => formData.value.setup_config.retention_days_max,
      () => daySelectAddToDisable(),
    );

    // 监听：可见范围类型切换
    watch(
      () => formData.value.visible_config.visible_type,
      (val) => {
        if (val !== 'multi_biz') {
          visibleList.value = [];
        } else {
          visibleList.value = JSON.parse(JSON.stringify(cacheVisibleList.value));
        }
        if (val !== 'biz_attr') {
          bkBizLabelsList.value = [];
        } else {
          bkBizLabelsList.value = JSON.parse(JSON.stringify(cacheBkBizLabelsList.value));
        }
      },
    );

    // 监听：多业务可见列表变化时，同步 ID 列表
    watch(
      () => visibleList.value,
      (val) => {
        visibleBkBiz.value = val.map((item: any) => item.id);
      },
      { deep: true },
    );

    const renderVisibleScope = () => (
      <TFormItem style='margin-top: 4px' label={t('可见范围')}>
        <TRadioGroup
          value={formData.value.visible_config.visible_type}
          onChange={(value) => {
            if (typeof value === 'string') ((v: string) => (formData.value.visible_config.visible_type = v))(value);
          }}
        >
          {visibleScopeOptions.value.map((item) => (
            <TRadio key={item.id} class='scope-radio' value={item.id}>
              {item.name}
            </TRadio>
          ))}
        </TRadioGroup>

        {/* 多空间选择 */}
        <bk-select
          v-show={!scopeValueType.value}
          display-key='space_full_code_name'
          id-key='bk_biz_id'
          list={mySpaceList.value}
          value={visibleBkBiz.value}
          virtual-scroll-render={virtualscrollSpaceList}
          display-tag
          enable-virtual-scroll
          multiple
          searchable
          onChange={(v: never[]) => {
            visibleBkBiz.value = v;
          }}
        ></bk-select>

        {/* 按照空间属性选择 */}
        {isBizAttr.value && (
          <bk-search-select
            ref={searchSelectRef}
            data={bizParentList.value}
            popover-zindex={selectZIndex.value}
            remote-method={handleRemoteMethod}
            show-condition={false}
            show-popover-tag-change={false}
            values={bkBizLabelsList.value}
            clearable
            onChange={(val: any[]) => {
              bkBizLabelsList.value = val;
            }}
            onInput-change={handleInputChange}
            onInput-click-outside={handleClickOutside}
            onMenu-child-select={handleChildMenuSelect}
            onMenu-select={handleMenuSelect}
          />
        )}
      </TFormItem>
    );

    const renderRetentionDays = () => (
      <TFormItem label={t('过期时间')} requiredMark>
        <div class='flex-space'>
          <div class='flex-space-item'>
            <div class='space-item-label'>{t('默认')}</div>
            <bk-select
              v-slots={{
                trigger: () => (
                  <div class='bk-select-name'>
                    {String(formData.value.setup_config.retention_days_default) + t('天')}
                  </div>
                ),
                extension: () => (
                  <div style='padding: 8px 0'>
                    <bk-input
                      placeholder={t('输入自定义天数，按 Enter 确认')}
                      show-controls={false}
                      size='small'
                      type='number'
                      value={customRetentionDay.value}
                      onChange={(val: string) => (customRetentionDay.value = val)}
                      onEnter={(val: string) => enterCustomDay(val, 'retention')}
                    />
                  </div>
                ),
              }}
              clearable={false}
              data-test-id='storageBox_select_selectExpiration'
              value={formData.value.setup_config.retention_days_default}
              onChange={(val: string) => (formData.value.setup_config.retention_days_default = val)}
            >
              {retentionDaysList.value.map((option, index) => (
                <bk-option id={option.id} key={index} disabled={option.disabled} name={option.name} />
              ))}
            </bk-select>
          </div>

          <div class='flex-space-item'>
            <div class='space-item-label'>{t('最大')}</div>
            <bk-select
              v-slots={{
                extension: () => (
                  <div style='padding: 8px 0'>
                    <bk-input
                      placeholder={t('输入自定义天数，按 Enter 确认')}
                      show-controls={false}
                      size='small'
                      type='number'
                      value={customMaxDay.value}
                      onChange={(val: string) => (customMaxDay.value = val)}
                      onEnter={(val: string) => enterCustomDay(val, 'max')}
                    />
                  </div>
                ),
                trigger: () => (
                  <div class='bk-select-name'>{String(formData.value.setup_config.retention_days_max) + t('天')}</div>
                ),
              }}
              clearable={false}
              data-test-id='storageBox_select_selectExpiration'
              value={formData.value.setup_config.retention_days_max}
              onChange={(val: string) => (formData.value.setup_config.retention_days_max = val)}
            >
              {maxDaysList.value.map((option, index) => (
                <bk-option id={option.id} key={index} disabled={option.disabled} name={option.name} />
              ))}
            </bk-select>
          </div>
        </div>
      </TFormItem>
    );

    const renderManagementToggle = () => (
      <TFormItem>
        <div
          class='es-cluster-management button-text'
          onClick={() => (isShowManagement.value = !isShowManagement.value)}
        >
          <span>{isDoris.value ? t('Doris集群管理') : t('ES集群管理')}</span>
          <span class={['bk-icon icon-angle-double-down', isShowManagement.value ? 'is-show' : ''].join(' ')} />
        </div>
      </TFormItem>
    );

    // 主渲染
    return () => (
      <div class='es-access-slider-container' data-test-id='addNewEsAccess_div_esAccessFromBox'>
        <TDrawer
          v-slots={{
            default: () => (
              <>
                <BklogLoading
                  class='es-king-slider-content'
                  data-testid='cluster-slider-loading'
                  loading={sliderLoading.value}
                >
                  {!sliderLoading.value && (
                    <TForm
                      ref={validateForm}
                      class='king-form'
                      labelAlign='top'
                      labelWidth={170}
                      {...{
                        ...{
                          data: basicFormData.value,
                          rules: basicRules.value,
                        },
                      }}
                    >
                      {/* 基础信息标题 */}
                      <div class='add-collection-title'>{t('基础信息')}</div>

                      {/* 集群名称 */}
                      <TFormItem label={t('集群名称')} name='display_name' requiredMark>
                        <TInput
                          data-test-id='esAccessFromBox_input_fillName'
                          maxlength={50}
                          readonly={isDoris.value}
                          value={basicFormData.value.display_name}
                          onChange={(val) => (basicFormData.value.display_name = String(val))}
                        />
                      </TFormItem>

                      {/* 集群英文名称 */}
                      <TFormItem label={t('集群英文名称')} name='cluster_name' requiredMark>
                        <TInput
                          maxlength={50}
                          readonly={isEdit.value}
                          placeholder={t('支持字母、数字、下划线、连字符')}
                          value={basicFormData.value.cluster_name}
                          onChange={(val) => (basicFormData.value.cluster_name = String(val))}
                        />
                      </TFormItem>

                      {/* 来源 + ES地址 */}
                      <div v-show={!isDoris.value} class='form-item-container'>
                        <TFormItem label={t('来源')} name='source_type' requiredMark>
                          <div class='source-item'>
                            <TSelect
                              popupProps={{ zIndex: selectZIndex.value + 1 }}
                              clearable
                              style='width: 154px; margin-right: 10px'
                              value={basicFormData.value.source_type}
                              onChange={(val) => {
                                basicFormData.value.source_type = String(val);
                                handleChangeSource(String(val));
                              }}
                            >
                              {(globalsData.value.es_source_type || []).map((option: any) => (
                                <TOption value={option.id} key={option.id} label={option.name} />
                              ))}
                            </TSelect>
                          </div>
                        </TFormItem>

                        <TFormItem class='es-address' label={t('ES地址')} name='domain_name' requiredMark>
                          <TInput
                            class='address-input'
                            data-test-id='esAccessFromBox_input_fillDomainName'
                            readonly={isEdit.value}
                            value={basicFormData.value.domain_name}
                            onChange={(val) => (basicFormData.value.domain_name = String(val))}
                          />
                        </TFormItem>
                      </div>

                      {isDoris.value && (
                        <div class='form-item-container'>
                          <TFormItem label={t('地址')} name='domain_name' requiredMark>
                            <TInput
                              data-test-id='esAccessFromBox_input_fillDomainName'
                              readonly
                              value={basicFormData.value.domain_name}
                            />
                          </TFormItem>

                          <TFormItem label={t('端口')} name='port' requiredMark>
                            <TInputNumber
                              data-test-id='esAccessFromBox_input_fillPort'
                              max={65_535}
                              min={0}
                              readonly
                              theme='normal'
                              value={basicFormData.value.port}
                            />
                          </TFormItem>
                        </div>
                      )}

                      {/* 端口 + 协议 */}
                      <div v-show={!isDoris.value} class='form-item-container'>
                        <TFormItem label={t('端口')} name='port' requiredMark>
                          <TInputNumber
                            data-test-id='esAccessFromBox_input_fillPort'
                            max={65_535}
                            min={0}
                            readonly={isEdit.value}
                            theme='normal'
                            value={basicFormData.value.port}
                            onChange={(val: number | string) => (basicFormData.value.port = String(val))}
                          />
                        </TFormItem>

                        <TFormItem label={t('协议')} requiredMark>
                          <TSelect
                            popupProps={{ zIndex: selectZIndex.value + 1 }}
                            clearable={false}
                            data-test-id='esAccessFromBox_select_selectProtocol'
                            value={basicFormData.value.schema}
                            onChange={(val) => (basicFormData.value.schema = String(val))}
                          >
                            <TOption value='http' label='http' />
                            <TOption value='https' label='https' />
                          </TSelect>
                        </TFormItem>
                      </div>

                      {/* 用户名 + 密码 */}
                      <div class='form-item-container'>
                        <TFormItem label={t('用户名')}>
                          <TInput
                            data-test-id='esAccessFromBox_input_fillUsername'
                            readonly={isDoris.value}
                            value={basicFormData.value.auth_info.username}
                            onChange={(val) => (basicFormData.value.auth_info.username = String(val))}
                          />
                        </TFormItem>
                        <TFormItem v-show={!isDoris.value} label={t('密码')}>
                          <TInput
                            data-test-id='esAccessFromBox_input_fillPassword'
                            type='password'
                            value={basicFormData.value.auth_info.password}
                            onChange={(val) => (basicFormData.value.auth_info.password = String(val))}
                          />
                        </TFormItem>
                      </div>

                      {/* 连通性测试 */}
                      {!isDoris.value && (
                        <TFormItem label=''>
                          <div class='test-container'>
                            <TButton
                              data-test-id='esAccessFromBox_button_connectivityTest'
                              loading={connectLoading.value}
                              theme='primary'
                              type='button'
                              onClick={handleTestConnect}
                            >
                              {t('连通性测试')}
                            </TButton>
                            {connectResult.value === 'success' && (
                              <div class='success-text'>
                                <i class='bk-icon icon-check-circle-shape' />
                                {t('连通成功！')}
                              </div>
                            )}
                            {connectResult.value === 'failed' && (
                              <div class='error-text'>
                                <i class='bk-icon icon-close-circle-shape' />
                                {t('连通失败！')}
                              </div>
                            )}
                          </div>
                        </TFormItem>
                      )}

                      {/* 连通失败信息 */}
                      {!isDoris.value && connectResult.value === 'failed' && !!connectFailedMessage.value && (
                        <TFormItem label=''>
                          <div class='connect-message'>{connectFailedMessage.value}</div>
                        </TFormItem>
                      )}

                      {/* Doris 集群管理不依赖连通性状态；ES 仍需连通成功后展示 */}
                      {isDoris.value && renderManagementToggle()}
                      {!isDoris.value && connectResult.value === 'success' && renderManagementToggle()}

                      {isDoris.value && isShowManagement.value && (
                        <div>
                          {renderVisibleScope()}
                          {renderRetentionDays()}
                        </div>
                      )}
                      {/* 管理区块 */}
                      {!isDoris.value && isShowManagement.value && connectResult.value === 'success' && (
                        <div>
                          {renderVisibleScope()}

                          {/* 过期时间 */}
                          {renderRetentionDays()}

                          {/* 副本数 */}
                          <TFormItem label={t('副本数')} requiredMark>
                            <div class='flex-space'>
                              <div class='flex-space-item'>
                                <div class='space-item-label'>{t('默认')}</div>
                                <bk-input
                                  max={Number(formData.value.setup_config.number_of_replicas_max)}
                                  min={0}
                                  type='number'
                                  value={formData.value.setup_config.number_of_replicas_default}
                                  onChange={(val: number | string) =>
                                    (formData.value.setup_config.number_of_replicas_default = Number(val))
                                  }
                                />
                              </div>
                              <div class='flex-space-item'>
                                <div class='space-item-label'>{t('最大')}</div>
                                <bk-input
                                  min={Number(formData.value.setup_config.number_of_replicas_default)}
                                  type='number'
                                  value={formData.value.setup_config.number_of_replicas_max}
                                  onChange={(val: number | string) =>
                                    (formData.value.setup_config.number_of_replicas_max = Number(val))
                                  }
                                />
                              </div>
                            </div>
                          </TFormItem>

                          {/* 分片数 */}
                          <TFormItem label={t('分片数')} requiredMark>
                            <div class='flex-space'>
                              <div class='flex-space-item'>
                                <div class='space-item-label'>{t('默认')}</div>
                                <bk-input
                                  max={Number(formData.value.setup_config.es_shards_max)}
                                  min={1}
                                  type='number'
                                  value={formData.value.setup_config.es_shards_default}
                                  onChange={(val: number | string) =>
                                    (formData.value.setup_config.es_shards_default = Number(val))
                                  }
                                />
                              </div>
                              <div class='flex-space-item'>
                                <div class='space-item-label'>{t('最大')}</div>
                                <bk-input
                                  min={Number(formData.value.setup_config.es_shards_default)}
                                  type='number'
                                  value={formData.value.setup_config.es_shards_max}
                                  onChange={(val: number | string) =>
                                    (formData.value.setup_config.es_shards_max = Number(val))
                                  }
                                />
                              </div>
                            </div>
                          </TFormItem>

                          {/* 冷热数据 */}
                          <TFormItem v-show={connectResult.value === 'success'} label={t('冷热数据')}>
                            <div class='form-flex-container'>
                              <TSwitch
                                disabled={isDisableHotSetting.value}
                                size='large'
                                value={formData.value.enable_hot_warm}
                                onChange={(value) => {
                                  if (typeof value === 'boolean')
                                    ((val: boolean) => {
                                      formData.value.enable_hot_warm = val;
                                      handleChangeHotWarm(val);
                                    })(value);
                                }}
                              />
                              {isDisableHotSetting.value &&
                                !connectLoading.value && [
                                  <span key='icon-info' class='bk-icon icon-info' />,
                                  <span key='left-text' style='font-size: 12px'>
                                    {t('没有获取到正确的标签，')}
                                  </span>,
                                  <a key='button-text' class='button-text' href={configDocUrl.value} target='_blank'>
                                    {t('查看具体的配置方法')}
                                  </a>,
                                ]}
                            </div>
                          </TFormItem>

                          {/* 冷热数据标签 */}
                          {formData.value.enable_hot_warm && (
                            <div class='form-item-container'>
                              {/* 热数据标签 */}
                              <div class='bk-form-item'>
                                <div class='form-item-label'>
                                  <p>{t('热数据标签')}</p>
                                  {formData.value.hot_attr_name && formData.value.hot_attr_value && (
                                    <div class='button-text' onClick={() => handleViewInstanceList('hot')}>
                                      <span class='bk-icon icon-eye' />
                                      {t('查看实例列表')}
                                    </div>
                                  )}
                                </div>
                                <bk-select value={selectedHotId.value} onChange={(v: string) => handleHotSelected(v)}>
                                  {hotColdAttrSet.value.map((option) => (
                                    <bk-option
                                      id={option.computedId}
                                      key={option.computedId}
                                      disabled={option.isSelected}
                                      name={`${option.computedName}(${option.computedCounts})`}
                                    />
                                  ))}
                                </bk-select>
                              </div>

                              {/* 冷数据标签 */}
                              <div class='bk-form-item'>
                                <div class='form-item-label'>
                                  <p>{t('冷数据标签')}</p>
                                  {formData.value.warm_attr_name && formData.value.warm_attr_value && (
                                    <div class='button-text' onClick={() => handleViewInstanceList('cold')}>
                                      <span class='bk-icon icon-eye' />
                                      {t('查看实例列表')}
                                    </div>
                                  )}
                                </div>
                                <bk-select value={selectedColdId.value} onChange={(v: string) => handleColdSelected(v)}>
                                  {hotColdAttrSet.value.map((option) => (
                                    <bk-option
                                      id={option.computedId}
                                      key={option.computedId}
                                      disabled={option.isSelected}
                                      name={`${option.computedName}(${option.computedCounts})`}
                                    />
                                  ))}
                                </bk-select>
                              </div>
                            </div>
                          )}

                          {/* 日志归档 / 容量评估 */}
                          <div class='form-item-container'>
                            <TFormItem label={t('日志归档')}>
                              <div class='document-container'>
                                <TSwitch
                                  size='large'
                                  value={formData.value.enable_archive}
                                  onChange={(value) => {
                                    if (typeof value === 'boolean')
                                      ((v: boolean) => (formData.value.enable_archive = v))(value);
                                  }}
                                />
                                {!!archiveDocUrl.value && (
                                  <div
                                    class='check-document button-text'
                                    onClick={() => ManageHelper.handleGotoLink('logArchive')}
                                  >
                                    <span class='bk-icon icon-text-file' />
                                    <a>{t('查看说明文档')}</a>
                                  </div>
                                )}
                              </div>
                            </TFormItem>
                            {isItsm.value && (
                              <TFormItem label={t('容量评估')}>
                                <TSwitch
                                  size='large'
                                  value={formData.value.enable_assessment}
                                  onChange={(value) => {
                                    if (typeof value === 'boolean')
                                      ((v: boolean) => (formData.value.enable_assessment = v))(value);
                                  }}
                                />
                              </TFormItem>
                            )}
                          </div>

                          {/* 集群负责人 */}
                          <TFormItem help={t('集群负责人可以用于容量审核等')} label={t('集群负责人')} requiredMark>
                            <div class='principal'>
                              <ValidateUserSelector
                                placeholder={t('请选择集群负责人')}
                                value={formData.value.admin}
                                onChange={(val: string[]) => (formData.value.admin = val)}
                              />
                            </div>
                          </TFormItem>

                          {/* 集群说明 */}
                          <TFormItem class='illustrate' label={t('说明')}>
                            <bk-input
                              maxlength={100}
                              rows={3}
                              type='textarea'
                              value={formData.value.description}
                              onChange={(val: string) => (formData.value.description = val)}
                            />
                          </TFormItem>
                        </div>
                      )}
                    </TForm>
                  )}

                  {/* 底部提交按钮 */}
                  <div class='submit-container'>
                    <TButton
                      class='king-button mr10'
                      data-test-id='esAccessFromBox_button_confirm'
                      disabled={isDisableClickSubmit.value}
                      loading={confirmLoading.value}
                      theme='primary'
                      onClick={handleConfirm}
                    >
                      {t('提交')}
                    </TButton>
                    <TButton
                      theme='default'
                      variant='outline'
                      data-test-id='esAccessFromBox_button_cancel'
                      onClick={handleCancel}
                    >
                      {t('取消')}
                    </TButton>
                  </div>
                </BklogLoading>
              </>
            ),
          }}
          drawerClassName='bklog-cluster-drawer'
          size='640px'
          visible={props.showSlider}
          header={isEdit.value ? t('编辑集群') : t('新建集群')}
          footer={false}
          attach='body'
          closeOnEscKeydown
          closeOnOverlayClick
          zIndex={selectZIndex.value}
          onClose={handleCancel}
          onBeforeOpen={handleShowSlider}
        ></TDrawer>

        {/* 查看实例列表弹窗 */}
        <EsDialog
          formData={formData.value}
          list={hotColdOriginList.value}
          type={viewInstanceType.value}
          value={showInstanceDialog.value}
          onHandleValueChange={(val: boolean) => (showInstanceDialog.value = val)}
        />
      </div>
    );
  },
});
