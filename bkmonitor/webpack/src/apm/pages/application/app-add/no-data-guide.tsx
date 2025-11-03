/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { applicationInfoByAppName, metaConfigInfo, pushUrl, queryBkDataToken } from 'monitor-api/modules/apm_meta';
import { copyText } from 'monitor-common/utils/utils';
import Collapse from 'monitor-pc/components/collapse/collapse';
import svgIcon from 'monitor-pc/components/svg-icon/svg-icon.vue';
import MarkdowViewer from 'monitor-ui/markdown-editor/viewer';

import * as authorityMap from '../../home/authority-map';
import SelectCardItem from './select-card-item';
import { type ICardItem, type IListDataItem, SystemData } from './utils';

import './no-data-guide.scss';

interface IProps {
  appName: string; // 应用名
  type: 'noData' | 'service'; // 应用无数据 | 新增服务
}
interface IPushUrlItem {
  bk_cloud_alias?: string;
  bk_cloud_id: number;
  push_url: string;
  tags: string[];
}
@Component({
  components: {
    svgIcon,
  },
})
export default class NoDataGuide extends tsc<IProps> {
  @Prop({ type: String, default: 'noData' }) type: IProps['type'];
  /** 应用名 */
  @Prop({ type: String, default: '' }) appName: IProps['appName'];
  /** 插件id */

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  loading = false;

  expandStepTips = true;

  showSecureKey = true;

  /** 无数据指引提示 */
  stepTipsList = [
    {
      message: window.i18n.t('当前页面暂无数据显示，你可以跟随安装指引将应用安装至你的网站。'),
    },
    {
      message: window.i18n.t('假如数据一直未能显示，请联系平台管理员。'),
    },
  ];

  /** md文档说明 */
  mdData = '';
  /** 秘钥 */
  secureKey = '';
  pushUrl: IPushUrlItem[] = [];
  secureKeyLoading = false;

  /** 语言环境实例 */
  systemData: SystemData = null;

  /** 选择环境的渲染数据 */
  systemDataList: IListDataItem[] = [];

  /** 应用信息 */
  appInfo = null;

  /** 配置说明折叠 */
  isCollapse = false;

  pluginId = '';

  async created() {
    this.loading = true;
    await this.getMdData();
    await this.getPushUrl();
    this.loading = false;
  }

  @Watch('appName', { immediate: true })
  handleAppNameChange(val: string) {
    if (val) {
      this.getAppInfo();
    }
  }

  /**
   * 通过app name来获取应用的信息
   */
  async getAppInfo() {
    this.appInfo = await applicationInfoByAppName({ app_name: this.appName });
  }

  /** 获取环境 语言 md文档等信息 */
  async getMdData() {
    const data = await metaConfigInfo().catch(() => null);
    this.systemData = new SystemData(data);
    this.systemDataList = this.systemData.addAppSystemData;
    // 默认选中第一个插件
    this.systemDataList[0].list[0].checked = true;
    this.pluginId = data.plugins[0].id;
  }

  /** 获取push url数据 */
  async getPushUrl() {
    const data = await pushUrl().catch(() => []);
    this.pushUrl = data || [];
  }

  /** 处理展开说明 */
  handleExpandStepTips() {
    this.expandStepTips = !this.expandStepTips;
  }

  /** 获取 secureKey */
  async handleGetSecureKey() {
    this.secureKeyLoading = true;
    this.secureKey = await queryBkDataToken(this.appInfo.application_id).catch(() => '');
    this.secureKeyLoading = false;
  }

  /** 拷贝操作 */
  handleCopy(text) {
    copyText(text, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  handleCheckedCardItem(cardItem: ICardItem, row: IListDataItem, val: boolean) {
    if (cardItem.theme === 'plugin') {
      this.pluginId = val ? cardItem.id : '';
    }
    !row.multiple && this.systemData.handleRowChecked(row);
    cardItem.checked = val;
    const isPass = this.systemData.validate(this.systemData.addAppSystemData);
    if (isPass) {
      this.mdData = this.systemData.getMdString(this.pluginId);
    } else {
      this.mdData = '';
    }
  }
  render() {
    const rowContent = (name: string, content, className?: string) => (
      <div class={['row-content-wrap', className]}>
        {!!name && (
          <div
            class={['row-title', { 'can-collapse': false }]}
            // onClick={() => {
            //   if (this.type === 'noData') {
            //     this.isCollapse = !this.isCollapse;
            //   }
            // }}
          >
            <i class={['icon-monitor icon-mc-triangle-down', { 'is-collapse': this.isCollapse }]} />
            {name}
          </div>
        )}
        {!this.isCollapse && <div class='row-content'>{content}</div>}
      </div>
    );
    /** 一行卡片 */
    const cardList = (list: ICardItem[], row: IListDataItem) =>
      list.map(
        cardItem =>
          !cardItem.hidden && (
            <SelectCardItem
              class='system-select-list-item'
              checked={cardItem.checked}
              descData={cardItem.descData}
              img={cardItem.img}
              mode='small'
              multiple={row.multiple}
              theme={cardItem.theme}
              title={cardItem.title}
              onClick={() => this.handleCheckedCardItem(cardItem, row, !cardItem.checked)}
            />
          )
      );
    return (
      <div
        class={['no-data-guide-wrap', { 'is-service': this.type === 'service' }]}
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='no-data-guide-header'>{this.$tc('配置与流程指引')}</div>
        <div class='no-data-guide-main'>
          {this.type === 'noData' && (
            <div class='no-data-guide-alert'>
              <div class='step-tips-wrap'>
                <Collapse
                  defaultHeight={56}
                  expand={this.expandStepTips}
                  maxHeight={96}
                  needCloseButton={false}
                  renderAnimation={false}
                >
                  <div class='step-tips-content'>
                    {this.stepTipsList.map((item, index) => (
                      <div
                        key={index}
                        class='step-tips-item'
                      >
                        <span>{index + 1}.</span>
                        <span>{item.message}</span>
                      </div>
                    ))}
                  </div>
                </Collapse>
                <div class='step-tips-btn-row'>
                  <span
                    class='step-tips-btn'
                    onClick={this.handleExpandStepTips}
                  >
                    <span>{this.$t(this.expandStepTips ? '收起' : '展开')}</span>
                    <i class={['icon-monitor icon-arrow-up', { 'is-hidden': !this.expandStepTips }]} />
                  </span>
                </div>
              </div>
            </div>
          )}
          <div class={['config-content', { 'is-service': this.type === 'service' }]}>
            {rowContent(
              this.$tc('配置信息'),
              <div class='config-row'>
                <div class='config-item'>
                  <span class='config-label'>Token</span>
                  <span class='config-value'>
                    {(this.showSecureKey ? this.secureKey : '********') || '●●●●●●●●●●'}
                    {!this.secureKey ? (
                      <span class={['handle-btn', { 'btn-loading': this.secureKeyLoading }]}>
                        <span class='loading' />
                        <span
                          class='handle-text'
                          v-authority={{ active: !this.authority.MANAGE_AUTH }}
                          onClick={() => {
                            this.authority
                              ? this.handleGetSecureKey()
                              : this.handleShowAuthorityDetail(authorityMap.MANAGE_AUTH);
                          }}
                        >
                          {this.$t('点击查看')}
                        </span>
                      </span>
                    ) : (
                      <span>
                        {this.showSecureKey && (
                          <i
                            class='icon-monitor icon-mc-copy copy-icon'
                            onClick={() => this.handleCopy(this.secureKey)}
                          />
                        )}
                      </span>
                    )}
                    {this.secureKey && (
                      <i
                        class={`bk-icon toggle-icon ${this.showSecureKey ? 'icon-eye-slash' : 'icon-eye'}`}
                        onClick={() => {
                          this.showSecureKey = !this.showSecureKey;
                        }}
                      />
                    )}
                  </span>
                </div>
                <div class='config-item pushUrl-item'>
                  <span class='config-label'>Push URL</span>
                  <span class='config-value'>
                    {this.pushUrl.map(item => (
                      <span
                        key={item.push_url}
                      >{`${item.bk_cloud_alias || this.$t('管控区域')} ${item.push_url} [${item.tags.join(
                        ','
                      )}]`}</span>
                    ))}
                  </span>
                </div>
              </div>
            )}
            {rowContent(
              this.$tc('配置选择'),
              !this.isCollapse && (
                <div class='select-view-content'>
                  <div class='select-lang-system'>
                    {/* 选择环境 and 语言 */}
                    {this.systemDataList.map((item, index) => (
                      <div
                        key={index}
                        class={['system-select-row']}
                      >
                        <div class={['system-select-title', { 'has-child': !!item.children?.length }]}>
                          {item.title}
                        </div>
                        <div class='system-select-content'>
                          {!!item.list?.length && (
                            <div class='system-select-list-wrap'>
                              <div class='system-select-list'>{!!item.list && cardList(item.list, item)}</div>
                            </div>
                          )}
                          {!!item.children?.length &&
                            item.children.map(child =>
                              child.list.length ? (
                                <div
                                  key={child.title}
                                  class='system-select-row-child'
                                >
                                  <div class='child-title'>{child.title}</div>
                                  <div class='system-select-list-wrap'>
                                    <div class='system-select-list'>
                                      {!!child.list?.length && cardList(child.list, child)}
                                    </div>
                                  </div>
                                </div>
                              ) : undefined
                            )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            )}
            {rowContent(
              this.$tc('流程指引'),
              <div class='view-main'>
                {this.mdData ? (
                  <MarkdowViewer
                    class='md-viwer'
                    flowchartStyle={true}
                    value={this.mdData}
                  />
                ) : (
                  <bk-exception
                    scene='part'
                    type='empty'
                  >
                    {this.$t('选择语言和环境')}
                  </bk-exception>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
