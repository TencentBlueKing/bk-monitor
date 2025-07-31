<!-- eslint-disable vue/no-v-html -->
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
    class="collection-status-container"
    v-bkloading="{ isLoading: basicLoading }"
  >
    <!-- 容器日志状态页 -->
    <container-status
      v-if="isContainer"
      :is-loading.sync="basicLoading"
    />
    <template v-else>
      <div
        v-if="dataFir"
        class="collect"
      >
        <div class="mb15 nav-section">
          <div class="button-group">
            <span
              v-for="(val, x) in dataButton"
              :class="clickSec.selected === val.key ? 'button-bul' : 'button-wit'"
              :key="x"
              @click="handleChangeGroup(val)"
              >{{ val.content }}({{ val.dataList.totalLenght }})</span
            >
          </div>
          <div>
            <span>{{ $t('每15分钟按照CMDB最新拓扑自动部署或取消采集') }}</span>
            <!-- <span class="bk-icon icon-question-circle" v-bk-tooltips="$t('每15分钟按照CMDB最新拓扑自动部署或取消采集')"></span> -->
            <bk-button
              class="mr10"
              :disabled="!collectProject"
              :size="size"
              :title="$t('重试')"
              icon="right-turn-line"
              theme="default"
              @click="retryClick(dataFal, dataFir.contents.length)"
              >{{ $t('失败批量重试') }}
            </bk-button>
            <!-- <bk-button
            :theme="'primary'"
            :title="$t('数据采样')"
            class="mr10"
            :size="size"
            :disabled="!collectProject"
            @click="jsonFormatClick">
            {{$t('数据采样')}}
          </bk-button> -->
          </div>
        </div>
        <div
          v-for="(value, i) in renderTableList"
          ref="unfold"
          style="margin-bottom: 10px; overflow: hidden"
          :key="i"
        >
          <div
            class="table-detail"
            @click="closeTable(i)"
          >
            <div>
              <i
                ref="icon"
                :style="{ color: collapseColor }"
                class="bk-icon title-icon icon-down-shape"
              ></i>
              <span>{{ value.node_path }}</span>
              <span>{{ dataSec[i] ? dataSec[i].length : '' }}</span>
              <span>{{ $t('个成功') }},</span>
              <span>{{ dataFal[i] ? dataFal[i].length : '' }}</span>
              <span>{{ $t('个失败') }}</span>
            </div>
          </div>
          <div class="table-calc">
            <bk-table
              v-bkloading="{ isLoading: reloadTable }"
              :data="clickSec.data[i]"
              :empty-text="$t('暂无内容')"
              size="small"
            >
              <bk-table-column :label="$t('目标')">
                <template #default="props">
                  <span>{{ getShowIp(props.row) }}</span>
                </template>
              </bk-table-column>
              <bk-table-column :label="$t('状态')">
                <template #default="props">
                  <span @click="reset(props.row)">
                    <i
                      v-if="props.row.status !== 'SUCCESS' && props.row.status !== 'FAILED'"
                      style="display: inline-block; animation: button-icon-loading 1s linear infinite"
                      class="bk-icon icon-refresh"
                    ></i>
                    <span
                      v-if="props.row.status === 'SUCCESS'"
                      class="SUCCESS"
                    >
                      {{ $t('成功') }}
                    </span>
                    <span
                      v-else-if="props.row.status === 'FAILED'"
                      class="FAILED"
                    >
                      {{ $t('失败') }}
                    </span>
                    <span
                      v-else
                      class="PENDING"
                      >{{ $t('执行中') }}</span
                    >
                  </span>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('更新时间')"
                prop="create_time"
              ></bk-table-column>
              <bk-table-column
                :label="$t('插件版本')"
                prop="plugin_version"
              ></bk-table-column>
              <bk-table-column
                width="280"
                :label="$t('详情')"
              >
                <template #default="props">
                  <div class="text-style">
                    <span @click.stop="viewDetail(props.row)">{{ $t('部署详情') }}</span>
                    <span
                      v-if="enableCheckCollector && collectorData.environment === 'linux'"
                      @click.stop="viewReport(props.row)"
                    >
                      {{ $t('一键检测') }}
                    </span>
                  </div>
                </template>
              </bk-table-column>
              <bk-table-column
                width="120"
                label=""
              >
                <template #default="props">
                  <bk-button
                    v-if="props.row.status === 'FAILED'"
                    theme="primary"
                    text
                    @click="retryClick(props.row, 'odd')"
                  >
                    {{ $t('重试') }}
                  </bk-button>
                </template>
              </bk-table-column>
              <template #empty>
                <div>
                  <empty-status
                    :show-text="false"
                    empty-type="empty"
                  >
                    <span>{{ $t('暂无内容') }}</span>
                  </empty-status>
                </div>
              </template>
            </bk-table>
          </div>
        </div>
        <template v-if="renderTableList.length">
          <div
            style="height: 40px"
            v-bkloading="{ isLoading: true }"
            v-show="!isPageOver && !reloadTable"
          ></div>
        </template>
        <bk-sideslider
          :ext-cls="'issued-detail'"
          :is-show.sync="detail.isShow"
          :quick-close="true"
          :width="800"
          transfer
          @animation-end="closeSlider"
        >
          <template #header>
            <div>{{ detail.title }}</div>
          </template>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <template #content>
            <div
              class="p20 detail-content"
              v-bkloading="{ isLoading: detail.loading }"
              v-html="$xss(detail.content)"
            ></div>
          </template>
        </bk-sideslider>
      </div>
    </template>
    <collection-report-view
      v-model="reportDetailShow"
      :check-record-id="checkRecordId"
      @close-report="() => (reportDetailShow = false)"
    />
  </div>
</template>

<script>
  import { projectManages } from '@/common/util';
  import EmptyStatus from '@/components/empty-status';

  import CollectionReportView from '../../../components/collection-report-view';
  import containerStatus from './components/container-status.vue';

  export default {
    components: {
      containerStatus,
      CollectionReportView,
      EmptyStatus,
    },
    props: {
      collectorData: {
        type: Object,
        required: true,
      },
    },
    data() {
      return {
        basicLoading: false,
        currentPage: 0,
        isPageOver: false, // 前端分页加载是否结束
        dataListPaged: [], // 将列表数据按 pageSize 分页
        count: 0, // 数据总条数
        pageSize: 30, // 每页展示多少数据
        totalPage: 1,
        size: 'small',
        renderTableList: [
          {
            is_label: false,
            bk_obj_name: '-',
            node_path: '-',
            bk_obj_id: '-',
            label_name: '',
            child: [],
            bk_inst_id: 6,
            bk_inst_name: '-',
          },
        ],
        detail: {
          isShow: false,
          title: this.$t('详情'),
          loading: true,
          content: '',
          log: '',
        },
        dataButton: [
          {
            key: 'all',
            content: this.$t('全部'),
            dataList: {},
          },
          {
            key: 'sec',
            content: this.$t('正常'),
            dataList: {},
          },
          {
            key: 'fal',
            content: this.$t('失败'),
            dataList: {},
          },
          {
            key: 'pen',
            content: this.$t('执行中'),
            dataList: {},
          },
        ],
        collapseColor: {
          type: String,
          default: '#63656E',
        },
        showSetting: true,
        reloadTable: false,
        instance: null,
        clickSec: {
          selected: 'all',
          data: '',
        },
        dataFir: null,
        dataSec: {},
        dataFal: {},
        dataPen: {},
        dataAll: {},
        // 是否支持一键检测
        enableCheckCollector: JSON.parse(window.ENABLE_CHECK_COLLECTOR),
        // 一键检测弹窗配置
        reportDetailShow: false,
        // 一键检测采集项标识
        checkRecordId: '',
      };
    },
    computed: {
      collectProject() {
        return projectManages(this.$store.state.topMenu, 'collection-item');
      },
      isContainer() {
        return this.collectorData.environment === 'container';
      },
      hostIdentifierPriority() {
        return this.$store.getters['globals/globalsData']?.host_identifier_priority ?? ['ip', 'host_name', 'ipv6'];
      },
    },
    created() {
      // 容器日志展示容器日志的内容
      if (this.isContainer) return;
      this.getCollectList();
    },
    beforeDestroy() {
      // 清除定时器
      this.timer && clearInterval(this.timer);
    },
    mounted() {
      // 容器日志展示容器日志的内容
      if (this.isContainer) return;
      this.adadScrollEvent();
    },
    methods: {
      closeTable(val) {
        this.$refs.unfold[val].style.height = this.$refs.unfold[val].style.height === '' ? '43px' : '';
        this.$refs.icon[val].classList.value =
          this.$refs.unfold[val].style.height === ''
            ? 'bk-icon title-icon icon-down-shape'
            : 'bk-icon title-icon icon-right-shape';
      },
      adadScrollEvent() {
        this.scrollontentEl = document.querySelector('.allocation');
        if (!this.scrollontentEl) return;

        this.scrollontentEl.addEventListener('scroll', this.handleScroll, { passive: true });
      },
      // 获取采集状态
      getCollectList(isLoading = true) {
        if (isLoading) {
          this.reloadTable = true;
          this.basicLoading = true;
        }
        this.dataAll = { totalLenght: 0 };
        this.dataSec = { totalLenght: 0 };
        this.dataFal = { totalLenght: 0 };
        this.dataPen = { totalLenght: 0 };
        this.$http
          .request('source/collectList', {
            params: {
              collector_config_id: this.$route.params.collectorId,
            },
            manualSchema: true,
          })
          .then(res => {
            this.dataFir = res.data;
            if (this.dataFir.contents.length !== 0) {
              // 过滤child为空的节点
              this.dataFir.contents = this.dataFir.contents.filter(data => data.child.length);

              for (let x = 0; x < this.dataFir.contents.length; x++) {
                let allSet = [];
                const secSet = [];
                const failSet = [];
                const penSet = [];
                allSet = this.dataFir.contents[x].child;
                for (let i = 0; i < allSet.length; i++) {
                  if (allSet[i].status === 'SUCCESS') {
                    secSet.push(allSet[i]);
                  } else if (allSet[i].status === 'FAILED') {
                    failSet.push(allSet[i]);
                  } else {
                    penSet.push(allSet[i]);
                  }
                }
                this.dataAll[x] = allSet;
                this.dataSec[x] = secSet;
                this.dataFal[x] = failSet;
                this.dataPen[x] = penSet;
                this.dataAll.totalLenght += allSet.length;
                this.dataSec.totalLenght += secSet.length;
                this.dataFal.totalLenght += failSet.length;
                this.dataPen.totalLenght += penSet.length;
                this.reloadTable = false;
              }
              this.dataButton.forEach(item => {
                item.dataList =
                  item.key === 'pen'
                    ? this.dataPen
                    : item.key === 'sec'
                      ? this.dataSec
                      : item.key === 'fal'
                        ? this.dataFal
                        : this.dataAll;
              });
              const sel = this.clickSec.selected;
              this.clickSec.data =
                sel === 'pen'
                  ? this.dataPen
                  : sel === 'sec'
                    ? this.dataSec
                    : sel === 'fal'
                      ? this.dataFal
                      : this.dataAll;

              if (!this.timer) {
                this.dataListPaged = [];
                this.dataListShadow = [];
                this.renderTableList = [];
                this.initPageConf(this.dataFir.contents);
                this.loadPage();
              }

              //  如果存在执行中添加定时器
              if (this.dataPen.totalLenght === 0) {
                clearInterval(this.timer);
                this.timer = null;
              } else {
                if (this.timer) {
                  return 1;
                }
                this.timer = setInterval(() => {
                  this.getCollectList(false);
                }, 10000);
              }
            }
          })
          .catch(e => {
            console.warn(e);
            this.reloadTable = false;
          })
          .finally(() => {
            this.basicLoading = false;
          });
      },
      // 采集状态过滤
      handleChangeGroup(val) {
        this.clickSec.selected = val.key;
        this.clickSec.data = val.dataList;
        this.dataListPaged = [];
        this.dataListShadow = [];
        this.renderTableList = [];
        this.initPageConf(this.dataFir.contents || []);
        this.loadPage();
      },
      // 初始化前端分页
      initPageConf(list) {
        this.currentPage = 0;
        this.isPageOver = false;

        this.count = list.length;
        this.totalPage = Math.ceil(this.count / this.pageSize) || 1;
        this.dataListShadow = list;
        this.dataListPaged = [];
        for (let i = 0; i < this.count; i += this.pageSize) {
          this.dataListPaged.push(this.dataListShadow.slice(i, i + this.pageSize));
        }
      },
      loadPage() {
        this.currentPage += 1;
        this.isPageOver = this.currentPage === this.totalPage;

        if (this.dataListPaged[this.currentPage - 1]) {
          this.renderTableList.splice(this.renderTableList.length, 0, ...this.dataListPaged[this.currentPage - 1]);
          top &&
            this.$nextTick(() => {
              // this.scrollontentEl.scrollTop = top
            });
        }
      },
      handleScroll() {
        if (this.throttle) {
          return;
        }

        this.throttle = true;
        setTimeout(() => {
          this.throttle = false;

          const el = this.scrollontentEl;

          if (this.isPageOver) {
            return;
          }
          if (el.scrollHeight - el.offsetHeight - el.scrollTop < 60) {
            this.loadPage(el.scrollTop);
          }
        }, 200);
      },
      // 重试
      retryClick(val, key) {
        this.reloadTable = true;
        const retryList = [];
        if (key === 'odd') {
          retryList.push(val.instance_id);
        } else {
          if (val.totalLenght === 0) {
            // 判断是否存在失败项
            this.reloadTable = false;
            return 1;
          }
          for (let y = 0; y < key; y++) {
            for (let i = 0; i < val[y].length; i++) {
              retryList.push(val[y][i].instance_id);
            }
          }
        }
        this.$http
          .request('source/retryList', {
            params: {
              collector_config_id: this.$route.params.collectorId,
            },
            data: {
              instance_id_list: retryList,
            },
          })
          .then(() => {
            this.getCollectList();
          })
          .catch(e => {
            console.warn(e);
            this.reloadTable = false
          });
      },
      viewDetail(row) {
        this.detail.isShow = true;
        this.detail.loading = true;
        this.requestDetail(row);
      },
      requestDetail(row) {
        this.$http
          .request('collect/executDetails', {
            params: {
              collector_id: this.$route.params.collectorId,
            },
            query: {
              instance_id: row.instance_id,
              task_id: row.task_id,
            },
          })
          .then(res => {
            if (res.result) {
              this.detail.log = res.data.log_detail;
              this.detail.content = res.data.log_detail;
            }
          })
          .catch(err => {
            this.$bkMessage({
              theme: 'error',
              message: err.message || err,
            });
          })
          .finally(() => {
            this.detail.loading = false;
          });
      },
      closeSlider() {
        this.detail.content = '';
        this.detail.loading = false;
      },
      jsonFormatClick() {
        // this.$router.push({
        //   name: 'jsonFormat',
        //   params: {
        //     collectorId: this.config_id,
        //   },
        //   query: {
        //     spaceUid: this.$store.state.spaceUid,
        //   },
        // });
      },
      viewReport(row) {
        const { cloud_id: cloudId, host_id: hostId, ip } = row;
        this.$http
          .request('collect/runCheck', {
            data: {
              collector_config_id: this.$route.params.collectorId,
              hosts: [
                {
                  bk_cloud_id: cloudId,
                  bk_host_id: hostId,
                  ip,
                },
              ],
            },
          })
          .then(res => {
            if (res.data?.check_record_id) {
              this.reportDetailShow = true;
              this.checkRecordId = res.data.check_record_id;
            }
          });
      },
      getShowIp(row) {
        return row[this.hostIdentifierPriority.find(pItem => Boolean(row[pItem]))] ?? row.ip;
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '../../../../../../scss/mixins/clearfix';
  @import '../../../../../../scss/conf';

  /* stylelint-disable no-descending-specificity */
  .collection-status-container {
    .collect {
      min-width: 1040px;
    }

    .nav-section {
      display: flex;
      justify-content: space-between;

      span {
        display: inline-block;
        margin-right: 10px;
        font-size: 12px;
        color: #bfc0c6;
      }

      .icon-question-circle {
        margin-right: 10px;
        font-size: 16px;
        color: #979ba5;
      }

      :deep(.bk-button) {
        padding: 0 10px;
        font-size: 12px;

        .icon-right-turn-line {
          margin-right: 4px;
          font-size: 18px;
        }
      }
    }

    .table-detail {
      width: 100%;

      div {
        width: 100%;
        height: 42px;
        line-height: 42px;
        user-select: none;
        background-color: #f0f1f5;
        border: 1px solid #dcdee5;
        border-bottom: none;
        border-radius: 2px 2px 0 0;

        :nth-child(2) {
          font-size: 12px;
          font-weight: Bold;
          color: #63656e;
        }

        span {
          font-size: 12px;
          color: #979ba5;
        }

        :nth-child(3) {
          margin-left: 20px;
          color: #2dcb56;
        }

        :nth-child(5) {
          color: #ea3636;
        }
      }
    }

    .text-style {
      display: flex;

      span {
        margin-right: 12px;
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .SUCCESS {
      color: #2dcb56;
    }

    .FAILED {
      color: #ea3636;
    }

    .PENDING {
      color: $primaryColor;
    }

    .button-group {
      font-size: 0;
      border-radius: 3px;

      span {
        display: inline-block;
        height: 32px;
        padding: 0 15px;
        margin: 0;
        font-size: 12px;
        line-height: 30px;
        cursor: pointer;
        border: 1px #c4c6cc solid;
        border-right: none;
      }

      :nth-child(1) {
        border-top-left-radius: 3px;
        border-bottom-left-radius: 3px;
      }

      :nth-child(4) {
        border-right: 1px #c4c6cc solid;
      }

      .button-wit {
        /* stylelint-disable-next-line declaration-no-important */
        color: #63656e !important;
        background-color: white;
      }

      .button-bul {
        /* stylelint-disable-next-line declaration-no-important */
        color: whitesmoke !important;
        background-color: #3a84ff;
      }
    }

    .content-style {
      display: flex;

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

    .title-icon {
      margin-left: 23px;
      font-size: 14px;

      &:hover {
        cursor: pointer;
      }
    }
  }

  .issued-detail {
    .detail-content {
      min-height: calc(100vh - 60px);
      white-space: pre-wrap;
    }

    :deep(.bk-sideslider-wrapper) {
      padding-bottom: 0;

      .bk-sideslider-content {
        color: #c4c6cc;
        background-color: #313238;

        a {
          color: #3a84ff;
        }
      }
    }
  }
</style>
