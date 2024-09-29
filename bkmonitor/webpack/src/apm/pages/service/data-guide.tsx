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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listApplication, metaConfigInfo, metaInstrumentGuides, pushUrl } from 'monitor-api/modules/apm_meta';
import { Debounce } from 'monitor-common/utils';
import MarkdownViewer from 'monitor-ui/markdown-editor/viewer';

import SelectCardItem from '../application/app-add/select-card-item';

import type { ICardItem } from '../application/app-add/utils';

import './data-guide.scss';
interface IProps {
  defaultAppName: string; // 应用名
}
@Component
export default class ServiceApply extends tsc<IProps> {
  @Prop({ type: String, default: '' }) defaultAppName: IProps['defaultAppName'];
  loading = false;
  /** 应用 */
  appName = '';
  appLoading = false;
  appList = [];
  /** 服务名称 */
  formData = {
    serviceName: 'test',
  };
  formRules = {
    serviceName: [{ required: true, message: '请输入服务名称', trigger: 'blur' }],
  };
  /** 语言列表 */
  languageList: ICardItem[] = [];
  languageLoading = false;
  /** 报表url列表 */
  reportUrlList = [];
  reportUrl = '';
  reportLoading = false;

  markdownStr = '';
  markdownLoading = false;

  guideUrl = '';
  created() {
    this.getAppList();
    this.getReportUrlList();
  }

  @Watch('defaultAppName', { immediate: true })
  handleAppNameChange(val: string) {
    if (val) {
      this.appName = val;
      this.getLanguageData();
    }
  }

  /** 获取应用列表 */
  async getAppList() {
    this.appLoading = true;
    const data = await listApplication().catch(() => ({
      data: [],
    }));
    this.appList = data.data.map(item => ({
      id: item.app_name,
      name: item.app_alias,
    }));
    this.appLoading = false;
  }

  /** 获取环境 语言 md文档等信息 */
  async getLanguageData() {
    this.languageLoading = true;
    const data = await metaConfigInfo()
      .then(data => {
        this.guideUrl = data?.setup?.guide_url?.access_url || '';
        return data;
      })
      .catch(() => {
        this.guideUrl = '';
        return {
          languages: [],
        };
      });
    this.languageList = (data.languages || []).map((item, index) => ({
      id: item.id,
      title: item.name,
      img: item.icon,
      checked: index === 0,
    }));
    this.languageLoading = false;
    console.log('🚀 ~ NoDataGuide ~ getLanguageData ~ data:', data);
    // this.languageList = data || [];
  }

  /** 获取push url数据 */
  async getReportUrlList() {
    this.reportLoading = true;
    this.reportUrlList = await pushUrl({
      format_type: 'simple',
    })
      .then(list => {
        return (list || []).map(item => ({
          id: item.push_url,
          name: `${this.$t('管控区域')} ${item.bk_cloud_id} ${item.push_url}`,
        }));
      })
      .catch(() => []);
    this.reportUrl = this.reportUrlList[0]?.id || '';
    this.reportLoading = false;
  }
  @Debounce(500)
  async getMarkdownStr() {
    this.markdownLoading = true;
    const lang = this.languageList.find(item => item.checked)?.id;
    const str = await metaInstrumentGuides({
      application_id: this.appName,
      languages: [lang],
      service_name: this.formData.serviceName,
    });
    this.markdownLoading = false;
  }
  @Debounce(300)
  handleServiceNameChange(v: string) {
    this.formData.serviceName = v?.trim();
    this.getMarkdownStr();
  }
  handleLanguageChange(language: ICardItem, val: boolean) {
    if (language.checked && !val) {
      return;
    }
    const checkLang = this.languageList.find(item => item.checked);
    if (checkLang) {
      checkLang.checked = false;
    }
    language.checked = val;
    this.getMarkdownStr();
  }
  render() {
    const rowContent = (name: string, content, subTitle?) => (
      <div class={['row-content-wrap']}>
        {!!name && (
          <div class={['row-title']}>
            {name}
            {subTitle}
          </div>
        )}
        {<div class='row-content'>{content}</div>}
      </div>
    );
    return (
      <div
        class='data-guide-wrap is-service'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='data-guide-main'>
          {rowContent(
            this.$tc('配置选择'),
            <div class='select-config-wrap'>
              <bk-form
                label-width={114}
                rules={this.formRules}
                {...{
                  props: {
                    model: this.formData,
                  },
                }}
              >
                <bk-form-item label={this.$tc('所属应用')}>
                  <bk-select
                    style='width:394px;'
                    clearable={false}
                    loading={this.appLoading}
                    searchable={true}
                    value={this.appName}
                  >
                    {this.appList.map(item => {
                      return (
                        <bk-option
                          id={item.id}
                          key={item.id}
                          name={item.name}
                        />
                      );
                    })}
                  </bk-select>
                </bk-form-item>
                <bk-form-item
                  class='service-name-form'
                  label={this.$tc('服务名')}
                  property='serviceName'
                  required
                >
                  <bk-input
                    style='width:394px;'
                    placeholder={this.$t('请输入服务名')}
                    value={this.formData.serviceName}
                    onChange={this.handleServiceNameChange}
                  />
                </bk-form-item>
                <bk-form-item label={this.$tc('选择语言')}>
                  <bk-input style='display: none' />
                  {!this.languageLoading ? (
                    this.languageList.map(item => {
                      return (
                        <SelectCardItem
                          key={item.id}
                          class='system-select-list-item'
                          checked={item.checked}
                          img={item.img}
                          mode='small'
                          title={item.title}
                          onClick={() => this.handleLanguageChange(item, !item.checked)}
                        />
                      );
                    })
                  ) : (
                    <div style='display: flex'>
                      {Array.of(1, 2, 3, 4).map((_, index) => (
                        <div
                          key={index}
                          style='width: 120px;height: 40px;margin-right: 16px;'
                          class='skeleton-element'
                        />
                      ))}
                    </div>
                  )}
                </bk-form-item>
                <bk-form-item label={this.$tc('默认上报地址')}>
                  <bk-select
                    style='width:580px;'
                    clearable={false}
                    loading={this.reportLoading}
                    searchable={true}
                    value={this.reportUrl}
                  >
                    {this.reportUrlList.map(item => {
                      return (
                        <bk-option
                          id={item.id}
                          key={item.id}
                          name={item.name}
                        />
                      );
                    })}
                  </bk-select>
                </bk-form-item>
              </bk-form>
            </div>
          )}

          <div class='config-content is-service'>
            {rowContent(
              this.$tc('上报示例'),
              <div class='view-main'>
                {this.markdownStr ? (
                  <MarkdownViewer
                    flowchartStyle={false}
                    value={this.markdownStr}
                  />
                ) : (
                  <bk-exception
                    scene='part'
                    type='empty'
                  >
                    {this.$t('请输入服务名')}
                  </bk-exception>
                )}
              </div>,

              this.guideUrl && (
                <bk-button
                  class='access-guide'
                  theme='primary'
                  onClick={() => window.open(this.guideUrl)}
                >
                  <i class='icon-monitor icon-mc-detail' />
                  {this.$tc('详情接入指引')}
                </bk-button>
              )
            )}
          </div>
        </div>
      </div>
    );
  }
}
