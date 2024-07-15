<!-- eslint-disable vue/no-deprecated-slot-attribute -->
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
  <div class="finger-container">
    <div
      v-if="allFingerList.length"
      class="top-operate"
    >
      <p class="operate-message">
        <i18n
          v-if="selectList.length"
          path="当前已选择{0}条数据, 共有{1}条数据"
        >
          <span>{{ selectSize }}</span>
          <span>{{ allFingerList.length }}</span>
        </i18n>
        <i18n
          v-else
          path="共有{0}条数据"
        >
          <span>{{ allFingerList.length }}</span>
        </i18n>
      </p>
      <span
        v-if="selectList.length"
        class="operate-click"
        @click="handleBatchUseAlarm(true)"
        >{{ $t('批量使用告警') }}</span
      >
      <span
        v-if="selectList.length"
        class="operate-click"
        @click="handleBatchUseAlarm(false)"
        >{{ $t('批量停用告警') }}</span
      >
    </div>
    <bk-table
      ref="fingerTableRef"
      class="finger-cluster-table table-no-data"
      :data="fingerList"
      :outer-border="false"
      data-test-id="cluster_div_fingerTable"
      row-key="$index"
      reserve-selection
    >
      <bk-table-column
        width="50"
        :render-header="renderHeader"
      >
        <template #default="{ row }">
          <bk-checkbox
            :checked="getCheckedStatus(row)"
            :disabled="isRequestAlarm"
            @change="handleRowCheckChange(row, $event)"
          >
          </bk-checkbox>
        </template>
      </bk-table-column>

      <bk-table-column
        width="150"
        :label="$t('数据指纹')"
        :render-header="$renderHeader"
      >
        <template #default="{ row }">
          <div class="fl-ac signature-box">
            <span v-bk-overflow-tips>{{ row.signature }}</span>
            <div
              class="new-finger"
              v-show="row.is_new_class"
            >
              New
            </div>
          </div>
        </template>
      </bk-table-column>

      <bk-table-column
        :label="$t('数量')"
        :render-header="$renderHeader"
        :width="getTableWidth.number"
        prop="count"
        sortable
      >
        <template #default="{ row }">
          <span
            class="link-color"
            @click="handleMenuBatchClick(row)"
          >
            {{ row.count }}</span
          >
        </template>
      </bk-table-column>

      <bk-table-column
        :label="$t('占比')"
        :render-header="$renderHeader"
        :width="getTableWidth.percentage"
        prop="percentage"
        sortable
      >
        <template #default="{ row }">
          <span
            class="link-color"
            @click="handleMenuBatchClick(row)"
          >
            {{ `${toFixedNumber(row.percentage, 2)}%` }}
          </span>
        </template>
      </bk-table-column>

      <template v-if="requestData.year_on_year_hour >= 1">
        <bk-table-column
          :label="$t('同比数量')"
          :render-header="$renderHeader"
          :sort-by="'year_on_year_count'"
          :width="getTableWidth.year_on_year_count"
          align="center"
          header-align="center"
          sortable
        >
          <template #default="{ row }">
            <span>{{ row.year_on_year_count }}</span>
          </template>
        </bk-table-column>

        <bk-table-column
          :label="$t('同比变化')"
          :render-header="$renderHeader"
          :sort-by="'year_on_year_percentage'"
          :width="getTableWidth.year_on_year_percentage"
          align="center"
          header-align="center"
          sortable
        >
          <template #default="{ row }">
            <div class="fl-ac compared-change">
              <span>{{ `${toFixedNumber(row.year_on_year_percentage, 2)}%` }}</span>
              <span :class="['bk-icon', showArrowsClass(row)]"></span>
            </div>
          </template>
        </bk-table-column>
      </template>

      <bk-table-column
        class-name="symbol-column"
        label="Pattern"
        min-width="350"
      >
        <!-- eslint-disable-next-line -->
        <template slot-scope="{ row, $index }">
          <div class="pattern">
            <div :class="['pattern-content', { 'is-limit': getLimitState($index) }]">
              <cluster-event-popover
                :context="row.pattern"
                :tippy-options="{ distance: 10, placement: 'bottom', boundary: scrollContent }"
                @event-click="(option, isLink) => handleMenuClick(option, row, isLink)"
              >
                <text-highlight
                  style="word-break: break-all; white-space: pre-line"
                  class="monospace-text"
                  :queries="getHeightLightList(row.pattern)"
                >
                  {{ getHeightLightStr(row.pattern) }}
                </text-highlight>
              </cluster-event-popover>
              <template v-if="!isLimitExpandView">
                <p
                  v-if="!cacheExpandStr.includes($index)"
                  class="show-whole-btn"
                  @click.stop="handleShowWhole($index)"
                >
                  {{ $t('展开全部') }}
                </p>
                <p
                  v-else
                  class="hide-whole-btn"
                  @click.stop="handleHideWhole($index)"
                >
                  {{ $t('收起') }}
                </p>
              </template>
            </div>
          </div>
        </template>
      </bk-table-column>

      <template v-if="isGroupSearch">
        <bk-table-column
          v-for="(item, index) of requestData.group_by"
          width="130"
          :key="index"
          :label="item"
          :render-header="$renderHeader"
          class-name="symbol-column"
        >
          <template #default="{ row }">
            <div v-bk-overflow-tips>
              <span class="monospace-text">{{ row.group[index] }}</span>
            </div>
          </template>
        </bk-table-column>
      </template>

      <bk-table-column
        width="200"
        :label="$t('责任人')"
        :render-header="renderUserHeader"
      >
        <template #default="{ row }">
          <div
            v-bk-tooltips.top="{
              content: row.owners.join(', '),
              delay: 300,
              disabled: !row.owners.length,
            }"
          >
            <bk-user-selector
              style="margin-top: 4px"
              class="principal-input"
              :api="userApi"
              :empty-text="$t('无匹配人员')"
              :value="row.owners"
              placeholder=" "
              multiple
              @change="val => handleChangePrincipal(val, row)"
            >
            </bk-user-selector>
          </div>
        </template>
      </bk-table-column>

      <bk-table-column
        width="260"
        :label="$t('备注')"
        :render-header="renderRemarkHeader"
        align="center"
      >
        <template #default="{ row }">
          <div
            class="auto-height-container"
            @mouseenter="e => handleHoverRemarkIcon(e, row)"
          >
            <span class="auto-height">
              {{ remarkContent(row.remark) }}
            </span>
          </div>
        </template>
      </bk-table-column>

      <template
        v-if="fingerList.length && isPageOver"
        slot="append"
      >
        <clustering-loader :width-list="loaderWidthList" />
      </template>

      <template
        v-if="isShowBottomTips"
        slot="append"
      >
        <div class="bottom-tips">
          <i18n path="已加载完全部数据，如需查看更多查询条件可以{0}">
            <span @click="handleReturnTop">{{ $t('返回顶部') }}</span>
          </i18n>
        </div>
      </template>

      <template #empty>
        <div>
          <empty-status
            :show-text="false"
            empty-type="empty"
          >
            <div
              v-if="!clusterSwitch || !configData.extra.signature_switch"
              class="empty-text"
            >
              <p>{{ getLeaveText }}</p>
              <span
                class="empty-leave"
                @click="handleLeaveCurrent"
                >{{ $t('去设置') }}</span
              >
            </div>
            <p v-if="!fingerList.length && configData.extra.signature_switch">{{ $t('暂无数据') }}</p>
          </empty-status>
        </div>
      </template>
    </bk-table>

    <div v-show="false">
      <div
        id="remark-tips"
        ref="remarkTips"
      >
        <div
          class="remark-list"
          v-show="currentRemarkList.length"
        >
          <div
            v-for="(remark, index) in currentRemarkList"
            :key="index"
          >
            <div
              v-if="remark.username"
              class="user"
            >
              {{ remark.username }}
            </div>
            <div class="content">{{ remark.remark }}</div>
            <div class="tools">
              <span>{{ remark.showTime }}</span>
              <div
                v-if="remark.username === username"
                class="icon"
              >
                <i
                  class="bk-icon icon-edit-line"
                  @click="handleEditRemark(remark)"
                ></i>
                <i
                  class="bk-icon icon-delete"
                  @click="handleDeleteRemark(remark)"
                ></i>
              </div>
            </div>
          </div>
        </div>
        <div class="add-new-remark">
          <div
            class="text-btn"
            @click="handleClickAddNewRemark"
          >
            <i class="icon bk-icon icon-plus push"></i>
            <span class="text">{{ $t('新增备注') }}</span>
          </div>
        </div>
      </div>
    </div>

    <bk-dialog
      v-model="isShowStrInputDialog"
      :confirm-fn="confirmDialogStr"
      :title="$t('备注')"
      :width="480"
      header-position="left"
    >
      <bk-form
        ref="labelRef"
        style="width: 100%"
        :label-width="0"
        :model="verifyData"
        :rules="rules"
      >
        <bk-form-item property="labelRuels">
          <bk-input
            v-model="verifyData.textInputStr"
            :maxlength="100"
            :placeholder="$t('请输入')"
            :rows="5"
            type="textarea"
          >
          </bk-input>
        </bk-form-item>
      </bk-form>
    </bk-dialog>
  </div>
</template>

<script>
  import TextHighlight from 'vue-text-highlight';

  import { copyMessage, formatDate, deepClone, deepEqual } from '@/common/util';
  import EmptyStatus from '@/components/empty-status';
  import ClusteringLoader from '@/skeleton/clustering-loader';
  import BkUserSelector from '@blueking/user-selector';

  import ClusterEventPopover from './components/cluster-event-popover';
  import ClusterFilter from './components/cluster-filter';
  import fingerSelectColumn from './components/finger-select-column';

  export default {
    components: {
      ClusterEventPopover,
      ClusteringLoader,
      TextHighlight,
      EmptyStatus,
      BkUserSelector,
    },
    inject: ['addFilterCondition', 'batchAddCondition'],
    inheritAttrs: false,
    props: {
      fingerList: {
        type: Array,
        require: true,
      },
      clusterSwitch: {
        type: Boolean,
        require: true,
      },
      requestData: {
        type: Object,
        require: true,
      },
      configData: {
        type: Object,
        require: true,
      },
      loaderWidthList: {
        type: Array,
        default: () => [''],
      },
      isPageOver: {
        type: Boolean,
        default: false,
      },
      allFingerList: {
        type: Array,
        require: true,
      },
    },
    data() {
      return {
        cacheExpandStr: [], // 展示pattern按钮数组
        selectSize: 0, // 当前选择几条数据
        isSelectAll: false, // 当前是否点击全选
        selectList: [], // 当前选中的数组
        isRequestAlarm: false, // 是否正在请求告警接口
        checkValue: 0, // 0为不选 1为半选 2为全选
        /** 当前编辑备注或标签的 唯一判断数据 */
        curEditUniqueVal: {},
        /** 输入框弹窗的字符串 */
        verifyData: {
          textInputStr: '',
        },
        rules: {
          labelRuels: [
            {
              validator: this.checkName,
              message: this.$t('{n}不规范, 包含特殊符号.', { n: this.$t('备注') }),
              trigger: 'blur',
            },
            {
              max: 100,
              message: this.$t('不能多于{n}个字符', { n: 100 }),
              trigger: 'blur',
            },
          ],
        },
        enTableWidth: {
          number: '110',
          percentage: '116',
          year_on_year_count: '171',
          year_on_year_percentage: '171',
        },
        cnTableWidth: {
          number: '91',
          percentage: '96',
          year_on_year_count: '101',
          year_on_year_percentage: '101',
        },
        /** 编辑标签或备注的弹窗 */
        isShowStrInputDialog: false,
        /** 当前备注信息 */
        currentRemarkList: [],
        popoverInstance: null,
        userApi: window.BK_LOGIN_URL,
        catchOperatorVal: {},
        ownerBaseList: [
          {
            id: 'all',
            name: this.$t('全部'),
          },
          {
            id: 'no_owner',
            name: this.$t('未指定责任人'),
          },
        ],
        remarkSelect: ['all'],
        ownerSelect: ['all'],
        remarkList: [
          {
            id: 'all',
            name: this.$t('全部'),
          },
          {
            id: 'remarked',
            name: this.$t('已备注'),
          },
          {
            id: 'no_remark',
            name: this.$t('未备注'),
          },
        ],
        ownerList: [],
        // ownerLoading: false,
      };
    },
    computed: {
      bkBizId() {
        return this.$store.state.bkBizId;
      },
      isLimitExpandView() {
        return this.$store.state.isLimitExpandView;
      },
      isShowBottomTips() {
        return this.fingerList.length >= 50 && this.fingerList.length === this.allFingerList.length;
      },
      getLeaveText() {
        return !this.clusterSwitch
          ? this.$t('当前日志聚类未启用，请前往设置')
          : this.$t('当前数据指纹未启用，请前往设置');
      },
      getTableWidth() {
        return this.$store.getters.isEnLanguage ? this.enTableWidth : this.cnTableWidth;
      },
      /** 获取当前编辑操作的数据 */
      getHoverRowValue() {
        const uniqueVal = this.curEditUniqueVal;
        // 如果有分组也带上分组的条件
        const fingerRow = this.fingerList.find(item =>
          Object.keys(uniqueVal).every(key => deepEqual(item[key], uniqueVal[key])),
        );
        return fingerRow;
      },
      scrollContent() {
        return document.querySelector('.result-scroll-container');
      },
      isGroupSearch() {
        return !!this.requestData.group_by.length;
      },
      username() {
        return this.$store.state.userMeta?.username;
      },
    },
    watch: {
      'fingerList.length': {
        handler(newLength, oldLength) {
          // 全选时 分页下拉新增页默认选中
          if (this.isSelectAll) {
            this.$nextTick(() => {
              this.selectList.push(...this.fingerList.slice(oldLength, newLength));
            });
          }
        },
      },
      'selectList.length'(newLength) {
        // 选择列表数据大小计算
        if (this.isSelectAll) {
          this.selectSize = newLength + this.allFingerList.length - this.fingerList.length;
        } else {
          this.selectSize = newLength;
        }
        // 根据手动选择列表长度来判断全选框显示 全选 半选 不选
        if (!newLength) {
          this.checkValue = 0;
          return;
        }
        if (newLength && newLength !== this.fingerList.length) {
          this.checkValue = 1;
        } else {
          this.checkValue = 2;
        }
      },
    },
    mounted() {
      this.handleToggleUserSelect();
      this.handleToggleRemarkSelect();
      this.scrollEvent('add');
    },
    beforeUnmount() {
      this.scrollEvent('close');
    },
    methods: {
      handleMenuClick(option, row, isLink = false) {
        switch (option) {
          // pattern 下钻
          case 'show original':
            this.handleMenuBatchClick(row, isLink);
            if (!isLink) this.$emit('show-origin-log');
            break;
          case 'copy':
            copyMessage(row.pattern);
            break;
        }
      },
      handleMenuBatchClick(row, isLink = true) {
        const additionList = [];
        const groupBy = this.requestData.group_by;
        if (groupBy.length) {
          groupBy.forEach((el, index) => {
            additionList.push({
              field: el,
              operator: 'is',
              value: row.group[index],
            });
          });
        }
        additionList.push({
          field: `__dist_${this.requestData.pattern_level}`,
          operator: 'is',
          value: row.signature.toString(),
        });
        this.batchAddCondition(additionList, isLink);
      },
      showArrowsClass(row) {
        if (row.year_on_year_percentage === 0) return '';
        return row.year_on_year_percentage < 0 ? 'icon-arrows-down' : 'icon-arrows-up';
      },
      handleShowWhole(index) {
        this.cacheExpandStr.push(index);
      },
      handleHideWhole(index) {
        this.cacheExpandStr = this.cacheExpandStr.map(item => item !== index);
      },
      handleLeaveCurrent() {
        this.$emit('show-setting-log');
      },
      toFixedNumber(value, size) {
        if (typeof value === 'number' && !isNaN(value)) {
          if (value === 0) return 0;
          return value.toFixed(size);
        }
        return value;
      },
      /**
       * @desc: 添加或删除监听分页事件
       * @param { String } state 新增或删除
       */
      scrollEvent(state = 'add') {
        const scrollEl = document.querySelector('.result-scroll-container');
        if (!scrollEl) return;
        if (state === 'add') {
          scrollEl.addEventListener('scroll', this.handleScroll, { passive: true });
        }
        if (state === 'close') {
          scrollEl.removeEventListener('scroll', this.handleScroll, { passive: true });
        }
      },
      /**
       * @desc: 批量开启或者关闭告警
       * @param { Boolean } option 开启或关闭
       */
      handleBatchUseAlarm(option = true) {
        if (this.isRequestAlarm) {
          return;
        }
        const title = option ? this.$t('是否批量开启告警') : this.$t('是否批量关闭告警');
        this.$bkInfo({
          title,
          confirmFn: () => {
            let alarmList = this.selectList;
            if (this.isSelectAll) {
              // 全选时获取未显示的数据指纹
              alarmList = alarmList.concat(this.allFingerList.slice(alarmList.length));
            }
            // 过滤告警开启或者关闭状态的元素
            let filterList;
            if (option) {
              filterList = alarmList.filter(el => !el.monitor.is_active);
            } else {
              filterList = alarmList.filter(el => !!el.monitor.is_active);
            }
            // 分组情况下过滤重复的列表元素
            if (this.isGroupSearch) {
              filterList = this.getSetList(filterList);
            }
            this.requestAlarm(filterList, option, () => {
              // 批量成功后刷新数据指纹请求
              this.$emit('update-request');
            });
          },
        });
      },
      getSetList(list = []) {
        const setIDList = new Set();
        const returnList = list.filter(el => {
          if (!setIDList.has(el.signature)) {
            setIDList.add(el.signature);
            return true;
          }
        });
        return returnList;
      },
      /**
       * @desc: 数据指纹告警请求
       * @param { Array } alarmList 告警数组
       * @param { Boolean } state 启用或关闭
       * @param { Function } callback 回调函数
       */
      requestAlarm(alarmList = [], state, callback) {
        if (!alarmList.length) {
          this.$bkMessage({
            theme: 'success',
            message: state ? this.$t('已全部开启告警') : this.$t('已全部关闭告警'),
          });
          return;
        }

        const action = state ? 'create' : 'delete';
        // 组合告警请求数组
        const actions = alarmList.reduce((pre, cur) => {
          const {
            signature,
            pattern,
            monitor: { strategy_id },
          } = cur;
          const queryObj = {
            signature,
            pattern,
            strategy_id,
            action,
          };
          !queryObj.strategy_id && delete queryObj.strategy_id;
          pre.push(queryObj);
          return pre;
        }, []);
        this.isRequestAlarm = true;
        this.$http
          .request('/logClustering/updateStrategies', {
            params: {
              index_set_id: this.$route.params.indexId,
            },
            data: {
              bk_biz_id: this.bkBizId,
              pattern_level: this.requestData.pattern_level,
              actions,
            },
          })
          .then(({ data: { operators, result } }) => {
            /**
             * 当操作成功时 统一提示操作成功
             * 当操作失败时 分批量和单次
             * 单次显示返回值的提示 批量则显示部分操作成功
             */
            let theme;
            let message;
            if (result) {
              theme = 'success';
              message = this.$t('操作成功');
            } else {
              theme = this.isSelectAll ? 'warning' : 'error';
              message = this.isSelectAll ? this.$t('部分操作成功') : operators[0].operator_msg;
            }
            this.$bkMessage({
              theme,
              message,
              ellipsisLine: 0,
            });
            callback(result, operators[0].strategy_id);
          })
          .finally(() => {
            this.isRequestAlarm = false;
          });
      },
      handleScroll() {
        if (this.throttle) return;
        this.throttle = true;
        setTimeout(() => {
          this.throttle = false;
          // scroll变化时判断是否展示返回顶部的Icon
          this.$emit('handle-scroll-is-show');
          if (this.fingerList.length >= this.allFingerList.length) return;
          const el = document.querySelector('.result-scroll-container');
          if (el.scrollHeight - el.offsetHeight - el.scrollTop < 5) {
            el.scrollTop = el.scrollTop - 5;
            this.throttle = false;
            this.$emit('pagination-options');
          }
        }, 200);
      },
      renderHeader(h) {
        return h(fingerSelectColumn, {
          props: {
            value: this.checkValue,
            disabled: !this.fingerList.length,
          },
          on: {
            change: this.handleSelectionChange,
          },
        });
      },
      /**
       * @desc: 单选操作
       * @param { Object } row 操作元素
       * @param { Boolean } state 单选状态
       */
      handleRowCheckChange(row, state) {
        if (state) {
          this.selectList.push(row);
        } else {
          const index = this.selectList.indexOf(row);
          this.selectList.splice(index, 1);
        }
      },
      getCheckedStatus(row) {
        return this.selectList.includes(row);
      },
      /**
       * @desc: 全选和全不选操作
       * @param { Boolean } state 是否全选
       */
      handleSelectionChange(state) {
        this.isSelectAll = state;
        this.selectSize = state ? this.allFingerList.length : 0;
        // 先清空数组，如果是全选状态再添加当前已显示的元素
        this.selectList.splice(0, this.selectList.length);
        state && this.selectList.push(...this.fingerList);
      },
      handleReturnTop() {
        const el = document.querySelector('.result-scroll-container');
        this.$easeScroll(0, 300, el);
      },
      getHeightLightStr(str) {
        return !!str ? str : this.$t('未匹配');
      },
      getHeightLightList(str) {
        return str.match(/#.*?#/g) || [];
      },
      /** 设置负责人 */
      handleChangePrincipal(val, row) {
        this.curEditUniqueVal = {
          signature: row.signature,
          group: row.group,
        };
        this.$http
          .request('/logClustering/setOwner', {
            params: {
              index_set_id: this.$route.params.indexId,
            },
            data: {
              signature: this.getHoverRowValue.signature,
              owners: val,
              origin_pattern: this.getHoverRowValue.origin_pattern,
              groups: this.getGroupsValue(row.group),
            },
          })
          .then(res => {
            if (res.result) {
              const { signature, groups, owners } = res.data;
              this.curEditUniqueVal = {
                signature,
                group: this.requestData.group_by.map(gKey => groups[gKey]),
              };
              this.getHoverRowValue.owners = owners;
              this.$bkMessage({
                theme: 'success',
                message: this.$t('操作成功'),
              });
            }
          })
          .finally(() => (this.curEditUniqueVal = {}));
      },
      /** 设置备注  */
      remarkQuery(markType = 'add') {
        let additionData;
        let queryStr;
        switch (markType) {
          case 'update':
            queryStr = 'updateRemark';
            additionData = {
              new_remark: this.verifyData.textInputStr.trim(),
              ...this.catchOperatorVal,
            };
            break;
          case 'delete':
            queryStr = 'deleteRemark';
            additionData = {
              remark: this.verifyData.textInputStr.trim(),
              ...this.catchOperatorVal,
            };
            break;
          case 'add':
            queryStr = 'setRemark';
            additionData = {
              remark: this.verifyData.textInputStr.trim(),
            };
            break;
        }
        this.$http
          .request(`/logClustering/${queryStr}`, {
            params: {
              index_set_id: this.$route.params.indexId,
            },
            data: {
              signature: this.getHoverRowValue.signature,
              ...additionData,
              origin_pattern: this.getHoverRowValue.origin_pattern,
              groups: this.getGroupsValue(this.curEditUniqueVal.group),
            },
          })
          .then(res => {
            if (res.result) {
              const { signature, groups, remark } = res.data;
              this.curEditUniqueVal = {
                signature,
                group: this.requestData.group_by.map(gKey => groups[gKey]),
              };
              this.getHoverRowValue.remark = remark;
              this.$bkMessage({
                theme: 'success',
                message: this.$t('操作成功'),
              });
            }
          })
          .finally(() => {
            this.curEditUniqueVal = {};
            this.verifyData.textInputStr = '';
            this.catchOperatorVal = {};
          });
      },
      checkName() {
        if (this.verifyData.textInputStr.trim() === '') return true;

        return /^[\u4e00-\u9fa5_a-zA-Z0-9`~!\s@#$%^&*()_\-+=<>?:"{}|,.\/;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
          this.verifyData.textInputStr.trim(),
        );
      },
      handleHoverRemarkIcon(e, row) {
        if (!this.popoverInstance) {
          this.currentRemarkList = row.remark
            .map(item => ({
              ...item,
              showTime: item.create_time > 0 ? formatDate(item.create_time) : '',
            }))
            .sort((a, b) => b.create_time - a.create_time);
          this.popoverInstance = this.$bkPopover(e.target, {
            content: this.$refs.remarkTips,
            allowHTML: true,
            arrow: true,
            theme: 'light',
            sticky: true,
            duration: [275, 0],
            interactive: true,
            boundary: 'window',
            placement: 'top',
            width: 240,
            onShow: () => {
              this.curEditUniqueVal = {
                signature: row.signature,
                group: row.group,
              };
            },
            onHidden: () => {
              this.popoverInstance?.destroy();
              this.popoverInstance = null;
            },
          });
        }
        this.popoverInstance.show();
      },
      /** 提交新的备注 */
      async confirmDialogStr() {
        try {
          await this.$refs.labelRef.validate();
          const queryType = Object.keys(this.catchOperatorVal).length ? 'update' : 'add';
          this.remarkQuery(queryType);
          this.isShowStrInputDialog = false;
        } catch (err) {
          return false;
        }
      },
      /** 点击新增备注 */
      handleClickAddNewRemark() {
        this.popoverInstance.hide();
        this.verifyData.textInputStr = '';
        this.isShowStrInputDialog = true;
      },
      handleEditRemark(row) {
        this.popoverInstance.hide();
        this.verifyData.textInputStr = row.remark;
        this.catchOperatorVal = {
          old_remark: row.remark,
          create_time: row.create_time,
        };
        this.isShowStrInputDialog = true;
      },
      handleDeleteRemark(row) {
        this.popoverInstance.hide();
        this.catchOperatorVal = {
          remark: row.remark,
          create_time: row.create_time,
        };
        this.remarkQuery('delete');
      },
      remarkContent(remarkList) {
        if (!remarkList.length) return '--';
        const maxTimestamp = remarkList.reduce((pre, cur) => {
          return cur.create_time > pre.create_time ? cur : pre;
        }, remarkList[0]);
        return maxTimestamp.remark;
      },
      /**
       * @desc: 获取当前数据指纹所有的责任人
       */
      getUserList() {
        this.ownerLoading = true;
        const cloneOwnerBase = deepClone(this.ownerBaseList);
        this.$http
          .request('/logClustering/getOwnerList', {
            params: {
              index_set_id: this.$route.params.indexId,
            },
          })
          .then(res => {
            this.ownerList = res.data.reduce((acc, cur) => {
              acc.push({
                id: cur,
                name: cur,
              });
              return acc;
            }, cloneOwnerBase);
          })
          .finally(() => {
            this.ownerLoading = false;
          });
      },
      /**
       * @desc: 选中责任人列表里的值
       */
      handleUserSelectChange(v) {
        if (!v.length) {
          this.ownerSelect = ['all'];
          return;
        }
        const lastSelect = v[v.length - 1];
        if (lastSelect === 'all') {
          this.ownerSelect = [lastSelect];
        } else {
          this.ownerSelect = v.filter(item => !(item === 'all'));
        }
      },
      /**
       * @desc: 选中备注列表里的值 单选永远是最后一个
       */
      handleRemarkSelectChange(v) {
        if (!v.length) {
          this.remarkSelect = ['all'];
          return;
        }
        this.remarkSelect = [v[v.length - 1]];
      },
      /**
       * @desc: 责任人提交
       */
      handleUserSubmit(v) {
        const ownerData = v.includes('all')
          ? {
              owner_config: 'all',
              owners: [],
            }
          : {
              owner_config: v.includes('no_owner') ? 'no_owner' : 'owner',
              owners: v.filter(item => item !== 'no_owner'),
            };
        this.$emit('handle-finger-operate', 'requestData', ownerData, true);
      },
      /**
       * @desc: 备注提交
       */
      handleRemarkSubmit(v) {
        this.$emit('handle-finger-operate', 'requestData', { remark_config: v[v.length - 1] }, true);
      },
      /**
       * @desc: 初始化责任人选择的数据和初始化责任人列表
       */
      handleToggleUserSelect(v) {
        this.ownerSelect = !!this.requestData.owners.length ? this.requestData.owners : [this.requestData.owner_config];
        if (v) this.getUserList();
      },
      /**
       * @desc: 初始化备注选择的数据
       */
      handleToggleRemarkSelect() {
        this.remarkSelect = [this.requestData.remark_config];
      },
      renderUserHeader(h, { column }) {
        const isActive = this.ownerSelect.length && !this.ownerSelect.includes('all');
        return h(ClusterFilter, {
          props: {
            title: column.label,
            disabled: false,
            select: this.ownerSelect,
            selectList: this.ownerList,
            loading: this.ownerLoading,
            toggle: this.handleToggleUserSelect,
            isActive,
          },
          on: {
            selected: this.handleUserSelectChange,
            submit: this.handleUserSubmit,
          },
        });
      },
      renderRemarkHeader(h, { column }) {
        const isActive = this.remarkSelect.length && !this.remarkSelect.includes('all');
        return h(ClusterFilter, {
          props: {
            title: column.label,
            searchable: false,
            popoverMinWidth: 170,
            disabled: false,
            select: this.remarkSelect,
            selectList: this.remarkList,
            toggle: this.handleToggleRemarkSelect,
            isActive,
          },
          on: {
            selected: this.handleRemarkSelectChange,
            submit: this.handleRemarkSubmit,
          },
        });
      },
      /** 将分组的数组改成对像 */
      getGroupsValue(group) {
        if (!this.requestData.group_by.length) return {};
        return this.requestData.group_by.reduce((acc, cur, index) => {
          acc[cur] = group?.[index] ?? '';
          return acc;
        }, {});
      },
      getLimitState(index) {
        if (this.isLimitExpandView) return false;
        return !this.cacheExpandStr.includes(index);
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';

  /* stylelint-disable no-descending-specificity */
  .finger-container {
    position: relative;

    .monospace-text,
    %monospace-text {
      font-family: var(--table-fount-family);
      font-size: var(--table-fount-size);
      line-height: 20px;
    }

    .monospace-text {
      color: #313238;
    }

    .auto-height-container {
      padding: 6px 0 6px;
    }

    .auto-height {
      /* stylelint-disable-next-line value-no-vendor-prefix */
      display: -webkit-box;
      height: auto; /* 设置元素高度为自动 */
      min-height: 20px; /* 根据需要设置最小高度 */
      padding: 0 2px;
      overflow: hidden;
      text-overflow: ellipsis;

      /* stylelint-disable-next-line property-no-vendor-prefix */
      -webkit-box-orient: vertical;
      -webkit-line-clamp: 3;
    }

    .top-operate {
      position: absolute;
      top: 42px;
      z-index: 99;
      width: 100%;
      height: 32px;
      font-size: 12px;
      background: #f0f1f5;
      border-top: 1px solid #dfe0e5;
      border-bottom: 1px solid #dfe0e5;

      @include flex-center;

      .operate-message {
        padding-right: 6px;
        color: #63656e;
      }

      .operate-click {
        padding-right: 6px;
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .finger-cluster-table {
      color: #313238;

      :deep(.bk-table-body-wrapper) {
        min-height: calc(100vh - 570px);
        margin-top: 32px;

        .bk-table-empty-block {
          min-height: calc(100vh - 570px);

          @include flex-center;
        }
      }

      &:before {
        display: none;
      }

      :deep(.bk-table-row-last) {
        td {
          border: none;
        }
      }

      .signature-box {
        margin-top: 1px;

        span {
          overflow: hidden;
          line-height: 24px;
          text-overflow: ellipsis;
          white-space: nowrap;

          @extend %monospace-text;
        }
      }

      .compared-change {
        justify-content: center;
        margin-top: 1px;
      }

      .bk-icon {
        font-size: 22px;
      }

      .empty-text {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: space-between;

        .bk-icon {
          font-size: 65px;
        }

        .empty-leave {
          margin-top: 8px;
          color: #3a84ff;
          cursor: pointer;
        }
      }

      // .pattern {
      // display: flex;
      // align-items: center;
      // }

      .pattern-content {
        position: relative;
        display: inline-block;
        padding: 0 6px;
        margin-bottom: 15px;
        overflow: hidden;

        &.is-limit {
          max-height: 114px;
        }
      }

      .hover-row {
        .show-whole-btn {
          background-color: #f5f7fa;
        }

        .principal-input {
          &:hover {
            :deep(.user-selector-container) {
              /* stylelint-disable-next-line declaration-no-important */
              background: #eaebf0 !important;
            }
          }
        }
      }

      .show-whole-btn {
        position: absolute;
        top: 100px;
        width: 100%;
        height: 24px;
        font-size: 12px;
        color: #3a84ff;
        cursor: pointer;
        background: #fff;
        transition: background-color 0.25s ease;
      }

      .hide-whole-btn {
        margin-top: 2px;
        line-height: 14px;
        color: #3a84ff;
        cursor: pointer;
      }
    }
  }

  .table-no-data {
    :deep(.bk-table-header-wrapper) {
      tr {
        > th {
          /* stylelint-disable-next-line declaration-no-important */
          border-bottom: none !important;
        }
      }
    }
  }

  .bottom-tips {
    height: 43px;
    line-height: 43px;
    color: #979ba5;
    text-align: center;

    span {
      color: #3a84ff;
      cursor: pointer;
    }
  }

  .new-finger {
    flex-shrink: 0;
    width: 40px;
    height: 16px;
    margin-left: 6px;
    font-size: 12px;
    line-height: 14px;
    color: #ea3636;
    text-align: center;
    background: #fee;
    border: 1px solid #fd9c9c;
    border-radius: 9px;
  }

  .link-color {
    color: #3a84ff;
    cursor: pointer;

    @extend %monospace-text;
  }

  .icon-arrows-down {
    color: #2dcb56;
  }

  .icon-arrows-up {
    color: #ff5656;
  }

  .fl-ac {
    margin-top: -4px;

    @include flex-align;
  }

  .principal-input {
    width: 100%;

    :deep(.user-selector-container) {
      /* stylelint-disable-next-line declaration-no-important */
      background: transparent !important;

      /* stylelint-disable-next-line declaration-no-important */
      border: none !important;

      &.disabled {
        /* stylelint-disable-next-line declaration-no-important */
        background: transparent !important;
      }
    }
  }

  #remark-tips {
    .remark-list {
      max-height: 120px;
      margin-bottom: 6px;
      overflow-y: auto;
      font-size: 12px;
      color: #63656e;
      border-bottom: 1px solid #eaebf0;

      .user {
        font-weight: 700;
      }

      .content {
        padding: 6px 0;
        white-space: pre-wrap;
      }

      .tools {
        align-items: center;
        color: #979ba5;

        @include flex-justify(space-between);
      }

      .icon {
        display: inline-block;
        margin-right: 8px;
        font-size: 14px;

        .bk-icon:hover {
          cursor: pointer;
        }

        .icon-edit-line:hover {
          color: #3a84ff;
        }

        .icon-delete:hover {
          color: #ea3636;
        }
      }

      > div:not(:last-child) {
        margin-bottom: 10px;
      }

      > div:last-child {
        margin-bottom: 8px;
      }
    }

    .add-new-remark {
      @include flex-center();

      .text-btn {
        cursor: pointer;

        @include flex-align(center);

        .text,
        .icon {
          color: #3a84ff;
        }

        .push {
          font-size: 24px;
        }

        .text {
          font-size: 12px;
        }
      }
    }
  }
</style>
