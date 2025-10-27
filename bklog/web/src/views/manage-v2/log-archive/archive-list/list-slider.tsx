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

import { defineComponent, ref, reactive, computed, watch, onMounted, nextTick } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { InfoBox, Message } from 'bk-magic-vue';

import http from '@/api';

import './list-slider.scss';

export default defineComponent({
  name: 'ListSlider',
  props: {
    // 是否显示侧滑
    showSlider: {
      type: Boolean,
      default: false,
    },
    // 编辑归档数据
    editArchive: {
      type: Object,
      default: null,
    },
    onHandleCancelSlider: { type: Function },
    onHandleUpdatedTable: { type: Function },
  },
  emits: ['handleCancelSlider', 'handleUpdatedTable'],

  setup(props, { emit }) {
    const store = useStore();
    const { t } = useLocale(); // 获取国际化函数
    const validateForm = ref<any>(null); // 表单验证引用

    const confirmLoading = ref(false); // 确认按钮加载状态
    const sliderLoading = ref(false); // 侧滑内容加载状态
    const customRetentionDay = ref(''); // 自定义过期天数
    const collectorList = ref([
      { id: 'collector_config', name: t('采集项'), list: [] }, // 采集项列表
      { id: 'collector_plugin', name: t('采集插件'), list: [] }, // 采集插件列表
    ]);
    const repositoryOriginList = ref<any[]>([]); // 仓库列表
    const retentionDaysList = ref<any[]>([]); // 过期天数列表
    const collectorType = ref('collector_config'); // 采集类型

    // 表单数据
    const formData = reactive({
      snapshot_days: '',
      instance_id: '',
      target_snapshot_repository_name: '',
    });

    // 表单验证规则
    const basicRules = reactive({});
    const requiredRules = {
      required: true,
      trigger: 'blur',
    };

    const bkBizId = computed(() => store.getters.bkBizId); // 业务ID
    const globalsData = computed(() => store.getters['globals/globalsData']); // 全局数据
    const authorityMapComputed = computed(() => authorityMap); // 权限映射

    // 是否为编辑模式
    const isEdit = computed(() => props.editArchive !== null);

    // 仓库渲染列表 - 根据采集项关联的仓库列表
    const repositoryRenderList = computed(() => {
      let list: any[] = [];
      const collectorId = formData.instance_id;
      if (collectorId && collectorList.value.length && repositoryOriginList.value.length) {
        const targetList = collectorList.value.find(item => item.id === collectorType.value)?.list || [];
        const curCollector = targetList.find((collect: any) => collect.id === collectorId);
        const clusterId = curCollector?.storage_cluster_id;
        list = repositoryOriginList.value.filter(item => item.cluster_id === clusterId);
      }
      return list;
    });

    // 获取过期时间
    const getDaysStr = computed(() => {
      if (String(formData.snapshot_days) === '0') {
        return t('永久');
      }
      return formData.snapshot_days ? formData.snapshot_days + t('天') : '';
    });

    // 获取采集项列表
    const getCollectorList = async () => {
      const query = {
        bk_biz_id: bkBizId.value,
        have_data_id: 1,
      };

      try {
        // 获取采集项配置列表
        const collectorConfigRes = await http.request('collect/getAllCollectors', { query });
        collectorList.value[0].list =
          collectorConfigRes.data.map((item: any) => ({
            id: item.collector_config_id,
            name: item.collector_config_name,
            ...item,
          })) || [];

        // 获取采集插件列表
        const collectorPluginRes = await http.request('collect/getCollectorPlugins', { query });
        collectorList.value[1].list =
          collectorPluginRes.data.map((item: any) => ({
            id: item.collector_plugin_id,
            name: item.collector_plugin_name,
            ...item,
          })) || [];
      } catch (error) {
        console.warn('获取采集项列表失败:', error);
      }
    };

    // 获取归档仓库列表
    const getRepoList = async () => {
      try {
        const res = await http.request('archive/getRepositoryList', {
          query: {
            bk_biz_id: bkBizId.value,
          },
        });
        const { data } = res;
        repositoryOriginList.value = data || [];
      } catch (error) {
        console.warn('获取归档仓库列表失败:', error);
      } finally {
        sliderLoading.value = false;
      }
    };

    // 采集项变更处理
    const handleCollectorChange = (value: any) => {
      collectorType.value = collectorList.value.find(item => item.list.some((val: any) => val.id === value))?.id || '';
      formData.target_snapshot_repository_name = '';
    };

    // 取消处理
    const handleCancel = () => {
      InfoBox({
        title: t('确认离开当前页？'),
        subTitle: t('离开将会导致未保存信息丢失'),
        okText: t('离开'),
        cancelText: t('取消'),
        confirmFn: () => emit('handleCancelSlider'),
      });
    };

    // 更新天数列表
    const updateDaysList = () => {
      const retentionDaysListData = [...globalsData.value.storage_duration_time].filter(item => {
        return item.id;
      });
      retentionDaysListData.push({
        default: false,
        id: '0',
        name: t('永久'),
      });
      retentionDaysList.value = retentionDaysListData;
    };

    // 输入自定义过期天数
    const enterCustomDay = (val: string) => {
      const numberVal = Number.parseInt(val.trim(), 10);
      const stringVal = numberVal.toString();
      if (numberVal) {
        if (!retentionDaysList.value.some(item => item.id === stringVal)) {
          retentionDaysList.value.push({
            id: stringVal,
            name: stringVal + t('天'),
          });
        }
        formData.snapshot_days = stringVal;
        customRetentionDay.value = '';
        document.body.click();
      } else {
        customRetentionDay.value = '';
        Message({
          theme: 'error',
          message: t('请输入有效数值'),
        });
      }
    };

    // 确认提交表单逻辑
    const handleConfirm = async () => {
      try {
        // 验证表单
        await validateForm.value?.validate();

        // 确定请求URL和参数
        let url = '/archive/createArchive';
        const params: any = {};
        let paramsData: any = {
          ...formData,
          instance_type: collectorType.value,
          bk_biz_id: bkBizId.value,
        };

        // 编辑模式下的参数调整
        if (isEdit.value) {
          url = '/archive/editArchive';
          const { snapshot_days } = formData;
          const { archive_config_id } = props.editArchive;
          paramsData = {
            snapshot_days,
          };
          params.archive_config_id = archive_config_id;
        }

        // 设置提交按钮为加载状态
        confirmLoading.value = true;

        // 调用接口提交数据
        await http.request(url, {
          data: paramsData,
          params,
        });

        // 提示保存成功
        Message({
          theme: 'success',
          message: t('保存成功'),
          delay: 1500,
        });

        // 通知父组件更新
        emit('handleUpdatedTable');
      } catch (error) {
        // 捕获异常并输出
        console.warn('提交失败:', error);
        console.log('验证失败详情:', error);
      } finally {
        // 关闭加载状态
        confirmLoading.value = false;
      }
    };

    // 渲染采集项选项
    const renderCollectorOptions = () => {
      return collectorList.value.map(item => (
        <bk-option-group
          id={item.id}
          key={item.id}
          name={item.name}
          show-collapse
        >
          {item.list.map((option: any) => (
            <bk-option
              id={option.id}
              key={option.id}
              disabled={!option.permission[authorityMapComputed.value.MANAGE_COLLECTION_AUTH]}
              name={option.name}
            >
              {option.name}
            </bk-option>
          ))}
        </bk-option-group>
      ));
    };

    // 渲染仓库选项
    const renderRepositoryOptions = () => {
      return repositoryRenderList.value.map(option => (
        <bk-option
          id={option.repository_name}
          key={option.repository_name}
          disabled={!option.permission[authorityMapComputed.value.MANAGE_ES_SOURCE_AUTH]}
          name={option.repository_name}
        >
          {option.repository_name}
        </bk-option>
      ));
    };

    // 渲染过期时间选项
    const renderRetentionDaysOptions = () => {
      return retentionDaysList.value.map(option => (
        <bk-option
          id={option.id}
          key={option.id}
          name={option.name}
        />
      ));
    };

    // 监听 showSlider 变化
    watch(
      () => props.showSlider,
      async val => {
        if (val) {
          sliderLoading.value = isEdit.value;
          await getCollectorList();
          await getRepoList();
          updateDaysList();

          if (isEdit.value) {
            const {
              instance_id: instanceId,
              target_snapshot_repository_name,
              snapshot_days,
              instance_type: instanceType,
            } = props.editArchive;

            // 先设置采集类型和采集项
            collectorType.value = instanceType;
            formData.instance_id = instanceId;
            formData.snapshot_days = snapshot_days;

            // 等仓库选项刷新后再赋值仓库名称
            await nextTick();
            formData.target_snapshot_repository_name = target_snapshot_repository_name;
          }
        } else {
          // 清空表单数据
          Object.assign(formData, {
            snapshot_days: '',
            instance_id: '',
            target_snapshot_repository_name: '',
          });
        }
      },
    );

    // 组件挂载时初始化验证规则
    onMounted(() => {
      Object.assign(basicRules, {
        instance_id: [requiredRules],
        target_snapshot_repository_name: [requiredRules],
        snapshot_days: [requiredRules],
      });
    });

    // 侧滑组件主渲染
    return () => (
      <div class='archive-slider-container'>
        <bk-sideslider
          width={676}
          is-show={props.showSlider}
          quick-close={true}
          show-mask={true}
          title={isEdit.value ? t('编辑归档') : t('新建归档')}
          transfer
          onAnimation-end={handleCancel}
        >
          <template slot='content'>
            <div
              class='archive-slider-content'
              v-bkloading={{ isLoading: sliderLoading.value }}
            >
              {/* 加载完成后渲染表单 */}
              {!sliderLoading.value && (
                <bk-form
                  ref={validateForm}
                  class='king-form'
                  data-test-id='addNewArchive_div_formContainer'
                  form-type='vertical'
                  label-width={350}
                  {...{
                    props: {
                      model: formData,
                      rules: basicRules,
                    },
                  }}
                >
                  {/* 选择采集项/采集插件 */}
                  <bk-form-item
                    label={t('选择采集项/采集插件')}
                    property='instance_id'
                    required
                  >
                    <bk-select
                      clearable={false}
                      data-test-id='formContainer_select_selectCollector'
                      disabled={isEdit.value}
                      value={formData.instance_id}
                      searchable
                      onChange={val => {
                        formData.instance_id = val;
                        handleCollectorChange(val);
                      }}
                    >
                      {renderCollectorOptions()}
                    </bk-select>
                  </bk-form-item>

                  {/* 归档仓库 */}
                  <bk-form-item
                    label={t('归档仓库')}
                    property='target_snapshot_repository_name'
                    required
                  >
                    <bk-select
                      data-test-id='formContainer_select_selectStorehouse'
                      disabled={isEdit.value || !formData.instance_id}
                      value={formData.target_snapshot_repository_name}
                      onChange={val => (formData.target_snapshot_repository_name = val)}
                    >
                      {renderRepositoryOptions()}
                    </bk-select>
                  </bk-form-item>

                  {/* 过期时间 */}
                  <bk-form-item
                    label={t('过期时间')}
                    property='snapshot_days'
                    required
                  >
                    <bk-select
                      style='width: 300px'
                      scopedSlots={{
                        trigger: () => <div class='bk-select-name'>{getDaysStr.value}</div>,
                        extension: () => (
                          <div style='padding: 8px 0'>
                            <bk-input
                              placeholder={t('输入自定义天数，按 Enter 确认')}
                              show-controls={false}
                              size='small'
                              type='number'
                              value={customRetentionDay.value}
                              onChange={val => (customRetentionDay.value = val)}
                              onEnter={(val: string) => enterCustomDay(val)}
                            />
                          </div>
                        ),
                      }}
                      clearable={false}
                      data-test-id='formContainer_select_selectExpireDate'
                      value={formData.snapshot_days}
                      onChange={val => (formData.snapshot_days = val)}
                    >
                      {renderRetentionDaysOptions()}
                    </bk-select>
                  </bk-form-item>

                  {/* 提交/取消按钮 */}
                  <bk-form-item style='margin-top: 40px'>
                    <bk-button
                      class='king-button mr10'
                      data-test-id='formContainer_button_handleSubmit'
                      loading={confirmLoading.value}
                      theme='primary'
                      onClick={handleConfirm}
                    >
                      {t('提交')}
                    </bk-button>
                    <bk-button
                      data-test-id='formContainer_button_handleCancel'
                      onClick={handleCancel}
                    >
                      {t('取消')}
                    </bk-button>
                  </bk-form-item>
                </bk-form>
              )}
            </div>
          </template>
        </bk-sideslider>
      </div>
    );
  },
});
