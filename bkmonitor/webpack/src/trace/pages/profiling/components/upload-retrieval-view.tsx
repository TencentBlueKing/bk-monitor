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
import { computed, defineComponent, PropType, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Exception, Select } from 'bkui-vue';
import { Spinner, Upload as UploadIcon } from 'bkui-vue/lib/icon';

import { listProfileUploadRecord } from '../../../../monitor-api/modules/apm_profile';
import { ConditionType, RetrievalFormData } from '../typings';

import ProfilingFileUpload from './profiling-file-upload';
import ProfilingRetrievalView from './profiling-retrieval-view';

import './upload-retrieval-view.scss';

export default defineComponent({
  name: 'UploadRetrievalView',
  props: {
    formData: {
      type: Object as PropType<RetrievalFormData>,
      required: true
    }
  },
  emits: ['showFileDetail'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const uploadDialogShow = ref(false);
    const active = ref<ConditionType>(ConditionType.Where);
    const selectFile = ref(null);

    /* 查询项 */
    const searchObj = reactive({
      selectFile: '',
      list: []
    });
    /* 对比项   暂时不做 */
    const compareObj = reactive({
      selectFile: '',
      list: []
    });
    const loading = ref(false);

    const isCompare = computed(() => {
      return false;
      // return !!props.formData.isComparison;
    });

    init();

    /**
     * @description 初始化
     */
    async function init() {
      const data = await listProfileUploadRecord({
        app_name: props.formData.server.app_name,
        service_name: props.formData.server.service_name
      }).catch(() => []);
      searchObj.list = data;
      if (data.length) {
        searchObj.selectFile = data[0].id;
      }
    }

    function handleShowFileDetail(item) {
      emit('showFileDetail', item);
    }

    function handleUploadTypeChange(type: ConditionType) {
      active.value = type;
    }

    /**
     * @description 文件上传弹窗
     * @param v
     */
    function handleUploadShowChange(v: boolean) {
      uploadDialogShow.value = v;
    }

    function handleSelectFile(v) {
      searchObj.selectFile = v;
      loading.value = true;
      setTimeout(() => {
        loading.value = false;
      }, 3000);
    }

    function statusRender(status) {
      if (status === 'running') {
        return (
          <div class='status'>
            <Spinner class='loading'></Spinner>
            <span class='label'>{t('解析中')}</span>
          </div>
        );
      }
      if (status === 'success') {
        return (
          <div class='status'>
            <div class='success circle'></div>
            <span class='label'>{t('解析成功')}</span>
          </div>
        );
      }
      if (status === 'failed') {
        return (
          <div class='status'>
            <div class='error circle'></div>
            <span class='label'>{t('解析失败')}</span>
          </div>
        );
      }
    }

    return {
      t,
      uploadDialogShow,
      active,
      selectFile,
      searchObj,
      compareObj,
      loading,
      isCompare,
      handleUploadTypeChange,
      handleUploadShowChange,
      statusRender,
      handleShowFileDetail,
      handleSelectFile
    };
  },
  render() {
    return (
      <div class='upload-retrieval-view-component'>
        <div class='header-wrap'>
          <Button
            class='upload-btn'
            theme='primary'
            onClick={() => (this.uploadDialogShow = true)}
          >
            <UploadIcon class='upload-icon' />
            {this.t('上传文件')}
          </Button>

          <div class='file-select'>
            {this.isCompare && <div class='label where'>{this.t('查询项')}</div>}
            <Select
              modelValue={this.searchObj.selectFile}
              popoverOptions={{
                extCls: 'upload-select-popover'
              }}
              clearable={false}
              onSelect={v => this.handleSelectFile(v)}
            >
              {this.searchObj.list.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.app_name}
                >
                  <div class='upload-select-item'>
                    <div class='left'>
                      {this.statusRender(item.status)}
                      <div class='divider'></div>
                      <div class='name'>{item.app_name}</div>
                    </div>
                    <i
                      class='icon-monitor icon-mc-detail'
                      onClick={() => this.handleShowFileDetail(item)}
                    ></i>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </div>
          {this.isCompare && (
            <div class='file-select'>
              {this.isCompare && <div class='label comparison'>{this.t('对比项')}</div>}
              <Select
                modelValue={this.compareObj.selectFile}
                popoverOptions={{
                  extCls: 'upload-select-popover'
                }}
              >
                {this.compareObj.list.map(item => (
                  <Select.Option
                    id={item.id}
                    key={item.id}
                  >
                    <div class='upload-select-item'>
                      <div class='left'>
                        {this.statusRender(item.status)}
                        <div class='divider'></div>
                        <div class='name'>{item.app_name}</div>
                      </div>
                      <i class='icon-monitor icon-mc-detail'></i>
                    </div>
                  </Select.Option>
                ))}
              </Select>
            </div>
          )}
        </div>

        <div class='chart-wrap'>
          {this.loading || !this.searchObj.selectFile ? (
            <div class='exception-wrap'>
              <Exception
                class='loading-wrap'
                type='search-empty'
              >
                <div class='text'>
                  {!!this.searchObj.selectFile ? `${this.t('文件解析中')}...` : this.t('暂无数据')}
                </div>
                <div class='desc'>
                  {!!this.searchObj.selectFile
                    ? this.t('文件解析可能耗费较长时间，可先选择已解析文件查看')
                    : this.t('请上传文件后查看')}
                </div>
              </Exception>
            </div>
          ) : (
            <ProfilingRetrievalView></ProfilingRetrievalView>
          )}
        </div>

        <ProfilingFileUpload
          show={this.uploadDialogShow}
          appName={this.formData.server.app_name}
          isCompare={this.isCompare}
          onShowChange={this.handleUploadShowChange}
        ></ProfilingFileUpload>
      </div>
    );
  }
});
