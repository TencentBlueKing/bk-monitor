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
import { defineComponent, PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { Form, Sideslider } from 'bkui-vue';

import { DetailType, ServicesDetail } from '../typings';

import './profiling-detail.scss';

export default defineComponent({
  props: {
    detailType: {
      type: String as PropType<DetailType>,
      default: DetailType.Application
    },
    detailData: {
      type: Object as PropType<ServicesDetail>,
      default: () => null
    },
    show: {
      type: Boolean,
      default: false
    }
  },
  emits: ['showChange'],
  setup(props, { emit }) {
    const { t } = useI18n();

    function handleShowChange(val: boolean) {
      emit('showChange', val);
    }

    return {
      t,
      handleShowChange
    };
  },
  render() {
    return (
      <>
        <Sideslider
          isShow={this.show}
          onUpdate:isShow={this.handleShowChange}
          quick-close
          width={400}
          ext-cls='profiling-detail-sideslider'
        >
          {{
            header: () => (
              <div class='profiling-detail-header'>
                <span class='title'>{this.t('基础信息')}</span>
                <span class='jump-link'>
                  {this.t('Profile 接入文档')}
                  <i class='icon-monitor icon-fenxiang'></i>
                </span>
              </div>
            ),
            default: () => (
              <div class='profiling-detail-content'>
                {this.detailType === DetailType.Application ? (
                  this.detailData && (
                    <Form labelWidth={144}>
                      <Form.FormItem label={`${this.t('模块名称')}:`}>{this.detailData.service_name}</Form.FormItem>
                      <Form.FormItem label={`${this.t('所属应用')}:`}>
                        {this.detailData.app_name}
                        <span class='jump-link'>
                          {this.t('应用详情')}
                          <i class='icon-monitor icon-fenxiang'></i>
                        </span>
                      </Form.FormItem>
                      <Form.FormItem label={`${this.t('采样频率')}:`}>{this.detailData.frequency}</Form.FormItem>
                      <Form.FormItem label={`${this.t('上报数据类型')}:`}>***SDK</Form.FormItem>
                      <Form.FormItem label={`${this.t('SDK版本')}:`}>1.1.0</Form.FormItem>
                      <Form.FormItem label={`${this.t('数据语言')}:`}>java</Form.FormItem>
                      <Form.FormItem label={`${this.t('创建时间')}:`}>{this.detailData.create_time}</Form.FormItem>
                      <Form.FormItem label={`${this.t('最近上报时间')}:`}>
                        {this.detailData.last_report_time}
                      </Form.FormItem>
                    </Form>
                  )
                ) : (
                  <Form labelWidth={144}>
                    <Form.FormItem label={`${this.t('文件名称')}:`}>
                      Profile-2023-11-22-06-02-27.json （原文件名）
                    </Form.FormItem>
                    <Form.FormItem label={`${this.t('文件大小')}:`}>1.1 MB</Form.FormItem>
                    <Form.FormItem label={`${this.t('协议类型')}:`}>pprof</Form.FormItem>
                    <Form.FormItem label={`${this.t('解析状态')}:`}>
                      <div class='status'>
                        <div class='success circle'></div>
                        <span class='label'>{this.t('解析成功')}</span>
                        {/* {this.detailData.status === 'loading' && [
                          <Spinner class='loading'></Spinner>,
                          <span class='label'>{this.t('解析中')}</span>
                        ]}
                        {this.detailData.status === 'error' && [
                          <div class='error circle'></div>,
                          <span class='label'>{this.t('解析失败')}</span>
                        ]} */}
                      </div>
                    </Form.FormItem>
                    <Form.FormItem label={`${this.t('文件md5')}:`}>-</Form.FormItem>
                    <Form.FormItem label={`${this.t('上传人')}:`}>javanzhagn</Form.FormItem>
                    <Form.FormItem label={`${this.t('上传时间')}:`}>2023-10-31 12:49:34</Form.FormItem>
                  </Form>
                )}
              </div>
            )
          }}
        </Sideslider>
      </>
    );
  }
});
