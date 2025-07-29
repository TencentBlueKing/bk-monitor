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
import { type PropType, defineComponent } from 'vue';

import { Form, Loading, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useDocumentLink } from '../../../hooks';
import { transformByte } from '../../../utils';
import { type FileDetail, type ServicesDetail, DetailType } from '../typings';

import './profiling-detail.scss';

export default defineComponent({
  props: {
    detailType: {
      type: String as PropType<DetailType>,
      default: DetailType.Application,
    },
    detailData: {
      type: Object as PropType<FileDetail | ServicesDetail>,
      default: () => null,
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['showChange'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const statusMap = {
      uploaded: {
        type: 'success',
        name: t('已上传'),
      },
      parsing_failed: {
        type: 'error',
        name: t('解析失败'),
      },
      parsing_succeed: {
        type: 'success',
        name: t('解析成功'),
      },
      store_succeed: {
        type: 'success',
        name: t('已存储'),
      },
      store_failed: {
        type: 'error',
        name: t('存储失败'),
      },
    };

    const { handleGotoLink } = useDocumentLink();

    function handleShowChange(val: boolean) {
      emit('showChange', val);
    }

    function handleViewAppDetail() {
      const hash = `#/apm/home?queryString=${props.detailData.app_name}`;
      const url = location.href.replace(location.hash, hash);
      window.open(url, '_self');
    }

    return {
      t,
      statusMap,
      handleShowChange,
      handleViewAppDetail,
      handleGotoLink,
    };
  },
  render() {
    const renderContent = () => {
      if (!this.detailData) return undefined;
      if (this.detailType === DetailType.Application) {
        const data = this.detailData as ServicesDetail;
        return (
          <Form labelWidth={144}>
            <Form.FormItem label={`${this.t('模块名称')}:`}>{data.name || '-'}</Form.FormItem>
            <Form.FormItem label={`${this.t('所属应用')}:`}>
              {data.app_name}
              <span
                class='jump-link'
                onClick={this.handleViewAppDetail}
              >
                {this.t('应用详情')}
                <i class='icon-monitor icon-fenxiang' />
              </span>
            </Form.FormItem>
            {/* <Form.FormItem label={`${this.t('采样频率')}:`}>{data.frequency || '-'}</Form.FormItem> */}
            {/* <Form.FormItem label={`${this.t('上报数据类型')}:`}>***SDK</Form.FormItem>
            <Form.FormItem label={`${this.t('SDK版本')}:`}>1.1.0</Form.FormItem>
            <Form.FormItem label={`${this.t('数据语言')}:`}>java</Form.FormItem> */}
            <Form.FormItem label={`${this.t('创建时间')}:`}>{data.create_time || '-'}</Form.FormItem>
            <Form.FormItem label={`${this.t('最近上报时间')}:`}>{data.last_report_time || '-'}</Form.FormItem>
          </Form>
        );
      }
      const data = this.detailData as FileDetail;
      return (
        <Form labelWidth={144}>
          <Form.FormItem label={`${this.t('文件名称')}:`}>
            {data.file_name} （{data.origin_file_name}）
          </Form.FormItem>
          <Form.FormItem label={`${this.t('文件大小')}:`}>{transformByte(data.file_size)}</Form.FormItem>
          <Form.FormItem label={`${this.t('协议类型')}:`}>{data.file_type || '-'}</Form.FormItem>
          <Form.FormItem label={`${this.t('解析状态')}:`}>
            <div class='status'>
              <div class={['circle', this.statusMap[data.status].type]} />
              <span class='label'>{this.statusMap[data.status].name}</span>
            </div>
          </Form.FormItem>
          <Form.FormItem label={`${this.t('文件md5')}:`}>{data.file_md5 || '-'}</Form.FormItem>
          <Form.FormItem label={`${this.t('上传人')}:`}>{data.operator || '-'}</Form.FormItem>
          <Form.FormItem label={`${this.t('上传时间')}:`}>{data.uploaded_time || '-'}</Form.FormItem>
          <Form.FormItem label={`${this.t('pprof文件时间')}:`}>{data.data_time || '-'}</Form.FormItem>
          {['parsing_failed', 'store_failed'].includes(data.status) && (
            <Form.FormItem label={`${this.t('错误信息')}:`}>{data.content || '-'}</Form.FormItem>
          )}
        </Form>
      );
    };

    return (
      <>
        <Sideslider
          width={400}
          ext-cls='profiling-detail-sideslider'
          isShow={this.show}
          quick-close
          onUpdate:isShow={this.handleShowChange}
        >
          {{
            header: () => (
              <div class='profiling-detail-header'>
                <span class='title'>{this.t('基础信息')}</span>
                <span
                  class='jump-link'
                  onClick={() => this.handleGotoLink('profiling_docs')}
                >
                  <span class='link'>{this.t('Profile 接入指引')}</span>
                  <i class='icon-monitor icon-fenxiang' />
                </span>
              </div>
            ),
            default: () => (
              <Loading loading={!this.detailData}>
                <div class='profiling-detail-content'>{renderContent()}</div>
              </Loading>
            ),
          }}
        </Sideslider>
      </>
    );
  },
});
