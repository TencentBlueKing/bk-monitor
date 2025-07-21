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
    class="basic-info-container"
    v-bkloading="{ isLoading: basicLoading }"
  >
    <div>
      <div
        v-if="!isContainer"
        class="deploy-sub"
        v-en-class="'en-deploy'"
      >
        <!-- 数据ID -->
        <div>
          <span>{{ $t('数据ID') }}</span>
          <span>{{ collectorData.bk_data_id || '-' }}</span>
        </div>
        <!-- otlp_log Token -->
        <div v-if="collectorData.custom_type === 'otlp_log'">
          <span>Token</span>
          <section class="token-view">
            <span
              v-if="!tokenStr"
              :class="['mask-content', { 'btn-loading': tokenLoading }]"
            >
              <span class="placeholder">●●●●●●●●●●</span>
              <span
                v-if="tokenLoading"
                class="loading"
              ></span>
              <bk-button
                class="view-btn"
                v-cursor="{ active: !editAuth }"
                :loading="tokenLoading"
                text
                @click="handleGetToken"
                >{{ tokenLoading ? '' : $t('点击查看') }}</bk-button
              >
            </span>
            <span
              v-else
              class="password-content"
            >
              <span :class="{ placeholder: true, 'password-value': !showPassword }">
                {{ showPassword ? tokenStr || '-' : '********' }}
              </span>
              <span class="operate-box">
                <span
                  v-if="showPassword"
                  class="bklog-icon bklog-copy-2"
                  @click="handleCopy(tokenStr)"
                ></span>
                <span
                  :class="`bk-icon toggle-icon ${showPassword ? 'icon-eye-slash' : 'icon-eye'}`"
                  @click="showPassword = !showPassword"
                >
                </span>
              </span>
            </span>
          </section>
        </div>
        <!-- 名称 -->
        <div>
          <span>{{ $t('名称') }}</span>
          <span>{{ collectorData.collector_config_name || '-' }}</span>
        </div>
        <template v-if="isCustomReport">
          <div>
            <span>{{ $t('数据类型') }}</span>
            <span>{{ collectorData.custom_name || '-' }}</span>
          </div>
          <div>
            <span>{{ $t('数据名') }}</span>
            <span>{{ collectorData.collector_config_name_en || '-' }}</span>
          </div>
          <div>
            <span>{{ $t('数据分类') }}</span>
            <span>{{ collectorData.category_name || '-' }}</span>
          </div>
          <div>
            <span>{{ $t('说明') }}</span>
            <span>{{ collectorData.description || '-' }}</span>
          </div>
        </template>
        <template v-else>
          <!-- 日志类型 -->
          <div>
            <span>{{ $t('日志类型') }}</span>
            <span>{{ collectorData.collector_scenario_name || '-' }}</span>
          </div>
          <!-- 数据分类 -->
          <div>
            <span>{{ $t('数据分类') }}</span>
            <span>{{ collectorData.category_name || '-' }}</span>
          </div>
          <!-- 日志路径 -->
          <div>
            <span>
              {{ isWinEventLog ? $t('日志种类') : $t('日志路径') }}
            </span>
            <div
              v-if="params.paths"
              class="deploy-path"
            >
              <p
                v-for="(val, key) in params.paths"
                :key="key"
              >
                {{ val }}
              </p>
            </div>
            <div
              v-else
              class="deploy-path"
            >
              <p>{{ getLogSpeciesStr }}</p>
            </div>
          </div>
          <!-- 日志字符集 -->
          <div>
            <span>{{ $t('字符集') }}</span>
            <span>{{ collectorData.data_encoding || '-' }}</span>
          </div>
          <!-- 采集目标 -->
          <div>
            <span>{{ $t('采集目标') }}</span>
            <span>
              <i18n path="已选择 {0} 个{1}">
                <p
                  class="num-color"
                  @click="handleClickTarget"
                >
                  {{ collectorData.target_nodes.length || '-' }}
                </p>
                {{ collectorData.target_node_type !== 'INSTANCE' ? $t('节点') : $t('静态主机') }}
              </i18n>
            </span>
          </div>
          <!-- 存储索引名 -->
          <div>
            <span>{{ $t('索引名') }}</span>
            <span v-if="collectorData.table_id">{{ collectorData.table_id_prefix }}{{ collectorData.table_id }}</span>
            <span v-else>-</span>
          </div>
          <!-- 备注说明 -->
          <div>
            <span>{{ $t('备注说明') }}</span>
            <span>{{ collectorData.description || '-' }}</span>
          </div>
          <!-- 段日志 -->
          <template v-if="collectorData.collector_scenario_id === 'section'">
            <div class="content-style">
              <span>{{ $t('段日志参数') }}</span>
              <div class="section-box">
                <p>
                  {{ $t('行首正则') }}: <span>{{ params.multiline_pattern }}</span>
                </p>
                <br />
                <p>
                  <i18n path="最多匹配{0}行，最大耗时{1}秒">
                    <span>{{ params.multiline_max_lines }}</span>
                    <span>{{ params.multiline_timeout }}</span>
                  </i18n>
                </p>
              </div>
            </div>
          </template>
          <div
            v-if="!isWinEventLog && conditions.type === 'none'"
            class="content-style"
          >
            <span>{{ $t('过滤内容') }}</span>
            <div>--</div>
          </div>
          <div
            v-else-if="isNotWinAndHaveFilter"
            class="content-style"
          >
            <span>{{ $t('过滤内容') }}</span>
            <div>
              <p>{{ isMatchType ? $t('字符串过滤') : $t('分隔符匹配') }}</p>
              <p v-if="!isMatchType && conditions.separator">{{ conditions.separator }}</p>
              <div class="condition-stylex">
                <div
                  v-for="(fItem, fIndex) in filterGroup"
                  :key="fIndex"
                >
                  <span class="title">{{ $t('第{n}组', { n: fIndex + 1 }) }}</span>
                  <div class="column-box">
                    <div class="item-box">
                      <div
                        v-for="(gItem, gIndex) in groupKey"
                        :key="gIndex"
                        class="item"
                      >
                        {{ gItem }}
                      </div>
                    </div>
                    <div
                      v-for="(item, index) in fItem"
                      :key="index"
                      class="item-box"
                    >
                      <div
                        v-if="!isMatchType"
                        class="item the-column"
                      >
                        {{ $t('第{n}列', { n: item.fieldindex }) }}
                      </div>
                      <div class="item the-column">{{ showOperatorObj[item.op] }}</div>
                      <p
                        class="value the-column"
                        @mouseenter="handleEnter"
                        @mouseleave="handleLeave"
                      >
                        {{ item.word }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div
            v-else-if="isWinEventLog && isHaveEventValue"
            class="content-style"
          >
            <span>{{ $t('过滤内容') }}</span>
            <div class="win-log">
              <div>
                <p>{{ $t('事件ID') }}:{{ getEventIDStr }}</p>
              </div>
              <div>
                <p>{{ $t('级别') }}:{{ getLevelStr }}</p>
              </div>
            </div>
          </div>
        </template>
        <!-- 存储集群 -->
        <div>
          <span>{{ $t('存储集群') }}</span>
          <span
            v-bk-tooltips.top="{
              content: `${collectorData.storage_cluster_domain_name}:${collectorData.storage_cluster_port}`,
              disabled: !collectorData.storage_cluster_name,
            }"
            >{{ collectorData.storage_cluster_name || '-' }}</span
          >
        </div>
        <!-- 存储索引名 -->
        <div>
          <span>{{ $t('索引名') }}</span>
          <span>{{ collectorData.table_id_prefix + collectorData.table_id || '-' }}</span>
        </div>
        <!-- 过期时间 -->
        <div>
          <span>{{ $t('过期时间') }}</span>
          <span>{{ collectorData.retention || '-' }} {{ $t('天') }}</span>
        </div>
      </div>
      <container-base
        v-else
        :collector-data="collectorData"
        :is-loading.sync="basicLoading"
      ></container-base>
    </div>
    <div>
      <bk-button
        style="min-width: 88px; color: #3a84ff"
        class="mr10"
        v-cursor="{ active: !editAuth }"
        :theme="'default'"
        @click="handleClickEdit"
      >
        {{ $t('编辑') }}
      </bk-button>
      <bk-popover placement="bottom-end">
        <bk-button class="bklog-icon bklog-lishijilu"></bk-button>
        <template #content>
          <div class="create-name-and-time">
            <div
              v-for="item in createAndTimeData"
              :key="item.key"
            >
              <span>{{ item.label }}</span>
              <span>{{ item.value }}</span>
            </div>
          </div>
        </template>
      </bk-popover>
    </div>
  </div>
</template>

<script>
import { utcFormatDate, copyMessage } from '@/common/util';
import { operatorMappingObj, operatorMapping } from '@/components/collection-access/components/log-filter/type';
import { mapState } from 'vuex';

import containerBase from './components/container-base';

export default {
  components: {
    containerBase,
  },
  props: {
    collectorData: {
      type: Object,
      required: true,
    },
    editAuth: {
      type: Boolean,
      default: false,
    },
    editAuthData: {
      type: Object,
      default: null,
      validator(value) {
        // 校验 value 是否为 null 或一个有效的对象
        return value === null || (typeof value === 'object' && value !== null);
      },
    },
  },
  data() {
    return {
      // 右边展示的创建人、创建时间
      createAndTimeData: [],
      basicLoading: false,
      isShowToken: false, // 是否展示 oltp_log Token
      showPassword: true, // 是否展示Token值
      tokenLoading: false,
      tokenStr: '', // token 的值
      groupList: [this.$t('过滤参数'), this.$t('操作符'), 'Value'],
    };
  },
  computed: {
    ...mapState(['spaceUid']),
    getEventIDStr() {
      return this.params.winlog_event_id?.join(',') || '';
    },
    getLevelStr() {
      return this.params.winlog_level?.join(',') || '';
    },
    getLogSpeciesStr() {
      return this.params.winlog_name?.join(',') || '';
    },
    isHaveEventValue() {
      return this.params.winlog_event_id.length || this.params.winlog_level.length;
    },
    isContainer() {
      return this.collectorData.environment === 'container';
    },
    // 自定义上报基本信息
    isCustomReport() {
      return this.$route.name === 'custom-report-detail';
    },
    isWinEventLog() {
      return this.collectorData.collector_scenario_id === 'wineventlog';
    },
    isNotWinAndHaveFilter() {
      if (this.isWinEventLog || this.params.type === 'none') return false;
      return this.conditions && !!this.conditions?.separator_filters.length;
    },
    isMatchType() {
      return this.conditions.type === 'match';
    },
    params() {
      return this.collectorData.params;
    },
    conditions() {
      return this.collectorData.params.conditions;
    },
    filterGroup() {
      const filters = this.conditions?.separator_filters;
      return this.splitFilters(filters ?? []);
    },
    showOperatorObj() {
      return Object.keys(operatorMappingObj).reduce((pre, acc) => {
        let newKey = acc;
        if ((this.isMatchType && acc === 'include') || (!this.isMatchType && acc === 'eq')) newKey = '=';
        pre[newKey] = operatorMappingObj[acc];
        return pre;
      }, {});
    },
    groupKey() {
      return this.isMatchType ? this.groupList.slice(1) : this.groupList;
    },
  },
  created() {
    this.getCollectDetail();
  },
  methods: {
    getCollectDetail() {
      try {
        const { collectorData } = this;
        const createAndTimeData = [
          {
            key: 'updated_by',
            label: this.$t('更新人'),
          },
          {
            key: 'updated_at',
            label: this.$t('更新时间'),
          },
          {
            key: 'created_by',
            label: this.$t('创建人'),
          },
          {
            key: 'created_at',
            label: this.$t('创建时间'),
          },
        ];
        this.createAndTimeData = createAndTimeData.map(item => {
          if (item.key === 'created_at' || item.key === 'updated_at') {
            item.value = utcFormatDate(collectorData[item.key]);
          } else {
            item.value = collectorData[item.key];
          }
          return item;
        });
      } catch (e) {
        console.warn(e);
      }
    },
    handleClickTarget() {
      this.$emit('update-active-panel', 'collectionStatus');
    },
    // 判断是否超出  超出提示
    handleEnter(e) {
      const cWidth = e.target.clientWidth;
      const sWidth = e.target.scrollWidth;
      if (sWidth > cWidth) {
        this.instance = this.$bkPopover(e.target, {
          content: e.target.innerText,
          arrow: true,
          placement: 'right',
        });
        this.instance.show(1000);
      }
    },
    handleLeave() {
      this.instance?.destroy(true);
    },
    handleClickEdit() {
      if (!this.editAuth && this.editAuthData) {
        this.$store.commit('updateAuthDialogData', this.editAuthData);
        return;
      }
      const params = {};
      params.collectorId = this.$route.params.collectorId;
      const routeName = this.isCustomReport ? 'custom-report-edit' : 'collectEdit';
      this.$router.push({
        name: routeName,
        params,
        query: {
          spaceUid: this.$store.state.spaceUid,
          backRoute: 'manage-collection',
          type: 'basicInfo',
        },
      });
    },
    async handleGetToken() {
      if (!this.editAuth && this.editAuthData) {
        this.$store.commit('updateAuthDialogData', this.editAuthData);
        return;
      }
      try {
        this.tokenLoading = true;
        const res = await this.$http.request('collect/reviewToken', {
          params: {
            collector_config_id: this.$route.params.collectorId,
          },
        });
        this.tokenStr = res.data?.bk_data_token || '-';
      } catch (error) {
        console.warn(error);
        this.tokenStr = '';
      } finally {
        this.tokenLoading = false;
      }
    },
    handleCopy(text) {
      copyMessage(text);
    },
    /** 设置过滤分组 */
    splitFilters(filters) {
      const groups = [];
      let currentGroup = [];

      filters.forEach((filter, index) => {
        const mappingFilter = {
          ...filter,
          op: operatorMapping[filter.op] ?? filter.op, // 映射操作符
        };
        currentGroup.push(mappingFilter);
        // 检查下一个 filter
        if (filters[index + 1]?.logic_op === 'or' || index === filters.length - 1) {
          groups.push(currentGroup);
          currentGroup = [];
        }
      });
      if (currentGroup.length > 0) {
        groups.push(currentGroup);
      }
      return groups;
    },
  },
};
</script>

<style lang="scss" scoped>
  @import '@/scss/basic.scss';
  @import '@/scss/mixins/flex.scss';

  /* stylelint-disable no-descending-specificity */
  .basic-info-container {
    display: flex;
    justify-content: space-between;

    .en-deploy > div {
      > span:nth-child(1) {
        /* stylelint-disable-next-line declaration-no-important */
        width: 110px !important;
      }
    }

    .deploy-sub > div {
      display: flex;
      align-items: center;
      margin-bottom: 33px;

      > span:nth-child(1) {
        display: block;
        width: 98px;
        font-size: 14px;
        color: #979ba5;
        text-align: right;
      }

      > span:nth-child(2) {
        margin-left: 24px;
        font-size: 14px;
        color: #63656e;
      }

      .deploy-path {
        margin-left: 24px;
        font-size: 14px;
        line-height: 22px;
        color: #63656e;
      }

      .num-color {
        display: inline-block;
        padding: 0;
        font-weight: bold;

        /* stylelint-disable-next-line declaration-no-important */
        color: #4e99ff !important;
        cursor: pointer;
      }
    }

    .content-style {
      display: flex;
      align-items: flex-start;

      .win-log {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 60px;
      }

      .section-box {
        > :last-child {
          margin-top: 4px;
        }

        span {
          /* stylelint-disable-next-line declaration-no-important */
          display: inline !important;
        }
      }

      > div {
        margin-left: 24px;
        font-size: 14px;

        p {
          display: inline-block;
          height: 20px;
          padding: 0 5px;
          margin-right: 2px;
          line-height: 20px;
          color: #63656e;
          text-align: center;
          background-color: #f0f1f5;
          border-radius: 2px;
        }
      }
    }

    .create-name-and-time {
      border-top: 1px solid #dcdee5;
      border-radius: 2px;

      div {
        width: 260px;
        height: 40px;
        line-height: 40px;
        border-right: 1px solid #dcdee5;
        border-bottom: 1px solid #dcdee5;
        border-left: 1px solid #dcdee5;

        span:nth-child(1) {
          display: inline-block;
          width: 48px;
          margin-left: 14px;
          font-size: 12px;
          color: #313238;
        }

        span:nth-child(2) {
          margin-left: 22px;
          font-size: 12px;
          color: #63656e;
        }
      }
    }

    .token-view {
      margin: -2px 0 0 24px;
      color: #63656e;

      .mask-content {
        .view-btn {
          margin-left: 8px;
          font-size: 12px;
          color: #3a84ff;
          cursor: pointer;
        }

        &.btn-loading {
          color: #c4c6cc;
          cursor: not-allowed;

          .view-btn {
            color: #c4c6cc;
          }
        }
      }

      .password-content {
        height: 24px;
        font-size: 14px;

        @include flex-align;

        .toggle-icon {
          margin-left: 8px;
          cursor: pointer;
        }

        .operate-box {
          position: relative;
          top: -2px;
          display: inline-block;
          margin-left: 36px;

          .bklog-copy-2,
          .icon-eye-slash {
            cursor: pointer;

            &:hover {
              color: #3a84ff;
            }
          }
        }

        // .icon-eye-slash {
        //   margin-left: 36px;
        // }

        .password-value {
          padding-top: 6px;
        }
      }
    }
  }
</style>
