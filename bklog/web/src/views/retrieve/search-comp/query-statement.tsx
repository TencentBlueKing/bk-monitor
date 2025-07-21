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

import { Popover } from 'bk-magic-vue';
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './query-statement.scss';

const searchTypeList = ['Lucene', 'UI'];

@Component
export default class QueryStatement extends tsc<object> {
  @Prop({ default: () => [], type: Array }) historyRecords;
  @Prop({ required: true, type: Boolean }) isSqlSearchType: boolean;
  @Prop({ required: true, type: Boolean }) isShowUiType: boolean;
  @Prop({ required: true, type: Boolean }) isCanUseUiType: boolean;

  popoverInstance = null;
  activeSearchType = 'Lucene';
  docCenterUrl = window.BK_DOC_QUERY_URL;
  tips = {
    allowHtml: true,
    content: '#retrieve-help-tips-content',
    distance: 9,
    placement: 'bottom-start',
    theme: 'light',
    trigger: 'mouseenter',
  };

  @Watch('isSqlSearchType')
  watchSearchType(value) {
    this.activeSearchType = value ? 'Lucene' : 'UI';
  }

  @Emit('clickSearchType')
  handleClickSearchType() {}

  handleClickHistory(item) {
    this.$emit(
      'updateSearchParam',
      item.params.keyword,
      item.params.addition,
      item.params.ip_chooser
    );
    this.$nextTick(() => {
      this.$emit('retrieve');
      this.popoverInstance?.destroy();
    });
  }

  handleClickHistoryButton(e) {
    const popoverWidth = (this.$refs.tabTitleRef as any)?.clientWidth || 'auto';
    this.popoverInstance = this.$bkPopover(e.target, {
      arrow: true,
      content: this.$refs.historyUlRef,
      duration: [275, 0],
      extCls: 'retrieve-history-popover',
      interactive: true,
      onHidden: () => {
        this.popoverInstance?.destroy();
        this.popoverInstance = null;
      },
      placement: 'bottom-end',
      sticky: true,
      theme: 'light',
      trigger: 'manual',
      width: popoverWidth,
    });
    this.popoverInstance.show();
  }

  handleChangeSearchType(item: string) {
    // 如果当前为sql模式，且检索的keywords和收藏的keywords不一致 则不允许切换
    if (this.isSqlSearchType && !this.isCanUseUiType) return;
    this.activeSearchType = item;
    this.handleClickSearchType();
  }

  render() {
    return (
      <div class="retrieve-tab-item-title-old" ref="tabTitleRef">
        <div class="flex-div">
          {this.$t('查询语句')}
          <span class="bklog-icon bklog-help" v-bk-tooltips={this.tips}></span>
          <div id="retrieve-help-tips-content">
            <div>
              {this.$t('可输入DSL语句进行快速查询')}
              <a
                class="tips-link"
                onClick={() => this.handleGotoLink('queryString')}
              >
                {this.$t('查看语法')}
                <span class="bklog-icon bklog-lianjie"></span>
              </a>
            </div>
            <div class="title">{this.$t('精确匹配(支持AND、OR)：')}</div>
            <div class="detail">author:"John Smith" AND age:20</div>
            <div class="title">{this.$t('字段名匹配(*代表通配符)：')}</div>
            <div class="detail">status:active</div>
            <div class="detail">title:(quick brown)</div>
            <div class="title">{this.$t('字段名模糊匹配：')}</div>
            <div class="detail">vers\*on:(quick brown)</div>
            <div class="title">{this.$t('通配符匹配：')}</div>
            <div class="detail">{'qu?ck bro*'}</div>
            <div class="title">{this.$t('正则匹配：')}</div>
            <div class="detail">{'name:/joh?n(ath[oa]n)/'}</div>
            <div class="title">{this.$t('范围匹配：')}</div>
            <div class="detail">{'count:[1 TO 5]'}</div>
            <div class="detail">{'count:[1 TO 5}'}</div>
            <div class="detail">{'count:[10 TO *]'}</div>
          </div>
          <Popover
            disabled={this.isCanUseUiType || !this.isSqlSearchType}
            tippy-options={{
              placement: 'top',
              theme: 'light',
              trigger: 'mouseenter',
            }}
            v-show={this.isShowUiType}
          >
            <div class="search-type-switch" v-show={this.isShowUiType}>
              {searchTypeList.map((item) => (
                <span
                  class={{ active: this.activeSearchType === item }}
                  onClick={() => this.handleChangeSearchType(item)}
                >
                  {item}
                </span>
              ))}
            </div>
            <div slot="content">
              <span
                class="bk-icon icon-exclamation-circle-shape"
                style="color: #d7473f; display: inline-block; transform: translateY(-2px);"
              ></span>
              <span>{this.$t('收藏的内容已修改，不能切回表单模式')}</span>
            </div>
          </Popover>
        </div>
        <div>
          {/* 历史记录 */}
          <div class="history-button">
            <span class="bklog-icon bklog-lishijilu"></span>
            <span onClick={this.handleClickHistoryButton}>
              {this.$t('查询历史')}
            </span>
          </div>
          <div v-show={false}>
            <ul class="retrieve-history-list" ref="historyUlRef">
              {this.historyRecords.length ? (
                this.historyRecords.map((item) => (
                  <li
                    class="list-item"
                    key={item.id}
                    onClick={() => this.handleClickHistory(item)}
                  >
                    <div
                      class="item-text text-overflow-hidden"
                      v-bk-overflow-tips={{ placement: 'right' }}
                    >
                      {item.query_string}
                    </div>
                  </li>
                ))
              ) : (
                <li class="list-item not-history">{this.$t('暂无历史记录')}</li>
              )}
            </ul>
          </div>
        </div>
      </div>
    );
  }
}
