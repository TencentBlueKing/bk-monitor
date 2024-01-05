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
import { defineComponent, PropType, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Exception, Select } from 'bkui-vue';
import { Spinner, Upload as UploadIcon } from 'bkui-vue/lib/icon';

import { ConditionType, RetrievalFormData } from '../typings';

import ProfilingFileUpload from './profiling-file-upload';

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
  setup(_props, { emit }) {
    const { t } = useI18n();
    function handleShowFileDetail(item) {
      emit('showFileDetail', item);
    }

    const uploadDialogShow = ref(false);
    const active = ref<ConditionType>(ConditionType.Where);
    const selectFile = ref(null);

    /* 查询项 */
    const searchObj = reactive({
      selectFile: '',
      list: [
        {
          id: '1',
          name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
          status: 'running'
        },
        {
          id: '2',
          name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
          status: 'success'
        },
        {
          id: '3',
          name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
          status: 'failed'
        }
      ]
    });
    /* 对比项 */
    const compareObj = reactive({
      selectFile: '',
      list: [
        {
          id: '1',
          name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
          status: 'running'
        },
        {
          id: '2',
          name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
          status: 'success'
        },
        {
          id: '3',
          name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
          status: 'failed'
        }
      ]
    });

    function handleUploadTypeChange(type: ConditionType) {
      active.value = type;
    }

    function handleUploadShowChange(v: boolean) {
      uploadDialogShow.value = v;
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
      handleUploadTypeChange,
      handleUploadShowChange,
      statusRender,
      handleShowFileDetail
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
            {this.formData.isComparison && <div class='label where'>{this.t('查询项')}</div>}
            <Select
              v-model={this.searchObj.selectFile}
              popoverOptions={{
                extCls: 'upload-select-popover'
              }}
            >
              {this.searchObj.list.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                >
                  <div class='upload-select-item'>
                    <div class='left'>
                      {this.statusRender(item.status)}
                      <div class='divider'></div>
                      <div class='name'>{item.name}</div>
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
          {this.formData.isComparison && (
            <div class='file-select'>
              {this.formData.isComparison && <div class='label comparison'>{this.t('对比项')}</div>}
              <Select
                v-model={this.compareObj.selectFile}
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
                        <div class='name'>{item.name}</div>
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
          <Exception
            class='loading-wrap'
            type='search-empty'
          >
            <div class='text'>{this.t('文件解析中')}</div>
            <div class='desc'>{this.t('文件解析可能耗费较长时间，可先选择已解析文件查看')}</div>
          </Exception>
        </div>

        <ProfilingFileUpload
          show={this.uploadDialogShow}
          isCompare={this.formData.isComparison}
          onShowChange={this.handleUploadShowChange}
        ></ProfilingFileUpload>
      </div>
    );
  }
});
