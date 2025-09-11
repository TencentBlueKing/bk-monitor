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

import { messageError } from '@/common/bkmagic';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import BkUserSelector from '@blueking/user-selector';
import { Message } from 'bk-magic-vue';

import { useSidebarDiff } from '../../hooks/use-sidebar-diff';
import { useSpaceSelector } from '../../hooks/use-space-selector';
import ManageHelper from '../../manage-helper.ts';
import EsDialog from './es-dialog.tsx';
import http from '@/api';

import './es-slider.scss';

export default defineComponent({
  name: 'EsSlider',
  components: {
    EsDialog,
    BkUserSelector,
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
    onHandleCancelSlider: { type: Function },
    onHandleUpdatedTable: { type: Function },
  },
  emits: ['handleCancelSlider', 'handleUpdatedTable'],
  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale();

    // 表单与组件引用
    const validateForm = ref<any>(null);
    const searchSelectRef = ref<any>(null);

    const configDocUrl = ref((window as any).BK_HOT_WARM_CONFIG_URL);
    const archiveDocUrl = ref((window as any).BK_ARCHIVE_DOC_URL); // 日志归档跳转链接
    const isItsm = ref((window as any).FEATURE_TOGGLE.collect_itsm === 'on'); // 容量评估全局参数

    const confirmLoading = ref(false); // 确认按钮加载状态
    const sliderLoading = ref(false); // 侧边栏加载状态

    // 连通性测试表单
    const formData = ref<any>({
      cluster_name: '', // 集群名称
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
      cluster_name: '', // 集群名
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
      cluster_name: [{ required: true, trigger: 'blur' }],
      domain_name: [{ required: true, trigger: 'blur' }],
      port: [{ required: true, trigger: 'blur' }],
    });

    const connectLoading = ref(false); // 连通性测试按钮加载状态
    const connectResult = ref(''); // 连通性测试结果
    const connectFailedMessage = ref(''); // 连通性测试失败信息

    const hotColdOriginList = ref([]); // 新增编辑时的冷热数据
    const hotColdAttrSet = ref([]); // 相同 attr value 的集合
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
    const visibleBkBiz = ref([]); // 下拉框选中的值列表
    const visibleList = ref([]); // 多业务选择下拉框
    const cacheVisibleList = ref([]); // 缓存多业务选择下拉框
    const bkBizLabelsList = ref([]); // 按照业务属性选择列表
    const cacheBkBizLabelsList = ref([]); // 缓存按照业务属性选择
    const bizParentList = ref([]); // 按照业务属性父级列表
    const bizChildrenList = ref({}); // 业务属性选择子级键值对象
    const userApi = ref((window as any).BK_LOGIN_URL); // 负责人api
    const isShowManagement = ref(false); // 是否展示集群管理
    const retentionDaysList = ref([]); // 默认过期时间列表
    const maxDaysList = ref([]); // 最大过期时间列表
    const customRetentionDay = ref(''); // 默认过期时间输入框
    const customMaxDay = ref(''); // 最大过期时间输入框
    const isAdminError = ref(false); // 集群负责人是否为空
    const bizSelectID = ref(''); // 选中的当前按照业务属性选择
    const bizInputStr = ref(''); // 按照业务属性选择输入值
    const isFirstShow = ref(true); // 是否是第一次渲染
    const selectZIndex = ref(3007);

    const mySpaceList = computed(() => store.state.mySpaceList);
    const userMeta = computed(() => store.state.userMeta);
    const bkBizId = computed(() => store.getters.bkBizId);
    const globalsData = computed(() => store.getters['globals/globalsData']);
    const isEdit = computed(() => props.editClusterId !== null);

    // 冷热设置不对，禁用提交
    const invalidHotSetting = computed(() => {
      return formData.value.enable_hot_warm && !(formData.value.hot_attr_name && formData.value.warm_attr_value);
    });

    const isRulesCheckSubmit = computed(() => !formData.value.admin.length);
    const isDisableHotSetting = computed(() => hotColdAttrSet.value.length < 2); // 标签数量不足，禁止开启冷热设置

    const scopeValueType = computed(() => formData.value.visible_config.visible_type !== 'multi_biz'); // 可见范围单选判断，禁用下拉框
    const isBizAttr = computed(() => formData.value.visible_config.visible_type === 'biz_attr');
    // 提交按钮是否禁用
    const isDisableClickSubmit = computed(
      () => connectResult.value !== 'success' || invalidHotSetting.value || isRulesCheckSubmit.value,
    );

    // 侧边栏需要对比的formData
    const watchFormData = computed(() => ({ formData: formData.value, basicFormData: basicFormData.value }));

    const { initSidebarFormData, handleCloseSidebar } = useSidebarDiff(watchFormData.value);
    const { virtualscrollSpaceList } = useSpaceSelector(visibleBkBiz);

    const handleShowSlider = () => {
      selectZIndex.value = (window as any).__bk_zIndex_manager.nextZIndex();
    };

    // 来源变更：非 other 时清空来源名称
    const handleChangeSource = (val: string) => {
      if (val !== 'other') formData.value.source_name = '';
    };

    // 编辑：获取集群信息并回填
    const editDataSource = async () => {
      try {
        sliderLoading.value = true;
        const res = await http.request('/source/info', {
          params: {
            cluster_id: props.editClusterId,
            bk_biz_id: bkBizId.value,
          },
        });

        // 回填 basicFormData.value
        Object.assign(basicFormData.value, {
          cluster_name: res.data.cluster_config.cluster_name,
          source_type: res.data.cluster_config.custom_option?.source_type || '',
          source_name:
            res.data.cluster_config.custom_option?.source_type === 'other'
              ? res.data.cluster_config.custom_option?.source_name
              : '',
          domain_name: res.data.cluster_config.domain_name,
          port: res.data.cluster_config.port,
          schema: res.data.cluster_config.schema,
          auth_info: {
            username: res.data.auth_info.username,
            password: res.data.auth_info.password || '******',
          },
        });

        // 回填 formData.value
        Object.assign(formData.value, {
          enable_hot_warm: res.data.cluster_config.enable_hot_warm,
          hot_attr_name: res.data.cluster_config.custom_option?.hot_warm_config?.hot_attr_name || '',
          hot_attr_value: res.data.cluster_config.custom_option?.hot_warm_config?.hot_attr_value || '',
          warm_attr_name: res.data.cluster_config.custom_option?.hot_warm_config?.warm_attr_name || '',
          warm_attr_value: res.data.cluster_config.custom_option?.hot_warm_config?.warm_attr_value || '',
          setup_config: res.data.cluster_config.custom_option?.setup_config || {},
          admin: res.data.cluster_config.custom_option?.admin || [],
          description: res.data.cluster_config.custom_option?.description || '',
          enable_archive: res.data.cluster_config.custom_option?.enable_archive || false,
          enable_assessment: res.data.cluster_config.custom_option?.enable_assessment || false,
          visible_config: res.data.cluster_config.custom_option?.visible_config || {},
          // 合并 basicFormData.value 的基础属性
          cluster_name: basicFormData.value.cluster_name,
          source_type: basicFormData.value.source_type,
          source_name: basicFormData.value.source_name,
          domain_name: basicFormData.value.domain_name,
          port: basicFormData.value.port,
          schema: basicFormData.value.schema,
          auth_info: basicFormData.value.auth_info,
        });

        initSidebarFormData();

        // 回填多业务选择
        visibleList.value = [];
        cacheVisibleList.value = [];
        (res.data.cluster_config.custom_option.visible_config?.visible_bk_biz ?? []).forEach(val => {
          const target = mySpaceList.value.find(project => project.bk_biz_id === String(val.bk_biz_id));
          if (target) {
            target.is_use = val.is_use;
            const targetObj = {
              id: String(val.bk_biz_id),
              name: target.space_full_code_name,
              is_use: val.is_use,
            };
            visibleList.value.push(targetObj);
            cacheVisibleList.value.push(targetObj);
          }
        });

        // 回填业务属性标签
        bkBizLabelsList.value = Object.entries(
          res.data.cluster_config.custom_option.visible_config?.bk_biz_labels || {},
        ).reduce((pre: any[], cur) => {
          const propertyName = bizParentList.value.find(item => item.id === cur[0]);
          const obj = {
            name: `${propertyName?.name}`,
            id: cur[0],
            values: (Array.isArray(cur[1]) ? cur[1] : []).map((item: string) => ({ id: item, name: item })),
          };
          pre.push(obj);
          return pre;
        }, []);
        cacheBkBizLabelsList.value = JSON.parse(JSON.stringify(bkBizLabelsList.value));

        // 若为编辑状态，则打开侧边栏后直接联通测试，通过则展开ES集群管理
        setTimeout(() => {
          handleTestConnect();
        }, 0);
      } catch (e) {
        console.warn(e);
      } finally {
        sliderLoading.value = false;
      }
    };

    // 连通性测试
    const handleTestConnect = async () => {
      try {
        await validateForm.value.validate();
        const postData: any = {
          bk_biz_id: bkBizId.value,
          cluster_name: basicFormData.value.cluster_name,
          domain_name: basicFormData.value.domain_name,
          port: basicFormData.value.port,
          schema: basicFormData.value.schema,
          es_auth_info: {
            username: basicFormData.value.auth_info.username,
            password: basicFormData.value.auth_info.password,
          },
        };
        if (isEdit.value) postData.cluster_id = props.editClusterId;
        if (postData.es_auth_info.password === '******') postData.es_auth_info.password = '';

        connectLoading.value = true;
        await http.request('/source/connectivityDetect', { data: postData }, { catchIsShowMessage: false });
        connectResult.value = 'success';

        // 连通性测试通过之后获取冷热数据
        const attrsRes = await http.request('/source/getNodeAttrs', { data: postData });
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
      const set: any[] = [];
      hotColdOriginList.value.forEach(item => {
        const newItem = { ...item };
        newItem.computedId = `${item.attr}:${item.value}`;
        newItem.computedName = `${item.attr}:${item.value}`;
        newItem.computedCounts = 1;
        newItem.isSelected = false;
        const exist = set.find(s => s.computedId === newItem.computedId);
        if (exist) exist.computedCounts += 1;
        else set.push(newItem);
      });
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
      const item = hotColdAttrSet.value.find(i => i.computedId === v) || {};
      formData.value.hot_attr_name = (item as any).attr || '';
      formData.value.hot_attr_value = (item as any).value || '';
      computeIsSelected();
    };

    // 选择冷标签
    const handleColdSelected = (v: string) => {
      selectedColdId.value = v;
      const item = hotColdAttrSet.value.find(i => i.computedId === v) || {};
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
      if (!isCanSubmit) return;
      try {
        await validateForm.value?.validate();
        let url = '/source/create';
        const paramsData: any = { bk_biz_id: bkBizId.value };

        // 合并基础信息到完整表单中
        Object.assign(formData.value, basicFormData.value);
        const postData: any = JSON.parse(JSON.stringify(formData.value));
        postData.bk_biz_id = bkBizId.value;

        // 冷热关闭时移除相关字段
        if (!postData.enable_hot_warm) {
          delete postData.hot_attr_name;
          delete postData.hot_attr_value;
          delete postData.warm_attr_name;
          delete postData.warm_attr_value;
        }

        // 数字化 setup_config
        for (const key in postData.setup_config) {
          postData.setup_config[key] = Number(postData.setup_config[key]);
        }

        // 来源非 other 时移除自定义来源名
        if (postData.source_type !== 'other') delete postData.source_name;

        // 可见范围：多业务
        if (visibleList.value.length) {
          postData.visible_config.visible_bk_biz = visibleList.value.map(item => item.id);
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
          url = '/source/update';
          paramsData.cluster_id = props.editClusterId;
          if (postData.auth_info.password === '******') postData.auth_info.password = '';
        }

        confirmLoading.value = true;
        await http.request(url, { data: postData, params: paramsData });
        Message({ theme: 'success', message: t('保存成功'), delay: 1500 });
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
      if (visibleType === 'multi_biz' && !visibleList.value.length) {
        messageType = t('可见类型为多业务时，可见业务范围不能为空');
      }
      if (visibleType === 'biz_attr' && !bkBizLabelsList.value.length) {
        messageType = t('可见类型为业务属性时，业务标签不能为空');
      }
      if (!!messageType) {
        Message({ theme: 'error', message: messageType });
        return false;
      }
      return true;
    };

    // 过滤/去重 按照业务属性选择结果
    const filterBzID = () => {
      const parentSet = new Set<string>();
      const list: Record<string, string[]> = {};
      bkBizLabelsList.value.forEach((item: any) => {
        // 若当前元素父级未重复则生成新键名并赋值
        if (!parentSet.has(item.id)) {
          parentSet.add(item.id);
          list[item.id] = [];
          const valuesList = item.values.map((v: any) => v.id);
          list[item.id] = list[item.id].concat(valuesList);
        } else {
          // 若当前元素父级重复则去重过滤
          const valuesList = item.values.map((v: any) => v.id);
          const concatList = valuesList.concat(list[item.id]);
          const childSet = new Set<string>([...concatList]);
          list[item.id] = [...childSet];
        }
      });
      return list;
    };

    // 关闭侧边栏
    const handleCancel = async () => {
      const canClose = await handleCloseSidebar();
      if (canClose) {
        emit('handleCancelSlider');
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
      retentionDaysList.value.forEach(el => (el.disabled = Number(m) < Number(el.id)));
      maxDaysList.value.forEach(el => (el.disabled = Number(d) > Number(el.id)));
    };

    // 判断过期时间输入的值
    const enterCustomDay = (val, type) => {
      const numberVal = parseInt(val.trim(), 10);
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
          if (!retentionDaysList.value.some(item => item.id === stringVal)) {
            retentionDaysList.value.push({
              id: stringVal,
              name: stringVal + t('天'),
            });
          }
          formData.value.setup_config.retention_days_default = stringVal;
          customRetentionDay.value = '';
        } else {
          if (!maxDaysList.value.some(item => item.id === stringVal)) {
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

    // 集群负责人为空时报错警告
    const handleChangePrincipal = (val: any[]) => {
      const realVal = val.filter(item => item !== undefined);
      isAdminError.value = !realVal.length;
      formData.value.admin = realVal;
    };
    const handleBlur = () => {
      isAdminError.value = !formData.value.admin.length;
    };

    // 获取业务属性（父/子）列表
    const getBizPropertyId = async () => {
      // 因搜索框如果直接搜索子级元素则返回值不带父级元素 传参需要父级元素则分开展示
      try {
        const res = await http.request('/source/getProperty');
        // 父级键名
        bizParentList.value = (res.data || []).map((item: any) => ({
          name: item.biz_property_name,
          id: item.biz_property_id,
          multiable: true,
          remote: true,
        }));
        // 生成子级数组
        (res.data || []).forEach((item: any) => {
          bizChildrenList.value[item.biz_property_id] = (item.biz_property_value || []).map((v: any) => ({
            id: v,
            name: v,
          }));
        });
      } catch (e) {
        console.warn(e);
      }
    };

    const handleRemoteMethod = () =>
      new Promise(resolve => {
        setTimeout(() => {
          // 空值返回全部，搜索返回部分
          if (!!bizInputStr.value) {
            resolve((bizChildrenList.value[bizSelectID.value] || []).filter(i => i.name.includes(bizInputStr.value)));
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
          if (searchSelectRef.value.menuChildInstance) searchSelectRef.value.menuChildInstance.checked = {};
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
      val => {
        if (val) {
          if (isEdit.value) {
            isShowManagement.value = true;
            editDataSource();
          } else {
            formData.value.admin = [userMeta.value.username];
            initSidebarFormData();
          }
          updateDaysList();
          getBizPropertyId();
        } else {
          Object.assign(formData.value, {
            cluster_name: '',
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
        if (!isFirstShow.value) connectResult.value = '';
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
      val => {
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
      val => {
        visibleBkBiz.value = val.map((item: any) => item.id);
      },
      { deep: true },
    );

    // 主渲染
    return () => (
      <div
        class='es-access-slider-container'
        data-test-id='addNewEsAccess_div_esAccessFromBox'
      >
        <bk-sideslider
          width={640}
          before-close={handleCloseSidebar}
          is-show={props.showSlider}
          quick-close={true}
          title={isEdit.value ? t('编辑集群') : t('新建集群')}
          transfer
          onAnimation-end={() => emit('handleCancelSlider')}
          onShown={handleShowSlider}
        >
          <template slot='content'>
            <div
              class='es-king-slider-content'
              v-bkloading={{ isLoading: sliderLoading.value }}
            >
              {!sliderLoading.value && (
                <bk-form
                  ref={validateForm}
                  class='king-form'
                  form-type='vertical'
                  label-width={170}
                  {...{
                    props: {
                      model: basicFormData.value,
                      rules: basicRules.value,
                    },
                  }}
                >
                  {/* 基础信息标题 */}
                  <div class='add-collection-title'>{t('基础信息')}</div>

                  {/* 数据源名称 */}
                  <bk-form-item
                    label={t('数据源名称')}
                    property='cluster_name'
                    required
                  >
                    <bk-input
                      data-test-id='esAccessFromBox_input_fillName'
                      maxlength={50}
                      readonly={isEdit.value}
                      value={basicFormData.value.cluster_name}
                      onChange={(val: string) => (basicFormData.value.cluster_name = val)}
                    />
                  </bk-form-item>

                  {/* 来源 + ES地址 */}
                  <div class='form-item-container'>
                    <bk-form-item
                      label={t('来源')}
                      property='source_type'
                      required
                    >
                      <div class='source-item'>
                        <bk-select
                          style='width: 154px; margin-right: 10px'
                          value={basicFormData.value.source_type}
                          onChange={(val: string) => {
                            basicFormData.value.source_type = val;
                            handleChangeSource(val);
                          }}
                        >
                          {(globalsData.value.es_source_type || []).map((option: any) => (
                            <bk-option
                              id={option.id}
                              key={option.id}
                              name={option.name}
                            />
                          ))}
                        </bk-select>
                      </div>
                    </bk-form-item>

                    <bk-form-item
                      class='es-address'
                      label={t('ES地址')}
                      property='domain_name'
                      required
                    >
                      <bk-input
                        class='address-input'
                        data-test-id='esAccessFromBox_input_fillDomainName'
                        readonly={isEdit.value}
                        value={basicFormData.value.domain_name}
                        onChange={(val: string) => (basicFormData.value.domain_name = val)}
                      />
                    </bk-form-item>
                  </div>

                  {/* 端口 + 协议 */}
                  <div class='form-item-container'>
                    <bk-form-item
                      label={t('端口')}
                      property='port'
                      required
                    >
                      <bk-input
                        data-test-id='esAccessFromBox_input_fillPort'
                        max={65535}
                        min={0}
                        readonly={isEdit.value}
                        show-controls={false}
                        type='number'
                        value={basicFormData.value.port}
                        onChange={(val: number | string) => (basicFormData.value.port = String(val))}
                      />
                    </bk-form-item>

                    <bk-form-item
                      label={t('协议')}
                      required
                    >
                      <bk-select
                        clearable={false}
                        data-test-id='esAccessFromBox_select_selectProtocol'
                        value={basicFormData.value.schema}
                        onChange={(val: string) => (basicFormData.value.schema = val)}
                      >
                        <bk-option
                          id='http'
                          name='http'
                        />
                        <bk-option
                          id='https'
                          name='https'
                        />
                      </bk-select>
                    </bk-form-item>
                  </div>

                  {/* 用户名 + 密码 */}
                  <div class='form-item-container'>
                    <bk-form-item label={t('用户名')}>
                      <bk-input
                        data-test-id='esAccessFromBox_input_fillUsername'
                        value={basicFormData.value.auth_info.username}
                        onChange={(val: string) => (basicFormData.value.auth_info.username = val)}
                      />
                    </bk-form-item>
                    <bk-form-item label={t('密码')}>
                      <bk-input
                        data-test-id='esAccessFromBox_input_fillPassword'
                        type='password'
                        value={basicFormData.value.auth_info.password}
                        onChange={(val: string) => (basicFormData.value.auth_info.password = val)}
                      />
                    </bk-form-item>
                  </div>

                  {/* 连通性测试 */}
                  <bk-form-item label=''>
                    <div class='test-container'>
                      <bk-button
                        data-test-id='esAccessFromBox_button_connectivityTest'
                        loading={connectLoading.value}
                        theme='primary'
                        type='button'
                        onClick={handleTestConnect}
                      >
                        {t('连通性测试')}
                      </bk-button>
                      {connectResult.value === 'success' && (
                        <div class='success-text'>
                          <i class='bk-icon icon-check-circle-shape'></i>
                          {t('连通成功！')}
                        </div>
                      )}
                      {connectResult.value === 'failed' && (
                        <div class='error-text'>
                          <i class='bk-icon icon-close-circle-shape'></i>
                          {t('连通失败！')}
                        </div>
                      )}
                    </div>
                  </bk-form-item>

                  {/* 连通失败信息 */}
                  {connectResult.value === 'failed' && !!connectFailedMessage.value && (
                    <bk-form-item label=''>
                      <div class='connect-message'>{connectFailedMessage.value}</div>
                    </bk-form-item>
                  )}

                  {/* ES 集群管理折叠条 */}
                  {connectResult.value === 'success' && (
                    <bk-form-item>
                      <div
                        class='es-cluster-management button-text'
                        onClick={() => (isShowManagement.value = !isShowManagement.value)}
                      >
                        <span>{t('ES集群管理')}</span>
                        <span
                          class={['bk-icon icon-angle-double-down', isShowManagement.value ? 'is-show' : ''].join(' ')}
                        ></span>
                      </div>
                    </bk-form-item>
                  )}

                  {/* 管理区块 */}
                  {isShowManagement.value && connectResult.value === 'success' && (
                    <div>
                      {/* 可见范围 */}
                      <bk-form-item
                        style='margin-top: 4px'
                        label={t('可见范围')}
                      >
                        <bk-radio-group
                          value={formData.value.visible_config.visible_type}
                          onChange={(v: string) => (formData.value.visible_config.visible_type = v)}
                        >
                          {visibleScopeSelectList.value.map(item => (
                            <bk-radio
                              key={item.id}
                              class='scope-radio'
                              value={item.id}
                            >
                              {item.name}
                            </bk-radio>
                          ))}
                        </bk-radio-group>

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
                            value={bkBizLabelsList.value}
                            clearable
                            onChange={(val: any[]) => (bkBizLabelsList.value = val)}
                            onInput-change={handleInputChange}
                            onInput-click-outside={handleClickOutside}
                            onMenu-child-select={handleChildMenuSelect}
                            onMenu-select={handleMenuSelect}
                          />
                        )}
                      </bk-form-item>

                      {/* 过期时间 */}
                      <bk-form-item
                        label={t('过期时间')}
                        required
                      >
                        <div class='flex-space'>
                          <div class='flex-space-item'>
                            <div class='space-item-label'>{t('默认')}</div>
                            <bk-select
                              clearable={false}
                              data-test-id='storageBox_select_selectExpiration'
                              value={formData.value.setup_config.retention_days_default}
                              onChange={(val: string) => (formData.value.setup_config.retention_days_default = val)}
                            >
                              {retentionDaysList.value.map((option, index) => (
                                <bk-option
                                  id={option.id}
                                  key={index}
                                  disabled={option.disabled}
                                  name={option.name}
                                />
                              ))}
                              <div
                                class='bk-select-name'
                                slot='trigger'
                              >
                                {String(formData.value.setup_config.retention_days_default) + t('天')}
                              </div>
                              <div
                                style='padding: 8px 0'
                                slot='extension'
                              >
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
                            </bk-select>
                          </div>

                          <div class='flex-space-item'>
                            <div class='space-item-label'>{t('最大')}</div>
                            <bk-select
                              clearable={false}
                              data-test-id='storageBox_select_selectExpiration'
                              value={formData.value.setup_config.retention_days_max}
                              onChange={(val: string) => (formData.value.setup_config.retention_days_max = val)}
                            >
                              {maxDaysList.value.map((option, index) => (
                                <bk-option
                                  id={option.id}
                                  key={index}
                                  disabled={option.disabled}
                                  name={option.name}
                                />
                              ))}
                              <div
                                style='padding: 8px 0'
                                slot='extension'
                              >
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
                              <div
                                class='bk-select-name'
                                slot='trigger'
                              >
                                {String(formData.value.setup_config.retention_days_max) + t('天')}
                              </div>
                            </bk-select>
                          </div>
                        </div>
                      </bk-form-item>

                      {/* 副本数 */}
                      <bk-form-item
                        label={t('副本数')}
                        required
                      >
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
                      </bk-form-item>

                      {/* 分片数 */}
                      <bk-form-item
                        label={t('分片数')}
                        required
                      >
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
                      </bk-form-item>

                      {/* 冷热数据 */}
                      <bk-form-item
                        v-show={connectResult.value === 'success'}
                        label={t('冷热数据')}
                      >
                        <div class='form-flex-container'>
                          <bk-switcher
                            disabled={isDisableHotSetting.value}
                            size='large'
                            theme='primary'
                            value={formData.value.enable_hot_warm}
                            onChange={val => {
                              formData.value.enable_hot_warm = val;
                              handleChangeHotWarm(val);
                            }}
                          />
                          {isDisableHotSetting.value &&
                            !connectLoading.value && [
                              <span class='bk-icon icon-info'></span>,
                              <span style='font-size: 12px'>{t('没有获取到正确的标签，')}</span>,
                              <a
                                class='button-text'
                                href={configDocUrl.value}
                                target='_blank'
                              >
                                {t('查看具体的配置方法')}
                              </a>,
                            ]}
                        </div>
                      </bk-form-item>

                      {/* 冷热数据标签 */}
                      {formData.value.enable_hot_warm && (
                        <div class='form-item-container'>
                          {/* 热数据标签 */}
                          <div class='bk-form-item'>
                            <div class='form-item-label'>
                              <p>{t('热数据标签')}</p>
                              {formData.value.hot_attr_name && formData.value.hot_attr_value && (
                                <div
                                  class='button-text'
                                  onClick={() => handleViewInstanceList('hot')}
                                >
                                  <span class='bk-icon icon-eye'></span>
                                  {t('查看实例列表')}
                                </div>
                              )}
                            </div>
                            <bk-select
                              value={selectedHotId.value}
                              onChange={(v: string) => handleHotSelected(v)}
                            >
                              {hotColdAttrSet.value.map(option => (
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
                                <div
                                  class='button-text'
                                  onClick={() => handleViewInstanceList('cold')}
                                >
                                  <span class='bk-icon icon-eye'></span>
                                  {t('查看实例列表')}
                                </div>
                              )}
                            </div>
                            <bk-select
                              value={selectedColdId.value}
                              onChange={(v: string) => handleColdSelected(v)}
                            >
                              {hotColdAttrSet.value.map(option => (
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
                        <bk-form-item label={t('日志归档')}>
                          <div class='document-container'>
                            <bk-switcher
                              size='large'
                              theme='primary'
                              value={formData.value.enable_archive}
                              onChange={(v: boolean) => (formData.value.enable_archive = v)}
                            />
                            {!!archiveDocUrl.value && (
                              <div
                                class='check-document button-text'
                                onClick={() => ManageHelper.handleGotoLink('logArchive')}
                              >
                                <span class='bk-icon icon-text-file'></span>
                                <a>{t('查看说明文档')}</a>
                              </div>
                            )}
                          </div>
                        </bk-form-item>
                        {isItsm.value && (
                          <bk-form-item label={t('容量评估')}>
                            <bk-switcher
                              size='large'
                              theme='primary'
                              value={formData.value.enable_assessment}
                              onChange={(v: boolean) => (formData.value.enable_assessment = v)}
                            />
                          </bk-form-item>
                        )}
                      </div>

                      {/* 集群负责人 */}
                      <bk-form-item
                        desc={t('集群负责人可以用于容量审核等')}
                        label={t('集群负责人')}
                        required
                      >
                        <div class='principal'>
                          <BkUserSelector
                            class={isAdminError.value && 'is-error'}
                            api={userApi.value}
                            empty-text={t('无匹配人员')}
                            placeholder={t('请选择集群负责人')}
                            value={formData.value.admin}
                            onBlur={handleBlur}
                            onChange={handleChangePrincipal}
                          />
                        </div>
                      </bk-form-item>

                      {/* 集群说明 */}
                      <bk-form-item
                        class='illustrate'
                        label={t('说明')}
                      >
                        <bk-input
                          maxlength={100}
                          rows={3}
                          type='textarea'
                          value={formData.value.description}
                          onChange={(val: string) => (formData.value.description = val)}
                        />
                      </bk-form-item>
                    </div>
                  )}
                </bk-form>
              )}

              {/* 底部提交按钮 */}
              <div class='submit-container'>
                <bk-button
                  class='king-button mr10'
                  data-test-id='esAccessFromBox_button_confirm'
                  disabled={isDisableClickSubmit.value}
                  loading={confirmLoading.value}
                  theme='primary'
                  onClick={handleConfirm}
                >
                  {t('提交')}
                </bk-button>
                <bk-button
                  data-test-id='esAccessFromBox_button_cancel'
                  onClick={handleCancel}
                >
                  {t('取消')}
                </bk-button>
              </div>
            </div>
          </template>
        </bk-sideslider>

        {/* 查看实例列表弹窗 */}
        <EsDialog
          formData={formData.value}
          list={hotColdOriginList.value}
          type={viewInstanceType.value}
          value={showInstanceDialog.value}
          on-handle-value-change={val => (showInstanceDialog.value = val)}
        />
      </div>
    );
  },
});
