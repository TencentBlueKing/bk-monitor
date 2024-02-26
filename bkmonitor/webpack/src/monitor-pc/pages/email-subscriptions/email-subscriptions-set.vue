<!--
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
-->
<template>
  <div
    class="subscriptions-set-wrap"
    v-bkloading="{ isLoading }"
  >
    <!-- 基本信息 -->
    <div class="content-wrap">
      <div class="title-wrap">
        <span class="title">{{ $t('基本信息') }}</span>
      </div>
      <div class="content-main">
        <bk-form
          class="base-info-form"
          :rules="rules"
          :model="formData"
          ref="validateForm"
        >
          <bk-form-item
            :label="$t('邮件标题')"
            :required="true"
            :property="'mailTitle'"
            :error-display-type="'normal'"
          >
            <bk-input
              class="input"
              :placeholder="$t('输入邮件标题')"
              v-model="formData.mailTitle"
            />
          </bk-form-item>
          <bk-form-item
            :label="$t('订阅人')"
            :required="true"
            property="subscribe"
            :error-display-type="'normal'"
          >
            <div class="subscribe-item">
              <div class="subscribe-title">
                <bk-checkbox v-model="formData.receiversEnabled">
                  {{ $t('内部邮件') }}
                </bk-checkbox>
              </div>
              <div
                class="form-item-row"
                v-show="formData.receiversEnabled"
              >
                <!-- 人员选择器 -->
                <member-selector
                  style="width: 465px; height: 32px"
                  v-model="formData.receivers"
                  :group-list="memberGroupListFilter"
                />
              </div>
            </div>
            <div class="subscribe-item">
              <div class="subscribe-title">
                <bk-checkbox v-model="formData.channels[0].isEnabled">
                  {{ $t('外部邮件') }}
                </bk-checkbox>
                <span
                  v-show="formData.channels[0].isEnabled"
                  class="warning-hint"
                >
                  <i class="icon-monitor icon-remind" />
                  <span class="text">{{ $t("请遵守公司规范，切勿泄露敏感信息，后果自负！") }}</span>
                </span>
              </div>
              <div
                class="form-item-row"
                v-show="formData.channels[0].isEnabled"
              >
                <bk-input
                  style="width: 465px; height: 32px"
                  v-model="formData.channels[0].subscribers"
                  v-bk-tooltips.click="{
                    content: $t('多个邮箱使用逗号隔开'),
                    showOnInit: false,
                    duration: 200,
                    placements: ['right'],
                    theme: 'light'
                  }"
                >
                  <template slot="prepend">
                    <div class="group-text">
                      {{ $t('邮件列表') }}
                    </div>
                  </template>
                </bk-input>
              </div>
            </div>
            <div class="subscribe-item">
              <div class="subscribe-title">
                <bk-checkbox v-model="formData.channels[1].isEnabled">
                  {{ $t('企业微信群') }}
                </bk-checkbox>
              </div>
              <div
                class="form-item-row"
                v-show="formData.channels[1].isEnabled"
              >
                <bk-input
                  style="width: 465px; height: 32px"
                  v-model="formData.channels[1].subscribers"
                  v-bk-tooltips.click="{
                    content: wxworkBotTips,
                    showOnInit: false,
                    duration: 200,
                    placements: ['right'],
                    theme: 'light'
                  }"
                >
                  <template slot="prepend">
                    <div class="group-text">
                      {{ $t('群ID') }}
                    </div>
                  </template>
                </bk-input>
                <i
                  class="icon-monitor icon-mc-help-fill"
                  v-bk-tooltips="{
                    content: wxworkBotTips,
                    showOnInit: false,
                    duration: 200,
                    placements: ['right'],
                    allowHTML: false
                  }"
                />
              </div>
            </div>
          </bk-form-item>
          <bk-form-item
            :label="$t('管理员')"
            :required="true"
            :property="'managers'"
            :error-display-type="'normal'"
          >
            <div class="form-item-row">
              <!-- 人员选择器 -->
              <member-selector
                style="width: 465px; height: 32px"
                v-model="formData.managers"
                :group-list="memberGroupListFilter"
              />
              <i
                class="icon-monitor icon-tips"
                v-bk-tooltips="{
                  content: $t('可以对本订阅内容进行修改的人员'),
                  showOnInit: false,
                  duration: 200,
                  placements: ['top']
                }"
              />
              <div
                class="receiver-btn"
                ref="receiverTarget"
                @click="handleShowReceiver"
              >
                <i class="icon-monitor icon-audit" />
                <span class="text">{{ $t('订阅人员列表') }}</span>
              </div>
            </div>
          </bk-form-item>
          <bk-form-item
            :label="$t('发送频率')"
            :required="true"
          >
            <time-period v-model="formData.frequency" />
          </bk-form-item>
          <bk-form-item
            :label="$t('数据范围')"
            :required="true"
            property="timeRange"
            error-display-type="normal"
          >
            <bk-select
              class="time-range-select"
              v-model="formData.timeRange"
              :clearable="false"
            >
              <bk-option
                v-for="opt in timeRangeOption"
                :key="opt.id"
                :id="opt.id"
                :name="opt.name"
              />
            </bk-select>
          </bk-form-item>
          <!-- 订阅内容的校验替身 -->
          <bk-form-item
            ref="reportContentsFormItem"
            v-show="false"
            :required="true"
            :property="'reportContents'"
            :error-display-type="'normal'"
          />
        </bk-form>
      </div>
    </div>
    <div class="content-wrap mt24">
      <div
        class="title-wrap"
        style="margin-bottom: 8px;"
      >
        <span class="title">{{$t('订阅内容')}}</span>
        <div class="is-link-enabled">
          <span>{{ $t('是否附带链接') }}</span>
          <bk-switcher
            v-model="formData.isLinkEnabled"
            theme="primary"
            size="small"
          />
        </div>
      </div>
      <subscription-content
        :data="tableData"
        :content-type="contentType"
        @typeChange="(type) => handleTabChange(type)"
        @viewSort="(data) => formData.reportContents = data"
        @add="() => handleShowContent('add')"
        @del="index => handleDelContent(index)"
        @edit="({ row, index }) => handleShowContent('edit', row, index)"
      />
      <div
        class="errors-tips"
        v-if="errors && errors.field === 'reportContents'"
      >{{errors.content}}</div>
    </div>
    <div class="footer-wrap">
      <bk-button
        theme="primary"
        @click="handleSave"
        :loading="saveLoading"
      >{{ $t('保存') }}</bk-button>
      <bk-button
        v-bk-tooltips="{
          content: $t('往当前用户发送一封测试邮件'),
          placements: ['top']
        }"
        @click="handleTest"
        :loading="testLoading"
      >{{ $t('测试') }}</bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </div>
    <!-- 侧栏-添加内容 -->
    <add-content
      :content-type="contentType"
      :show.sync="showAddContent"
      :data="curEditContentData"
      :type="setType"
      @change="handleContentChange"
    />
    <!-- 测试提示 -->
    <monitor-dialog
      :need-footer="false"
      :need-header="false"
      :value.sync="showTips"
    >
      <div class="tips-content-wrap">
        <div class="tips-title-wrap">
          <span :class="['icon-monitor', tipsContent[tipsType].icon]" />
          <span class="tips-title">{{ tipsContent[tipsType].title }}</span>
        </div>
        <div class="tips-content">
          {{ tipsContent[tipsType].content }}
        </div>
      </div>
    </monitor-dialog>
    <!-- 接收人列表浮层 -->
    <receiver-list
      :show.sync="receiverList.show"
      :target="receiverTargetRef"
      :table-data="receiverListTableData"
      placement="bottom-start"
      :need-handle="true"
      :loading="receiverListLoading"
      @on-receiver="handleOnReciver"
    />
  </div>
</template>

<script lang="ts">
import VueI18n, { TranslateResult } from 'vue-i18n';
import { Component, Prop, Ref, Vue } from 'vue-property-decorator';

import Sortable from 'sortablejs';

import { getDashboardList } from '../../../monitor-api/modules/grafana';
import { getNoticeWay } from '../../../monitor-api/modules/notice_group';
import {
  groupList,
  reportContent,
  reportCreateOrUpdate,
  reportTest
} from '../../../monitor-api/modules/report';
import { deepClone, transformDataKey } from '../../../monitor-common/utils/utils';
import MonitorDialog from '../../../monitor-ui/monitor-dialog/monitor-dialog.vue';
import { SET_NAV_ROUTE_LIST } from '../../store/modules/app';
import memberSelector from '../alarm-group/alarm-group-add/member-selector.vue';

import addContent from './components/add-content.vue';
import ReceiverList from './components/receiver-list.vue';
import SubscriptionContent from './components/subscription-content';
import timePeriod from './components/time-period.vue';
import { IContentFormData, ITableColumnItem } from './types';
import { splitGraphId } from './utils';
/** 默认的图表数据时间范围 按照发送频率 */
const DEFAULT_TIME_RANGE = 'none';

interface IOption {
  id: string;
  name: string | TranslateResult;
}
interface ITimeRangeObj {
  timeLevel: 'minutes' | 'hours' | 'days';
  number: number;
}
/**
 * 邮件订阅新建/编辑页
 */
@Component({
  name: 'subscriptions-set',
  components: {
    timePeriod,
    addContent,
    MonitorDialog,
    memberSelector,
    ReceiverList,
    SubscriptionContent
  }
})
export default class SubscriptionsSet extends Vue {
  @Prop({ default: '', type: [Number, String] }) readonly id: number | string;
  @Ref('validateForm')readonly validateFormRef: any;
  @Ref('reportContentsFormItem')reportContentsFormItemRef: any;
  @Ref('receiverTarget')receiverTargetRef: Element;

  isLoading = false;
  saveLoading = false;
  testLoading = false;
  // 侧栏展示状态
  showAddContent = false;
  // 侧栏新增/编辑状态
  setType: 'add' | 'edit' = 'add';
  testVal: any = '';

  formData: any = {
    mailTitle: '',
    receivers: [],
    receiversEnabled: true,
    channels: [
      {
        channelName: 'email',
        isEnabled: false,
        subscribers: ''
      },
      {
        channelName: 'wxbot',
        isEnabled: false,
        subscribers: ''
      }
    ],
    managers: [],
    frequency: null,
    reportContents: [],
    fullReportContents: [], // 整屏截取数据
    timeRange: DEFAULT_TIME_RANGE, // 图表数据的时间范围
    isLinkEnabled: false // 是否附带链接
  };
  sortEndReportContents = [];
  curFromIndex = 0;

  rules: any = {
    mailTitle: [{ required: true, message: window.i18n.t('必填项'), trigger: 'none' }],
    subscribe: [
      {
        validator: this.checkSubscribe,
        message: window.i18n.t('必填项'), trigger: 'none'
      }
    ],
    managers: [{ validator(val) {
      return !!val.length;
    }, message: window.i18n.t('必填项'), trigger: 'none' }],
    timeRange: [
      {
        required: true,
        message: window.i18n.t('必填项'),
        trigger: 'none'
      }
    ]
  };
  errors: any = null;
  // 表格列数据
  tableColumnsMap: ITableColumnItem[] = [
    { label: window.i18n.t('子标题'), key: 'contentTitle' },
    { label: window.i18n.t('图表数量'), key: 'graphs', width: 150 },
    { label: window.i18n.t('布局'), key: 'rowPicturesNum', width: 150 },
    { label: window.i18n.t('说明'), key: 'contentDetails' }
  ];
  tableKey = 'tableKey';
  // 当前编辑的数据
  curEditContentData: IContentFormData = null;
  // 当前编辑数据索引
  curEditContentIndex: number = null;

  // 测试提示数据
  showTips = false;
  tipsType: 'success' | 'fail' = 'fail';
  tipsContent: any = {
    success: {
      icon: 'icon-mc-check-fill',
      title: window.i18n.t('发送测试邮件成功'),
      content: window.i18n.t('邮件任务已生成，请一分钟后到邮箱查看')
    },
    fail: {
      icon: 'icon-mc-close-fill',
      title: window.i18n.t('测试邮件发送失败'),
      content: window.i18n.t('您好，订阅邮件模板发送失败，请稍后重试！')
    }
  };

  // 人员数据
  memberList: any = [];
  // 接收人数据
  receiverList: any = {
    show: false
  };
  // 接收用户数据
  receiversUser: any = [];
  // 所有receiver数据
  receivers: any = [];
  receiverListLoading = false;
  contentType = 'view';

  /** 时间范围可选项 */
  timeRangeOption: IOption[] = [
    {
      id: 'none',
      name: window.i18n.t('按发送频率')
    },
    {
      id: '5minutes',
      name: window.i18n.t('近{n}分钟', { n: 5 })
    },
    {
      id: '15minutes',
      name: window.i18n.t('近{n}分钟', { n: 15 })
    },
    {
      id: '30minutes',
      name: window.i18n.t('近{n}分钟', { n: 30 })
    },
    {
      id: '1hours',
      name: window.i18n.t('近{n}小时', { n: 1 })
    },
    {
      id: '3hours',
      name: window.i18n.t('近{n}小时', { n: 3 })
    },
    {
      id: '6hours',
      name: window.i18n.t('近{n}小时', { n: 6 })
    },
    {
      id: '12hours',
      name: window.i18n.t('近{n}小时', { n: 12 })
    },
    {
      id: '24hours',
      name: window.i18n.t('近{n}小时', { n: 24 })
    },
    {
      id: '2days',
      name: window.i18n.t('近 {n} 天', { n: 2 })
    },
    {
      id: '7days',
      name: window.i18n.t('近 {n} 天', { n: 7 })
    },
    {
      id: '30days',
      name: window.i18n.t('近 {n} 天', { n: 30 })
    }
  ];

  noticeWayList = [];

  get receiverListTableData() {
    const groupList = this.memberList.find(item => item.id === 'group')?.children || [];
    let list = [];
    if (this.id) {
      // 编辑
      const receivers = [];
      this.formData.receivers.forEach((item) => {
        const res = groupList.find(set => item === set.id);
        res ? receivers.push(...res.children) : receivers.push(item);
      });
      receivers.forEach((item) => {
        const res = this.receiversUser.find(set => set.id === item);
        let temp = {};
        if (res) {
          const { createTime, isEnabled, lastSendTime } = res;
          temp = {
            name: item,
            createTime,
            isEnabled,
            lastSendTime
          };
        } else {
          temp = {
            name: item,
            createTime: '',
            isEnabled: null,
            lastSendTime: ''
          };
        }
        list.push(temp);
      });
    } else {
      const temp = [];
      this.formData.receivers.forEach((item) => {
        const res = groupList.find(set => item === set.id);
        if (res) {
          temp.push(...res.children);
        } else {
          temp.push(item);
        }
      });
      list = temp.map(item => ({
        name: item,
        createTime: '',
        isEnabled: null,
        lastSendTime: ''
      }));
    }
    return list;
  }


  get isSuperUser() {
    return this.$store.getters.isSuperUser;
  }

  get wxworkBotTips() {
    const name = this.noticeWayList.find(item => item.type === 'wxwork-bot')?.name || '';
    return this.$t('获取会话ID方法:<br/>1.群聊列表右键添加群机器人: {name}<br/>2.手动 @{name} 并输入关键字\'会话ID\'<br/>3.将获取到的会话ID粘贴到输入框，使用逗号分隔', { name });
  }

  // 人员数据筛选
  get memberGroupListFilter() {
    if (this.isSuperUser) {
      const temp = deepClone(this.memberList);
      const list = temp.filter(item => item.id === 'group');
      list.forEach((item) => {
        item.children = item.children.map((group) => {
          group.username = group.id;
          delete group.children;
          return group;
        });
      });
      return list;
    }
    return [];
  }
  get tableData() {
    const viewData = this.formData?.reportContents || [];
    const pullData = this.formData?.fullReportContents || [];
    return {
      viewData,
      pullData
    };
  }
  created() {
    this.updateNavData(this.id ? this.$tc('编辑') : this.$tc('新建订阅'));
    getNoticeWay().then((res) => {
      this.noticeWayList = res;
    })
      .catch(() => []);
    if (this.id) this.getEditInfo(this.id);
    // 获取通知对象数据
    // getReceiver({ bk_biz_id: 0 }).then((data) => {
    //   this.memberList = data
    // })
    groupList().then((data) => {
      this.memberList = [
        {
          id: 'group',
          display_name: this.$t('用户组'),
          children: data
        }
      ];
    });
  }
  /** 更新面包屑 */
  updateNavData(name: string | VueI18n.TranslateResult = '') {
    if (!name) return;
    const routeList = [];
    routeList.push({
      name,
      id: ''
    });
    this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
  }

  /**
   * 转换时间范围数据
   * @param timeRangeObj 接口数据
   */
  getTimeRange(timeRangeObj: ITimeRangeObj) {
    const { timeLevel, number } = timeRangeObj;
    return (timeLevel && number) ? `${number}${timeLevel}` : DEFAULT_TIME_RANGE;
  }
  /**
   * 转换成接口格式
   * @param str 时间范围字符串
   */
  getTimeRangeObj(str: string) {
    if (str === 'none') return undefined;
    let res: ITimeRangeObj = {
      timeLevel: 'hours',
      number: 24
    };
    const isMatch = str.match(/(\d+)(minutes|hours|days)/);
    if (isMatch) {
      const [, date, level] = isMatch;
      res = {
        timeLevel: level as ITimeRangeObj['timeLevel'],
        number: +date
      };
    }
    return transformDataKey(res, true);
  }

  /**
   * 校验是否有选择订阅人
   */
  checkSubscribe() {
    const { formData: { receivers, receiversEnabled, channels } } = this;
    // 必须勾选一种方式，且对应的方式必须有值
    return (receiversEnabled && receivers.length)
    || (channels[0].isEnabled && channels[0].subscribers.length)
    || (channels[1].isEnabled && channels[1].subscribers.length);
  }
  /**
   * 编辑信息
   */
  async getEditInfo(id) {
    this.isLoading = true;
    const res = await reportContent({ report_item_id: id }).catch(() => (false));
    if (!res) return;
    this.updateNavData(`${this.$t('编辑')} ${res.mail_title}`);
    const data = transformDataKey(res);
    this.formData.frequency = data.frequency;
    this.formData.mailTitle = data.mailTitle;
    this.formData.managers = data.managers.filter(item => !item.group).map(item => item.id);
    this.receivers = data.receivers;
    this.formData.reportItemId = data.id;
    this.formData.receiversEnabled = !!data.receivers.length;
    this.formData.isLinkEnabled = data.isLinkEnabled;
    if (data.channels && Object.keys(data.channels).length) {
      this.formData.channels = data.channels.map(({ subscribers, ...params }) => ({
        ...params,
        subscribers: subscribers.map(item => item.username).join(',')
      }));
    }
    // this.
    this.formData.timeRange = !!data.frequency.dataRange
      ? this.getTimeRange(data.frequency.dataRange)
      : DEFAULT_TIME_RANGE;
    this.getReceiverId(data.receivers);
    const graphsData = splitGraphId(data.contents[0].graphs[0]);
    const isFull = graphsData.panelId === '*';
    // 是否是整屏截取
    if (isFull) {
      this.contentType = 'full';
      const ids = Array.from<string>(new Set(data.contents.map(item => splitGraphId(item.graphs[0]).bizId)));
      this.formData.fullReportContents = data.contents.map((content) => {
        const { contentDetails, contentTitle, rowPicturesNum } = content;
        const graphData = splitGraphId(content.graphs[0]);
        return {
          contentDetails, contentTitle, rowPicturesNum,
          curBizId: graphData.bizId,
          curGrafana: graphData.dashboardId,
          curGrafanaName: ''
        };
      });
      this.setFullReportContents(ids);
    } else {
      this.contentType = 'view';
      this.formData.reportContents = data.contents;
      this.formData.reportContents.forEach((content) => {
        content.graphs = content.graphName.map(item => ({
          id: item.graphId,
          name: item.graphName
        }));
      });
    }
    this.isLoading = false;
  }
  /**
   * 仪表盘名称列的数据处理
   * @params ids 获取graphList的id参数集合
   * @description 通过bizId获取对应的仪表盘名称
   */
  async setFullReportContents(ids: string[]) {
    const graghsList = await this.getGraphsListByBiz(ids);
    this.formData.fullReportContents.forEach((item: any) => {
      const bizGraph = graghsList.find((graph) => {
        return graph[item.curBizId];
      });
      if (bizGraph) {
        item.curGrafanaName = bizGraph[item.curBizId].find(graph => graph.uid === item.curGrafana)?.text
        || item.curGrafana;
      }
    });
  }

  async getGraphsListByBiz(ids: string[]) {
    const promiseList = [];
    if (ids.length) {
      await Promise.all(ids.map(async (id) => {
        const graphBiziId = {};
        const res = await getDashboardList({ bk_biz_id: id }).catch(() => []);
        graphBiziId[id] = res;
        promiseList.push(graphBiziId);
      }));
    }
    return Promise.all(promiseList).catch(() => ([]));
  }

  // 更新本地接收人数据
  getReceiverId(receivers) {
    this.receivers = receivers;
    this.receiversUser = receivers.filter(item => item.type === 'user');
    this.formData.receivers = receivers
      .filter(item => !item.group)
      .filter(item => item.isEnabled)
      .map(item => item.id);
  }

  /**
   * 表格数据格式化
   * @params column 列数据column
   * @params cellValue 值
   */
  formatterColumn(row, column, cellValue) {
    if (column.property === 'layout') return cellValue + this.$t('个/行');
    if (column.property === 'graphs') return cellValue.length;
    return cellValue;
  }

  /**
   * 展开内容编辑侧栏
   * @params type 新增/编辑状态
   * @params row 行数据
   * @params index 数据索引
   */
  handleShowContent(type: 'add' | 'edit', row?: any, index?: number) {
    this.setType = type;
    if (type === 'edit') {
      this.curEditContentIndex = index;
      const temp = deepClone(row);
      this.curEditContentData = temp;
    } else if (type === 'add') {
      this.curEditContentData = null;
    }
    this.showAddContent = true;
  }

  /**
   * 内容值更新
   * @params data 编辑/新增更新的值
   */
  handleContentChange(data: IContentFormData) {
    // 清除订阅内容的错误信息
    this.reportContentsFormItemRef.handlerFocus();
    const temp = deepClone(data);
    if (this.contentType === 'view') {
      if (this.setType === 'edit') {
        this.formData.reportContents.splice(this.curEditContentIndex, 1, temp);
      } else if (this.setType === 'add') {
        this.formData.reportContents.push(temp);
      }
    }
    if (this.contentType === 'full') {
      if (this.setType === 'edit') {
        this.formData.fullReportContents.splice(this.curEditContentIndex, 1, temp);
      } else if (this.setType === 'add') {
        this.formData.fullReportContents.push(temp);
      }
    }
  }

  /**
   * 删除订阅内容
   * @params index 数据索引
   */
  handleDelContent(index: number) {
    if (this.contentType === 'view') {
      this.formData.reportContents.splice(index, 1);
    }
    if (this.contentType === 'full') {
      this.formData.fullReportContents.splice(index, 1);
    }
  }

  /**
   * 处理新增编辑接收人参数
   */
  getReceiversParams(receivers) {
    let res = [];
    const groupList = this.memberList.find(item => item.id === 'group')?.children || [];
    res = receivers.map((item) => {
      const flag = groupList.find(set => set.id === item);
      return {
        id: item,
        is_enabled: true,
        type: flag ? 'group' : 'user'
      };
    });
    this.receivers.forEach((item) => {
      if (item.group) {
        res.push({
          id: item.id,
          group: item.group,
          is_enabled: item.isEnabled,
          type: item.type
        });
      }
    });
    return res;
  }

  /**
   * 保存配置 新建/编辑
   */
  handleSave() {
    this.saveLoading = true;
    this.validateFormRef.validate().then(() => {
      if (!(this.formData.reportContents.length || this.formData.fullReportContents.length)) {
        this.errors = { field: 'reportContents', content: this.$t('必填项') };
        this.saveLoading = false;
        return;
      }
      this.errors = null;
      const groupList = this.memberList.find(item => item.id === 'group')?.children || [];
      let params = deepClone(this.formData);
      if (!params.receiversEnabled) params.receivers = [];
      delete params.receiversEnabled;
      params.receivers = this.getReceiversParams(params.receivers);
      params.managers = params.managers.map((item) => {
        const flag = groupList.find(set => set.id === item);
        return {
          id: item,
          type: flag ? 'group' : 'user'
        };
      });
      params.channels.forEach((channel) => {
        const subscribers = channel.subscribers.split(',');
        channel.subscribers = subscribers.reduce((pre, cur) => {
          if (cur.length) pre.push({ username: cur });
          return pre;
        }, []);
      });
      if (this.contentType === 'view') {
        params.reportContents.forEach((content) => {
          content.graphs = content.graphs.map(chart => chart.id);
        });
      }
      if (this.contentType === 'full') {
        params.reportContents = params.fullReportContents.map((content) => {
          const { contentDetails, contentTitle, rowPicturesNum, curBizId, curGrafana } = content;
          return {
            contentDetails,
            contentTitle,
            rowPicturesNum,
            graphs: [`${curBizId}-${curGrafana}-*`]
          };
        });
      }
      delete params.fullReportContents;
      params = transformDataKey(params, true);
      params.frequency.data_range = this.getTimeRangeObj(this.formData.timeRange);
      reportCreateOrUpdate(params).then(() => {
        this.$router.push({
          name: 'email-subscriptions'
        });
      })
        .finally(() => {
          this.saveLoading = false;
        });
    })
      .catch((err) => {
        console.log(err);
        this.errors = err;
        this.saveLoading = false;
      });
  }

  /**
   * 测试邮件
   */
  handleTest() {
    this.testLoading = true;
    this.validateFormRef.validate().then(() => {
      const {
        reportContents,
        fullReportContents,
        mailTitle,
        receivers,
        frequency,
        channels,
        receiversEnabled,
        isLinkEnabled
      } = deepClone(this.formData);
      // const groupList = this.memberList.find(item => item.id === 'group').children
      let params = {
        mail_title: mailTitle,
        receivers,
        channels,
        report_contents: reportContents,
        frequency: {
          ...frequency,
          data_range: this.getTimeRangeObj(this.formData.timeRange)
        },
        isLinkEnabled
      };
      if (!receiversEnabled) params.receivers = [];
      params.receivers = this.getReceiversParams(params.receivers);
      params.channels.forEach((channel) => {
        const subscribers = channel.subscribers.split(',');
        channel.subscribers = subscribers.reduce((pre, cur) => {
          if (cur.length) pre.push({ username: cur });
          return pre;
        }, []);
      });
      if (this.contentType === 'view') {
        params.report_contents.forEach((content) => {
          content.graphs = content.graphs.map(chart => chart.id);
        });
      } else if (this.contentType === 'full') {
        params.report_contents = fullReportContents.map((content) => {
          const { contentDetails, contentTitle, rowPicturesNum, curBizId, curGrafana } = content;
          return {
            contentDetails,
            contentTitle,
            rowPicturesNum,
            graphs: [`${curBizId}-${curGrafana}-*`]
          };
        });
      }
      params = transformDataKey(params, true);
      reportTest(params).then(() => {
        this.tipsType = 'success';
      })
        .catch(() => {
          this.tipsType = 'fail';
        })
        .finally(() => {
          this.showTips = true;
          this.testLoading = false;
        });
    })
      .catch((err) => {
        this.errors = err;
        this.testLoading = false;
      });
  }

  /**
   * 取消返回上一页
   */
  handleCancel() {
    this.$router.go(-1);
  }

  // 恢复订阅
  handleOnReciver(row) {
    if (!this.id) return;
    this.receiverListLoading = true;
    const receivers = deepClone(this.receivers);
    receivers.forEach(item => item.id === row.name && (item.isEnabled = !item.isEnabled));
    let params = {
      reportItemId: this.id,
      receivers
    };
    params = transformDataKey(params, true);
    reportCreateOrUpdate(params)
      .then(() => {
        this.getReceiverId(receivers);
        this.$bkMessage({ message: this.$t('订阅成功'), theme: 'success' });
      })
      .finally(() => (this.receiverListLoading = false));
  }

  /**
   * 表格行拖拽
   */
  rowDrop() {
    const tbody = document.querySelector('.drag-table-wrap .bk-table-body-wrapper tbody');
    Sortable.create(tbody, {
      onStart: ({ oldIndex: from }) => {
        this.curFromIndex = from;
      },
      onEnd: ({ newIndex: to, oldIndex: from }) => {
        if (to === from) return;
        this.formData.reportContents = deepClone(this.sortEndReportContents);
        this.tableKey = String(new Date());
        this.sortEndReportContents = [];
        this.$nextTick(() => {
          this.rowDrop();
        });
      },
      onChange: ({ newIndex: to }) => {
        const from = this.curFromIndex;
        this.sortEndReportContents = this.sortEndReportContents.length
          ? this.sortEndReportContents
          : deepClone(this.formData.reportContents);
        const temp = this.sortEndReportContents[to];
        this.sortEndReportContents[to] = this.sortEndReportContents[from];
        this.sortEndReportContents[from] = temp;
        this.curFromIndex = to;
      }
    });
  }

  handleShowReceiver() {
    this.receiverList.show = true;
  }
  handleTabChange(type: string) {
    this.contentType = type;
  }
}
</script>

<style lang="scss" scoped>
.subscriptions-set-wrap {
  margin: 24px;

  .content-wrap {
    padding: 22px 37px;
    background-color: #fff;
    border-radius: 2px;
    box-shadow: 0px 1px 2px 0px rgba(0, 0, 0, .05);

    .title-wrap {
      display: flex;
      align-items: center;

      .title {
        font-size: 12px;
        font-weight: 700;
        line-height: 16px;
        color: #63656e;
      }

      .add-btn {
        display: flex;
        align-items: center;
        margin-left: 34px;
        color: #3a84ff;
        cursor: pointer;

        .icon-mc-plus-fill {
          margin-right: 4px;
          font-size: 16px;
        }
      }
    }

    .base-info-form {
      margin-top: 26px;

      :deep(.bk-label-text) {
        font-size: 12px;
      }

      :deep(.bk-form-item) {
        &:not(:first-child) {
          margin-top: 18px;
        }
      }

      .input {
        width: 465px;
      }

      .bk-member-selector {
        width: 465px;
        min-height: 32px;

        .bk-selector-member {
          display: flex;
          align-items: center;
          padding: 0 10px;
        }

        .avatar {
          width: 22px;
          height: 22px;
          border: 1px solid #c4c6cc;
          border-radius: 50%;
        }

        :deep(.tag-list) {
          > li {
            height: 22px;
          }

          .no-img {
            margin-right: 5px;
            font-size: 22px;
            color: #979ba5;
            background: #fafbfd;
            border-radius: 16px;
          }

          .key-node {
            /* stylelint-disable-next-line declaration-no-important */
            background: none !important;

            /* stylelint-disable-next-line declaration-no-important */
            border: 0 !important;

            .tag {
              display: flex;
              align-items: center;
              height: 22px;
              background: none;

              .avatar {
                float: left;
                width: 22px;
                height: 22px;
                margin-right: 8px;
                vertical-align: middle;
                border: 1px solid #c4c6cc;
                border-radius: 50%;
              }
            }
          }
        }
      }

      .form-item-row {
        display: flex;
        align-items: center;

        .icon-tips,
        .icon-mc-help-fill {
          margin-left: 8px;
          font-size: 16px;
          color: #63656e;

          &:hover {
            color: #3a84ff;
          }
        }

        .receiver-btn {
          display: flex;
          align-items: center;
          height: 16px;
          margin-left: 18px;
          font-size: 0;
          color: #3a84ff;
          cursor: pointer;

          .icon-monitor {
            font-size: 14px;
          }

          .text {
            margin-left: 5px;
            font-size: 12px;
          }
        }
      }

      .time-range-select {
        width: 168px;
      }

      .subscribe-item {
        margin-bottom: 12px;

        :deep(.bk-checkbox-text) {
          font-size: 12px;
          line-height: 20px;
        }

        .subscribe-title {
          display: flex;
          align-items: center;
          margin-bottom: 6px;
          line-height: 20px;
        }

        .warning-hint {
          font-size: 0;
          color: #ea3636;

          i {
            display: inline-block;
            margin: 0 5px 0 17px;
            font-size: 14px;
            vertical-align: middle;
          }

          .text {
            display: inline-block;
            font-size: 12px;
            vertical-align: middle;
          }
        }
      }
    }

    .content-main {
      .drag-table-wrap {
        :deep(.sortable-chosen) {
          td {
            background-color: #eef5ff;
          }
        }
      }

      .icon-drag {
        position: relative;
        display: inline-block;
        height: 14px;
        cursor: move;

        &::after {
          position: absolute;
          top: 0;
          width: 2px;
          height: 14px;
          content: ' ';
          border-right: 2px dotted #979ba5;
          border-left: 2px dotted #979ba5;
        }
      }
    }

    .errors-tips {
      margin: 2px 0 0;
      font-size: 12px;
      line-height: 18px;
      color: #ea3636;
    }

    .is-link-enabled {
      display: flex;
      align-items: center;
      margin-left: 24px;

      .bk-switcher {
        margin-left: 8px;
      }
    }
  }

  .mt24 {
    margin-top: 24px;
  }

  .footer-wrap {
    display: flex;
    margin-top: 24px;

    & > :not(:last-child) {
      margin-right: 10px;
    }
  }

  .tips-content-wrap {
    padding-top: 3px;
    padding-bottom: 23px;

    .tips-title-wrap {
      margin-bottom: 7px;
      font-size: 0;

      /* stylelint-disable-next-line no-descending-specificity */
      .icon-monitor {
        margin-right: 7px;
        font-size: 18px;
      }

      .icon-mc-check-fill {
        color: #2dcb56;
      }

      .icon-mc-close-fill {
        color: #ea3636;
      }

      .tips-title {
        height: 21px;
        font-size: 16px;
        font-weight: 700;
        line-height: 21px;
        color: #313238;
        text-align: left;
      }
    }

    .tips-content {
      padding-left: 25px;
      font-size: 14px;
      line-height: 19px;
      color: #63656e;
      text-align: left;
    }
  }

  :deep(.monitor-dialog) {
    min-height: 112px;
  }
}
</style>
<style lang="scss">
.user-selector-container,
.user-selector-alternate-list-wrapper {
  .only-notice {
    display: flex;
    align-items: center;
    padding-left: 10px;
  }

  .only-img {
    margin-right: 5px;
    font-size: 22px;
    color: #979ba5;
    background: #fafbfd;
    border-radius: 16px;
  }
}
</style>
`
