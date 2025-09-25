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
import { defineComponent, ref, computed, onMounted } from 'vue';

import useLocale from '@/hooks/use-locale';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import BkUserSelector from '@blueking/user-selector';

import http from '@/api';

import './link-create.scss';

export default defineComponent({
  name: 'ExtractLinkCreateTsx',
  setup() {
    const store = useStore();
    const router = useRouter();
    const { t } = useLocale();

    const formRef = ref<any>(null); // 表单ref
    const hostListRef = ref<any>(null); // 主机列表ul ref
    const basicLoading = ref(false); // 基础信息loading
    const submitLoading = ref(false); // 提交按钮loading
    const isSubmit = ref(false); // 是否已提交
    const userApi = (window as any).BK_LOGIN_URL; // 用户选择器API
    const isAdminError = ref(false); // 人员是否为空
    const cacheOperator = ref<any[]>([]); // 缓存的人员
    const isDisableCommon = ref(false); // 是否禁用内网链路
    const editInitLinkType = ref(''); // 编辑初始化时的链路类型
    const formData = ref<any>({
      // 表单数据
      name: '',
      link_type: 'common',
      operator: [],
      op_bk_biz_id: '',
      qcloud_secret_id: '', // 腾讯云SecretId
      qcloud_secret_key: '', // 腾讯云SecretKey
      qcloud_cos_bucket: '', // 腾讯云Cos桶名称
      qcloud_cos_region: '', // 腾讯云Cos区域
      is_enable: true, // 是否启用
      hosts: [
        {
          keyId: Date.now(),
          target_dir: '',
          bk_cloud_id: '',
          ip: '',
        },
      ],
    });
    const formRules = {
      // 表单校验规则
      name: [{ required: true, trigger: 'blur' }],
      op_bk_biz_id: [{ required: true, trigger: 'blur' }],
      qcloud_secret_key: [{ required: true, trigger: 'blur' }],
      qcloud_cos_bucket: [{ required: true, trigger: 'blur' }],
      qcloud_secret_id: [{ required: true, trigger: 'blur' }],
      qcloud_cos_region: [{ required: true, trigger: 'blur' }],
    };
    const isK8sDeploy = computed(() => store.getters['globals/globalsData']?.is_k8s_deploy); // 是否k8s部署
    const isShowCommon = computed(() => router.currentRoute?.params?.linkId && editInitLinkType.value === 'common'); // 是否展示内网链路

    // 初始化表单数据
    // biome-ignore lint/complexity/noExcessiveCognitiveComplexity: reason
    const init = async () => {
      const linkId = router.currentRoute?.params?.linkId;
      if (linkId) {
        try {
          basicLoading.value = true;
          const res = await http.request('extractManage/getLogExtractLinkDetail', {
            params: { link_id: linkId },
          });
          const { link_id: _linkId, ...otherData } = res.data;
          const data = otherData;
          data.hosts.forEach((item: any, idx: number) => {
            item.keyId = idx;
          });
          data.operator = [data.operator];
          if (data.link_type === 'qcloud_cos') {
            data.qcloud_secret_key = res.qcloud_secret_key || '******';
          }
          Object.assign(formData.value, data);
          basicLoading.value = false;
          editInitLinkType.value = formData.value.link_type;
        } catch (e) {
          console.warn(e);
          router.push({ name: 'extract-link-list', query: { spaceUid: store.state.spaceUid } });
        } finally {
          if (isK8sDeploy.value && editInitLinkType.value === 'common') {
            isDisableCommon.value = true;
          }
        }
      } else if (isK8sDeploy.value) {
        formData.value.link_type = 'qcloud_cos';
      }
    };

    // 添加中转机
    const addHost = () => {
      formData.value.hosts.push({
        keyId: Date.now(),
        target_dir: '',
        bk_cloud_id: '',
        ip: '',
      });
    };

    // 删除中转机
    const deleteHost = (index: number) => {
      formData.value.hosts.splice(index, 1);
    };

    // 输入框失焦校验
    const handleInputBlur = (value: string, event: any) => {
      if (value) {
        event.target.classList.remove('error');
      } else {
        event.target.classList.add('error');
      }
    };

    // 提交表单
    const submitForm = async () => {
      try {
        let isError = false;
        const inputList = hostListRef.value?.getElementsByClassName('bk-form-input') || [];
        for (const inputEl of inputList) {
          if (inputEl.value) {
            inputEl.classList.remove('error');
          } else {
            isError = true;
            console.log('输入框验证失败:', inputEl);
            inputEl.classList.add('error');
          }
        }

        await formRef.value.validate();

        if (isError || isAdminError.value) {
          return;
        }

        submitLoading.value = true;
        let requestData = { ...formData.value };
        if (requestData.link_type === 'common') {
          const {
            qcloud_cos_bucket: _qcloudCosBucket,
            qcloud_cos_region: _qcloudCosRegion,
            qcloud_secret_id: _qcloudSecretId,
            qcloud_secret_key: _qcloudSecretKey,
            ...rest
          } = requestData;
          requestData = rest;
        }
        if (requestData.link_type === 'qcloud_cos' && requestData.qcloud_secret_key === '******') {
          requestData.qcloud_secret_key = '';
        }
        requestData.hosts = requestData.hosts.map((host: any) => {
          const { keyId: _keyId, ...rest } = host;
          return rest;
        });
        requestData.operator = requestData.operator[0];
        const linkId = router.currentRoute?.params?.linkId;
        if (linkId) {
          await http.request('extractManage/updateLogExtractLink', {
            params: { link_id: linkId },
            data: requestData,
          });
          (window as any)?.bkMessage?.success?.(t('保存成功'));
        } else {
          await http.request('extractManage/createLogExtractLink', {
            data: requestData,
          });
          (window as any)?.bkMessage?.success?.(t('创建成功'));
        }
        isSubmit.value = true;
        router.push({ name: 'extract-link-list', query: { spaceUid: store.state.spaceUid } });
      } catch (e) {
        console.warn(e);
        submitLoading.value = false;
      }
    };

    // 人员选择变化
    const handleUserChange = (val: any[]) => {
      const realVal = val.filter(item => item !== undefined);
      isAdminError.value = !realVal.length;
      formData.value.operator = realVal;
      cacheOperator.value = realVal;
    };

    // 清空人员选择
    const handleClearOperator = () => {
      if (formData.value.operator.length) {
        cacheOperator.value = formData.value.operator;
        formData.value.operator = [];
      }
    };

    // 人员选择失焦
    const handleBlur = () => {
      if (cacheOperator.value.length) {
        formData.value.operator = cacheOperator.value;
      }
    };

    // 组件挂载时初始化
    onMounted(() => {
      init();
    });

    // 主渲染函数
    return () => (
      <div
        class='extract-link-create-container'
        v-bkloading={{ isLoading: basicLoading.value }}
        data-test-id='extractLinkCreate_div_extractLinkCreateBox'
      >
        {/* 基础信息 */}
        <article
          class='article'
          data-test-id='extractLinkCreateBox_article_basicInformation'
        >
          <h3 class='title'>{t('基础信息')}</h3>
          <bk-form
            ref={formRef}
            class='king-form'
            label-width={160}
            {...{
              props: {
                model: formData.value,
                rules: formRules,
              },
            }}
          >
            {/* 链路名称 */}
            <bk-form-item
              label={t('链路名称')}
              property='name'
              required
            >
              <bk-input
                data-test-id='basicInformation_input_linkName'
                value={formData.value.name}
                onChange={val => (formData.value.name = val)}
              />
            </bk-form-item>

            {/* 链路类型 */}
            <bk-form-item
              label={t('链路类型')}
              property='link_type'
              required
            >
              <bk-select
                clearable={false}
                data-test-id='basicInformation_select_selectLinkType'
                value={formData.value.link_type}
                onChange={val => (formData.value.link_type = val)}
              >
                {(!isK8sDeploy.value || isShowCommon.value) && (
                  <bk-option
                    id='common'
                    disabled={isDisableCommon.value}
                    name={t('内网链路')}
                  />
                )}
                <bk-option
                  id='qcloud_cos'
                  name={t('腾讯云链路')}
                />
                <bk-option
                  id='bk_repo'
                  name={t('蓝鲸制品库')}
                />
              </bk-select>
            </bk-form-item>

            {/* 执行人 */}
            <bk-form-item
              label={t('执行人')}
              property='operator'
              required
            >
              <BkUserSelector
                class={isAdminError.value ? 'is-error' : ''}
                api={userApi}
                data-test-id='basicInformation_input_executive'
                empty-text={t('无匹配人员')}
                placeholder={t('请选择用户')}
                value={formData.value.operator}
                onBlur={handleBlur}
                onChange={handleUserChange}
                onFocus={handleClearOperator}
              />
            </bk-form-item>

            {/* 执行bk_biz_id */}
            <bk-form-item
              label={t('执行bk_biz_id')}
              property='op_bk_biz_id'
              required
            >
              <bk-input
                data-test-id='basicInformation_input_executivebk_biz_id'
                value={formData.value.op_bk_biz_id}
                onChange={val => (formData.value.op_bk_biz_id = val)}
              />
            </bk-form-item>

            {/* 腾讯云相关表单项，仅在qcloud_cos时显示 */}
            {formData.value.link_type === 'qcloud_cos' && [
              <bk-form-item
                key='qcloud_secret_id'
                label={t('腾讯云SecretId')}
                property='qcloud_secret_id'
                required
              >
                <bk-input
                  data-test-id='basicInformation_input_SecretId'
                  value={formData.value.qcloud_secret_id}
                  onChange={val => (formData.value.qcloud_secret_id = val)}
                />
              </bk-form-item>,
              <bk-form-item
                key='qcloud_secret_key'
                label={t('腾讯云SecretKey')}
                property='qcloud_secret_key'
                required
              >
                <bk-input
                  data-test-id='basicInformation_input_SecretKey'
                  type='password'
                  value={formData.value.qcloud_secret_key}
                  onChange={val => (formData.value.qcloud_secret_key = val)}
                />
              </bk-form-item>,
              <bk-form-item
                key='qcloud_cos_bucket'
                label={t('腾讯云Cos桶名称')}
                property='qcloud_cos_bucket'
                required
              >
                <bk-input
                  data-test-id='basicInformation_input_cosBucket'
                  value={formData.value.qcloud_cos_bucket}
                  onChange={val => (formData.value.qcloud_cos_bucket = val)}
                />
              </bk-form-item>,
              <bk-form-item
                key='qcloud_cos_region'
                label={t('腾讯云Cos区域')}
                property='qcloud_cos_region'
                required
              >
                <bk-input
                  data-test-id='basicInformation_input_cosRegion'
                  value={formData.value.qcloud_cos_region}
                  onChange={val => (formData.value.qcloud_cos_region = val)}
                />
              </bk-form-item>,
            ]}

            {/* 是否启用 */}
            <bk-form-item
              class='is-enable-group'
              label={t('是否启用')}
              property='is_enable'
              required
            >
              <bk-radio-group
                data-test-id='basicInformation_radio_whetherToEnable'
                value={formData.value.is_enable}
                onChange={val => (formData.value.is_enable = val)}
              >
                <bk-radio
                  style='margin-right: 16px'
                  value={true}
                >
                  {t('是')}
                </bk-radio>
                <bk-radio value={false}>{t('否')}</bk-radio>
              </bk-radio-group>
            </bk-form-item>
          </bk-form>
        </article>

        {/* 链路中转机 */}
        <article
          class='article'
          data-test-id='extractLinkCreateBox_article_linkTransfer'
        >
          <h3 class='title'>{t('链路中转机')}</h3>
          <div class='custom-form'>
            <div class='custom-label'>{t('中转机')}</div>
            <div class='custom-content'>
              {/* 中转机主机列表 */}
              <ul
                ref={hostListRef}
                class='host-list'
              >
                {/* 表头 */}
                <li class='host-item header'>
                  <div
                    class='min-box dir-container'
                    title={t('挂载目录')}
                  >
                    {t('挂载目录')}
                  </div>
                  <div
                    class='min-box id-container'
                    title={t('主机管控区域ID')}
                  >
                    {t('主机管控区域ID')}
                  </div>
                  <div
                    class='min-box ip-container'
                    title={t('主机IP')}
                  >
                    {t('主机IP')}
                  </div>
                  <div
                    class='min-box operation-container'
                    title={t('操作')}
                  >
                    {t('操作')}
                  </div>
                </li>

                {/* 列表内容 */}
                {formData.value.hosts.map((item: any, index: number) => (
                  <li
                    key={item.keyId}
                    class='host-item'
                  >
                    <div class='min-box dir-container'>
                      <bk-input
                        class='king-input'
                        value={item.target_dir}
                        onBlur={(e: any) => handleInputBlur(item.target_dir, e)}
                        onChange={val => (item.target_dir = val)}
                      />
                    </div>
                    <div class='min-box id-container'>
                      <bk-input
                        class='king-input'
                        value={item.bk_cloud_id}
                        onBlur={(e: any) => handleInputBlur(item.bk_cloud_id, e)}
                        onChange={val => (item.bk_cloud_id = val)}
                      />
                    </div>
                    <div class='min-box ip-container'>
                      <bk-input
                        class='king-input'
                        value={item.ip}
                        onBlur={(e: any) => handleInputBlur(item.ip, e)}
                        onChange={val => (item.ip = val)}
                      />
                    </div>
                    <div class='min-box operation-container'>
                      <bk-button
                        style='padding: 0'
                        disabled={formData.value.hosts.length === 1}
                        size='small'
                        text
                        onClick={() => deleteHost(index)}
                      >
                        {t('删除')}
                      </bk-button>
                    </div>
                  </li>
                ))}
              </ul>

              {/* 添加中转机按钮 */}
              <bk-button
                class='king-button'
                onClick={addHost}
              >
                {t('添加链路中转机')}
              </bk-button>
            </div>
          </div>
        </article>

        {/* 提交按钮 */}
        <bk-button
          style='width: 86px'
          data-test-id='basicInformation_button_submitFrom'
          loading={submitLoading.value}
          theme='primary'
          onClick={submitForm}
        >
          {t('提交')}
        </bk-button>
      </div>
    );
  },
});
