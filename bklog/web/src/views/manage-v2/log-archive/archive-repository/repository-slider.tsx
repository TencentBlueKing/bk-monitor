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

import { defineComponent, ref, reactive, computed, watch } from 'vue';

import * as authorityMap from '@/common/authority-map';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { Message, InfoBox } from 'bk-magic-vue';

import http from '@/api';

import './repository-slider.scss';

// 添加类型声明
declare function require(path: string): string;

// 配置表单初始化函数 HDFS
const hdfsConfigForm = () => ({
  uri: '',
  path: '',
  isSecurity: false,
  compress: true,
  security: {
    principal: '',
  },
});

// 配置表单初始化函数 COS
const cosConfigForm = () => ({
  app_id: '',
  access_key_id: '',
  access_key_secret: '',
  bucket: '',
  region: '',
  base_path: '',
  compress: true,
});

// 配置表单初始化函数 FS
const fsConfigForm = () => ({
  location: '',
});

export default defineComponent({
  name: 'RepositorySlider',
  props: {
    showSlider: {
      type: Boolean,
      default: false,
    },
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

    const confirmLoading = ref(false); // 确认按钮加载状态
    const sliderLoading = ref(false); // 侧滑内容加载状态
    const esClusterSource = ref(''); // ES集群来源
    const esClusterList = ref<any[]>([]); // ES集群列表
    const validateForm = ref<any>(null); // 表单验证引用

    // 仓库类型配置
    const repository = ref([
      { id: 'hdfs', name: 'HDFS', image: require('@/images/hdfs.png') },
      { id: 'fs', name: t('共享目录'), image: require('@/images/fs.png') },
      { id: 'cos', name: 'COS', image: require('@/images/cos.png') },
    ]);

    // 表单数据
    const formData = reactive({
      cluster_id: '',
      snapshot_repository_name: '',
      es_config: {
        type: 'hdfs',
      },
      cosFormData: cosConfigForm(),
      hdfsFormData: hdfsConfigForm(),
      fsFormData: fsConfigForm(),
    });

    // 获取业务ID和编辑状态
    const bkBizId = computed(() => store.getters.bkBizId);
    const isEdit = computed(() => props.editClusterId !== null);

    // 必填规则抽离
    const requiredRules = {
      required: true,
      trigger: 'blur',
    };

    // 表单验证规则
    const basicRules = reactive({
      cluster_id: [requiredRules],
      snapshot_repository_name: [
        {
          regex: /^[A-Za-z0-9_]+$/,
          trigger: 'blur',
        },
      ],
      path: [requiredRules],
      uri: [requiredRules],
      principal: [
        {
          validator: () => {
            const { isSecurity, security } = formData.hdfsFormData;
            if (isSecurity && security.principal.trim() === '') {
              return false;
            }
            return true;
          },
          trigger: 'blur',
        },
      ],
      location: [requiredRules],
      base_path: [requiredRules],
      region: [requiredRules],
      access_key_id: [requiredRules],
      access_key_secret: [requiredRules],
      app_id: [requiredRules],
      bucket: [requiredRules],
    });

    // 获取ES集群列表
    const getEsClusterList = async () => {
      try {
        const res = await http.request('/source/getEsList', {
          query: {
            bk_biz_id: bkBizId.value,
            enable_archive: 1,
          },
        });
        if (res.data) {
          esClusterList.value = res.data;
        }
      } catch (error) {
        console.warn('获取ES集群列表失败:', error);
      }
    };

    // 集群变更处理
    const handleChangeCluster = (_value: string) => {
      // const curCluster = esClusterList.value.find(cluster => cluster.cluster_config.cluster_id === value);
      // esClusterSource.value = curCluster?.source_name || '';
    };

    // 取消操作/关闭侧滑弹窗
    const handleCancel = () => {
      InfoBox({
        title: t('确认离开当前页？'),
        subTitle: t('离开将会导致未保存信息丢失'),
        okText: t('离开'),
        cancelText: t('取消'),
        confirmFn: () => emit('handleCancelSlider'),
      });
    };

    // 切换仓库类型
    const changeRepository = (card: any) => {
      if (formData.es_config.type !== card.id) {
        validateForm.value?.clearError();
        formData.es_config.type = card.id;
      }
    };

    // 初始化侧滑表单数据
    const initSidebarFormData = () => {
      // 重置表单数据
      Object.assign(formData, {
        cluster_id: '',
        snapshot_repository_name: '',
        es_config: { type: 'hdfs' },
        cosFormData: cosConfigForm(),
        hdfsFormData: hdfsConfigForm(),
        fsFormData: fsConfigForm(),
      });
    };

    // 确认提交表单逻辑
    const handleConfirm = async () => {
      try {
        // 验证表单
        await validateForm.value?.validate();
        const url = '/archive/createRepository';

        // 解构表单数据
        const {
          cluster_id,
          snapshot_repository_name: snapshotRepositoryName,
          es_config: esConfig,
          hdfsFormData,
          fsFormData,
          cosFormData,
        } = formData;

        // 组装提交参数
        const paramsData: any = {
          cluster_id,
          snapshot_repository_name: snapshotRepositoryName,
          alias: snapshotRepositoryName,
          es_config: {
            type: esConfig.type,
          },
          bk_biz_id: bkBizId.value,
        };

        // 根据仓库类型添加不同的配置参数
        if (esConfig.type === 'hdfs') {
          const { uri, path, isSecurity, security, compress } = hdfsFormData;
          const principal = isSecurity ? security.principal : undefined;
          paramsData.es_config.settings = {
            uri,
            path,
            compress,
            'security.principal': principal,
          };
        }
        if (esConfig.type === 'fs') {
          paramsData.es_config.settings = { ...fsFormData };
        }
        if (esConfig.type === 'cos') {
          paramsData.es_config.settings = { ...cosFormData };
        }

        // 设置提交按钮为加载状态
        confirmLoading.value = true;

        // 调用接口提交数据
        await http.request(url, {
          data: paramsData,
        });

        // 提示保存成功
        Message({
          theme: 'success',
          message: t('保存成功'),
          delay: 1500,
        });

        // 通知父组件刷新列表
        emit('handleUpdatedTable');
      } catch (error) {
        // 捕获异常并输出
        console.warn('提交失败:', error);
      } finally {
        // 关闭加载状态
        confirmLoading.value = false;
      }
    };

    // ES集群管理权限申请
    const applyProjectAccess = async (option: any) => {
      try {
        // 手动关闭下拉
        const event = new Event('click');
        document.dispatchEvent(event);

        const res = await store.dispatch('getApplyData', {
          action_ids: [authorityMap.MANAGE_ES_SOURCE_AUTH],
          resources: [
            {
              type: 'es_source',
              id: option.cluster_config.cluster_id,
            },
          ],
        });
        window.open(res.data.apply_url);
      } catch (error) {
        console.warn('权限申请失败:', error);
      }
    };

    // 监听showSlider变化
    watch(
      () => props.showSlider,
      val => {
        if (val) {
          getEsClusterList();
          initSidebarFormData();
        } else {
          // 清空表单数据
          initSidebarFormData();
        }
      },
    );

    // 渲染ES集群选项
    const renderEsClusterOptions = () => {
      return esClusterList.value.map(option => (
        <bk-option
          id={option.storage_cluster_id}
          key={option.storage_cluster_id}
          name={option.storage_cluster_name}
        >
          {option.permission?.[authorityMap.MANAGE_ES_SOURCE_AUTH] ? (
            <div
              class='option-slot-container'
              v-bk-overflow-tips
            >
              <span>{option.storage_cluster_name}</span>
            </div>
          ) : (
            <div
              class='option-slot-container no-authority'
              onClick={(e: Event) => e.stopPropagation()}
            >
              <span class='text'>
                <span>{option.storage_cluster_name}</span>
              </span>
              <span
                class='apply-text'
                onClick={() => applyProjectAccess(option)} // eslint-disable-line @typescript-eslint/no-misused-promises
              >
                {t('申请权限')}
              </span>
            </div>
          )}
        </bk-option>
      ));
    };

    // 渲染仓库类型卡片
    const renderRepositoryCards = () => {
      return repository.value.map(card => (
        <div
          key={card.name}
          class={{
            'repository-card': true,
            'is-active': formData.es_config.type === card.id,
          }}
          data-test-id={`addNewStorehouse_div_${card.id}`}
          onClick={() => changeRepository(card)}
        >
          <span class='repository-name'>{card.name}</span>
          {/** biome-ignore lint/performance/noImgElement: reason */}
          {/** biome-ignore lint/nursery/useImageSize: reason */}
          <img
            class='card-image'
            alt={card.name}
            src={card.image}
          />
        </div>
      ));
    };

    // 渲染HDFS配置
    const renderHdfsConfig = () => {
      if (formData.es_config.type !== 'hdfs') {
        return null;
      }

      return (
        <div key='hdfs'>
          <bk-form-item
            label={t('归档目录')}
            property={formData.hdfsFormData.path}
            rules={basicRules.path}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_archiveCatalog'
              value={formData.hdfsFormData.path}
              onChange={val => (formData.hdfsFormData.path = val)}
            />
          </bk-form-item>
          <bk-form-item
            label={t('HDFS地址')}
            property={formData.hdfsFormData.uri}
            rules={basicRules.uri}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_HDFSurl'
              value={formData.hdfsFormData.uri}
              onChange={val => (formData.hdfsFormData.uri = val)}
            />
          </bk-form-item>
          <bk-form-item
            label='Principal'
            property={formData.hdfsFormData.security.principal}
            rules={basicRules.principal}
            required
          >
            <div class='principal-item'>
              <bk-switcher
                size='large'
                theme='primary'
                value={formData.hdfsFormData.isSecurity}
                onChange={val => (formData.hdfsFormData.isSecurity = val)}
              />
              <bk-input
                data-test-id='addNewStorehouse_input_principal'
                value={formData.hdfsFormData.security.principal}
                onChange={val => (formData.hdfsFormData.security.principal = val)}
              />
            </div>
          </bk-form-item>
        </div>
      );
    };

    // 渲染FS配置
    const renderFsConfig = () => {
      if (formData.es_config.type !== 'fs') {
        return null;
      }

      return (
        <div key='fs'>
          <bk-form-item
            data-test-id='addNewStorehouse_input_archiveCatalog'
            label={t('归档目录')}
            property={formData.fsFormData.location}
            rules={basicRules.location}
            required
          >
            <bk-input
              value={formData.fsFormData.location}
              onChange={val => (formData.fsFormData.location = val)}
            />
          </bk-form-item>
        </div>
      );
    };

    // 渲染COS配置
    const renderCosConfig = () => {
      if (formData.es_config.type !== 'cos') {
        return null;
      }

      return (
        <div key='cos'>
          <bk-form-item
            label={t('归档目录')}
            property={formData.cosFormData.base_path}
            rules={basicRules.base_path}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_archiveCatalog'
              value={formData.cosFormData.base_path}
              onChange={val => (formData.cosFormData.base_path = val)}
            />
          </bk-form-item>
          <bk-form-item
            label={t('区域')}
            property={formData.cosFormData.region}
            rules={basicRules.region}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_region'
              value={formData.cosFormData.region}
              onChange={val => (formData.cosFormData.region = val)}
            />
          </bk-form-item>
          <bk-form-item
            label='Secretld'
            property={formData.cosFormData.access_key_id}
            rules={basicRules.access_key_id}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_Secretld'
              value={formData.cosFormData.access_key_id}
              onChange={val => (formData.cosFormData.access_key_id = val)}
            />
          </bk-form-item>
          <bk-form-item
            label='SecretKey'
            property={formData.cosFormData.access_key_secret}
            rules={basicRules.access_key_secret}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_SecretKey'
              type='password'
              value={formData.cosFormData.access_key_secret}
              onChange={val => (formData.cosFormData.access_key_secret = val)}
            />
          </bk-form-item>
          <bk-form-item
            label='APPID'
            property={formData.cosFormData.app_id}
            rules={basicRules.app_id}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_APPID'
              value={formData.cosFormData.app_id}
              onChange={val => (formData.cosFormData.app_id = val)}
            />
          </bk-form-item>
          <bk-form-item
            label={t('Bucket名字')}
            property={formData.cosFormData.bucket}
            rules={basicRules.bucket}
            required
          >
            <bk-input
              data-test-id='addNewStorehouse_input_BucketName'
              value={formData.cosFormData.bucket}
              onChange={val => (formData.cosFormData.bucket = val)}
            />
          </bk-form-item>
        </div>
      );
    };

    // 渲染配置说明
    const renderConfigAlert = () => {
      // 根据不同的仓库类型定义不同的配置说明
      const alertContent = () => {
        if (formData.es_config.type === 'hdfs') {
          return (
            <div>
              <p>{t('1. 用户需要在hdfs设置的kerberos中创建给es使用的principal, 然后导出对应的keytab文件')}</p>
              <p>{t('2. 将keytab放es每个节点对应的目录中去')}</p>
            </div>
          );
        }
        if (formData.es_config.type === 'fs') {
          return <p>{t('本地目录配置说明')}</p>;
        }
        if (formData.es_config.type === 'cos') {
          return <p>{t('COS的自动创建和关联，只能用于腾讯云')}</p>;
        }
        return null;
      };

      return (
        <bk-alert type='info'>
          <template slot='title'>
            <div class='repository-alert'>{alertContent()}</div>
          </template>
        </bk-alert>
      );
    };

    // 侧滑组件主渲染
    return () => (
      <div
        class='repository-slider-container'
        data-test-id='archive_div_addNewStorehouse'
      >
        <bk-sideslider
          width={676}
          is-show={props.showSlider}
          quick-close={true}
          show-mask={true}
          title={isEdit.value ? t('编辑归档仓库') : t('新建归档仓库')}
          transfer
          onAnimation-end={handleCancel}
        >
          <template slot='content'>
            <div
              class='repository-slider-content'
              v-bkloading={{ isLoading: sliderLoading.value }}
            >
              {/* 加载完成后渲染表单 */}
              {!sliderLoading.value && (
                <bk-form
                  ref={validateForm}
                  class='king-form'
                  form-type='vertical'
                  label-width={150}
                  {...{
                    props: {
                      model: formData,
                      rules: basicRules,
                    },
                  }}
                >
                  {/* 基础信息标题 */}
                  <h3 class='form-title'>{t('基础信息')}</h3>
                  {/* ES集群选择 */}
                  <bk-form-item
                    ext-cls='es-cluster-item'
                    label={t('ES集群')}
                    property='cluster_id'
                    rules={basicRules.cluster_id}
                    required
                  >
                    <bk-select
                      data-test-id='addNewStorehouse_select_selectEsCluster'
                      value={formData.cluster_id}
                      searchable
                      onChange={val => {
                        formData.cluster_id = val;
                        handleChangeCluster(val);
                      }}
                    >
                      {renderEsClusterOptions()}
                    </bk-select>
                    {/* 显示ES集群来源 */}
                    {esClusterSource.value && (
                      <p class='es-source'>
                        <span>{t('来源')}：</span>
                        <span>{esClusterSource.value}</span>
                      </p>
                    )}
                  </bk-form-item>

                  {/* 仓库类型选择 */}
                  <h3 class='form-title'>{t('配置')}</h3>
                  <bk-form-item
                    ext-cls='repository-item'
                    label={t('类型')}
                    required
                  >
                    {renderRepositoryCards()}
                  </bk-form-item>

                  {/* 配置说明提示 */}
                  {renderConfigAlert()}

                  {/* 仓库名称输入 */}
                  <bk-form-item
                    label={t('仓库名称')}
                    property='snapshot_repository_name'
                    required
                  >
                    <bk-input
                      data-test-id='addNewStorehouse_input_repoName'
                      placeholder={t('只能输入英文、数字或者下划线')}
                      value={formData.snapshot_repository_name}
                      onChange={val => (formData.snapshot_repository_name = val)}
                    />
                  </bk-form-item>

                  {/* 根据仓库类型动态渲染配置表单 */}
                  {renderHdfsConfig()}
                  {renderFsConfig()}
                  {renderCosConfig()}

                  {/* 提交/取消按钮 */}
                  <bk-form-item style='margin-top: 40px'>
                    <bk-button
                      class='king-button mr10'
                      data-test-id='addNewStorehouse_button_submit'
                      loading={confirmLoading.value}
                      theme='primary'
                      onClick={handleConfirm}
                    >
                      {t('提交')}
                    </bk-button>
                    <bk-button
                      data-test-id='addNewStorehouse_button_cancel'
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
