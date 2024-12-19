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
  <div class="basic-info-container">
    <div
      class="deploy-sub"
      v-en-class="'en-deploy'"
    >
      <!-- 数据ID -->
      <div>
        <span>{{ $t('数据ID') }}</span>
        <span>{{ collectorData.bk_data_id || '-' }}</span>
      </div>
      <!-- 名称 -->
      <div>
        <span>{{ $t('名称') }}</span>
        <span>{{ collectorData.collector_config_name || '-' }}</span>
      </div>
      <!-- 数据名 -->
      <div>
        <span>{{ $t('数据名') }}</span>
        <span>{{ collectorData.collector_config_name_en || '-' }}</span>
      </div>
      <!-- 备注说明 -->
      <div>
        <span>{{ $t('备注说明') }}</span>
        <span>{{ collectorData.description || '-' }}</span>
      </div>
      <!-- 数据分类 -->
      <div>
        <span>{{ $t('数据分类') }}</span>
        <span>{{ collectorData.category_name || '-' }}</span>
      </div>
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
      <!-- 日志类型 -->
      <div>
        <span>{{ $t('日志类型') }}</span>
        <span>{{ collectorData.collector_scenario_name || '-' }}</span>
      </div>
      <!-- 容器集群 -->
      <div>
        <span>{{ $t('容器集群') }}</span>
        <span>{{ bcsClusterName }}</span>
      </div>
      <!-- 配置项 -->
      <div>
        <span>{{ $t('配置项') }}</span>
        <div>
          <div
            v-for="(configItem, configIndex) in collectorConfigs"
            class="config-box"
            :key="configIndex"
          >
            <div class="config-title">{{ getFromCharCode(configIndex) }}</div>
            <div class="deploy-sub">
              <!-- 容器环境 -->
              <div>
                <span>{{ $t('容器环境') }}</span>
                <span>{{ configItem.collectorName }}</span>
              </div>
              <!-- Namespace -->
              <div>
                <span>Namespace</span>
                <span
                  v-if="showNameSpace(configItem).length"
                  class="span-warp"
                >
                  <span class="section-operator">{{ nameSpaceType(configItem) }}</span>
                  <span
                    v-for="(spaceItem, spaceIndex) in showNameSpace(configItem)"
                    :key="spaceIndex"
                  >
                    <span>
                      {{ spaceItem }}{{ spaceIndex + 1 !== showNameSpace(configItem).length ? ',' : '' }}&nbsp;
                    </span>
                  </span>
                </span>
                <span v-else>{{ $t('所有') }}</span>
              </div>
              <!-- 关联标签 -->
              <div>
                <span :class="{ 'label-title': isSelectorHaveValue(configItem.label_selector) }">
                  {{ $t('关联标签') }}
                </span>
                <div v-if="isSelectorHaveValue(configItem.label_selector)">
                  <template v-for="(labItem, labKey) in configItem.label_selector">
                    <div
                      v-for="(matchItem, matchKey) of labItem"
                      class="specify-box"
                      :key="`${labKey}_${matchKey}`"
                    >
                      <div
                        class="specify-container justify-bt"
                        v-bk-overflow-tips
                      >
                        <span>{{ matchItem.key }}</span>
                        <div class="operator">{{ matchItem.operator }}</div>
                      </div>
                      <div
                        class="specify-container"
                        v-bk-overflow-tips
                      >
                        <span>{{ matchItem.value }}</span>
                      </div>
                    </div>
                  </template>
                </div>
                <span v-else>{{ $t('所有') }}</span>
              </div>
              <!-- 关联注解 -->
              <div>
                <span :class="{ 'label-title': isSelectorHaveValue(configItem.match_annotations) }">
                  {{ $t('关联注解') }}
                </span>
                <div v-if="isSelectorHaveValue(configItem.match_annotations)">
                  <template v-for="(labItem, labKey) in configItem.match_annotations">
                    <div
                      v-for="(matchItem, matchKey) of labItem"
                      class="specify-box"
                      :key="`${labKey}_${matchKey}`"
                    >
                      <div
                        class="specify-container justify-bt"
                        v-bk-overflow-tips
                      >
                        <span>{{ matchItem.key }}</span>
                        <div class="operator">{{ matchItem.operator }}</div>
                      </div>
                      <div
                        class="specify-container"
                        v-bk-overflow-tips
                      >
                        <span>{{ matchItem.value }}</span>
                      </div>
                    </div>
                  </template>
                </div>
                <span v-else>{{ $t('所有') }}</span>
              </div>
              <!-- 工作负载 -->
              <div class="content-style">
                <span>{{ $t('工作负载') }}</span>
                <div
                  v-if="isSelectorHaveValue(configItem.container)"
                  class="container justify-bt"
                >
                  <template v-for="([speKey, speValue], speIndex) in Object.entries(configItem.container)">
                    <div
                      v-if="speValue"
                      class="container-item"
                      :key="speIndex"
                    >
                      {{ specifyName[speKey] }} : {{ speValue }}
                    </div>
                  </template>
                </div>
                <span v-else>--</span>
              </div>
              <!-- 容器名 -->
              <div class="content-style">
                <span>{{ $t('容器名') }}</span>
                <div
                  v-if="isContainerHaveValue(configItem.containerName)"
                  class="container justify-bt"
                >
                  <template>
                    <div
                      v-for="(conItem, conIndex) in configItem.containerName"
                      class="container-item"
                      :key="conIndex"
                    >
                      {{ conItem }}
                    </div>
                  </template>
                </div>
                <span v-else>--</span>
              </div>
              <!-- 日志路径 -->
              <div>
                <span>{{ $t('日志路径') }}</span>
                <div
                  v-if="configItem.params.paths.length"
                  class="deploy-path"
                >
                  <p
                    v-for="(val, key) in configItem.params.paths"
                    :key="key"
                  >
                    {{ val }}
                  </p>
                </div>
                <span v-else>--</span>
              </div>
              <!-- 日志字符集 -->
              <div>
                <span>{{ $t('字符集') }}</span>
                <span>{{ configItem.data_encoding || '-' }}</span>
              </div>
              <!-- 过滤内容 -->
              <div
                v-if="configItem.params.conditions.type === 'none'"
                class="content-style"
              >
                <span>{{ $t('过滤内容') }}</span>
                <div>--</div>
              </div>
              <div
                v-else-if="isHaveFilter(configItem.params)"
                class="content-style"
              >
                <span>{{ $t('过滤内容') }}</span>
                <div>
                  <p>{{ isMatchType(configItem.params) ? $t('字符串过滤') : $t('分隔符匹配') }}</p>
                  <p v-if="!isMatchType(configItem.params) && configItem.params.conditions.separator">
                    {{ configItem.params.conditions.separator }}
                  </p>
                  <div class="condition-stylex">
                    <div
                      v-for="(fItem, fIndex) in filterGroup(configItem.params)"
                      :key="fIndex"
                    >
                      <span class="title">{{ $t('第{n}组', { n: fIndex + 1 }) }}</span>
                      <div class="column-box">
                        <div class="item-box">
                          <div
                            v-for="(gItem, gIndex) in groupKey(configItem.params)"
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
                            v-if="!isMatchType(configItem.params)"
                            class="item the-column"
                          >
                            {{ $t('第{n}列', { n: item.fieldindex }) }}
                          </div>
                          <div class="item the-column">{{ showOperatorObj(configItem.params)[item.op] }}</div>
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
              <!-- 段日志 -->
              <template v-if="collectorData.collector_scenario_id === 'section'">
                <div class="content-style">
                  <span>{{ $t('段日志参数') }}</span>
                  <div class="section-box">
                    <p>
                      {{ $t('行首正则') }}: <span>{{ configItem.params.multiline_pattern }}</span>
                    </p>
                    <br />
                    <p>
                      <i18n path="最多匹配{0}行，最大耗时{1}秒">
                        <span>{{ configItem.params.multiline_max_lines }}</span>
                        <span>{{ configItem.params.multiline_timeout }}</span>
                      </i18n>
                    </p>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
      <!-- 附加日志标签 -->
      <div>
        <span>{{ $t('附加日志标签') }}</span>
        <template v-if="extraLabelList.length">
          <div>
            <div
              v-for="(extraItem, extraIndex) in extraLabelList"
              :key="extraIndex"
            >
              <div class="specify-box">
                <div
                  class="specify-container justify-bt"
                  v-bk-overflow-tips
                >
                  <span>{{ extraItem.key }}</span>
                  <div class="operator">=</div>
                </div>
                <div
                  class="specify-container"
                  v-bk-overflow-tips
                >
                  <span>{{ extraItem.value }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
        <span v-else> -- </span>
      </div>
      <!-- 上报链路 -->
      <div>
        <span>{{ $t('上报链路') }}</span>
        <span>{{ dataLinkName || '-' }}</span>
      </div>
    </div>
  </div>
</template>

<script>
  import { operatorMappingObj, operatorMapping } from '@/components/collection-access/components/log-filter/type';

  export default {
    props: {
      collectorData: {
        type: Object,
        required: true,
      },
      isLoading: {
        type: Boolean,
        default: false,
      },
    },
    data() {
      return {
        collectorConfigs: [], // config
        extraLabelList: [], // 附加日志标签
        specifyName: {
          // 指定容器中文名
          workload_type: this.$t('应用类型'),
          workload_name: this.$t('应用名称'),
        },
        collectorNameMap: {
          container_log_config: 'Container',
          node_log_config: 'Node',
          std_log_config: this.$t('标准输出'),
        },
        dataLinkName: '--',
        bcsClusterName: '--', // 容器环境集群名
        groupList: [this.$t('过滤参数'), this.$t('操作符'), 'Value'],
      };
    },
    computed: {},
    async created() {
      this.$emit('update:is-loading', true);
      try {
        await this.getLinkData(this.collectorData);
        await this.initContainerConfigData(this.collectorData);
      } catch (error) {
        console.warn(error);
      } finally {
        this.$emit('update:is-loading', false);
      }
    },
    methods: {
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
      /**
       * @desc: 初始化编辑的form表单值
       * @returns { Object } 返回初始化后的Form表单
       */
      async initContainerConfigData(data) {
        // 分yaml模式和ui模式下的config展示
        try {
          this.bcsClusterName = await this.getBcsClusterName(data.bcs_cluster_id);
          const showData = data.yaml_config_enabled ? await this.getYamlConfigData(data.yaml_config) : data;
          this.extraLabelList = showData.extra_labels;
          this.collectorConfigs = showData.configs.map(item => {
            const {
              workload_name,
              workload_type,
              container_name: baseContainerName,
              match_expressions,
              match_labels,
              data_encoding,
              params,
              container: yamlContainer,
              label_selector: yamlSelector,
              annotation_selector: yamlAnnotationSelector,
              namespaces,
              namespaces_exclude,
              match_annotations,
              collector_type: collectorType,
            } = item;
            let container;
            let labelSelector;
            let Annotations;
            let containerName = this.getContainerNameList(baseContainerName);
            if (data.yaml_config_enabled) {
              const { workload_name, workload_type, container_name: yamlContainerName } = yamlContainer;
              container = { workload_name, workload_type };
              containerName = this.getContainerNameList(yamlContainerName);
              labelSelector = yamlSelector;
              Annotations = yamlAnnotationSelector;
            } else {
              container = {
                workload_type,
                workload_name,
              };
              Annotations = {
                match_annotations,
              };
              labelSelector = {
                match_labels,
                match_expressions,
              };
            }
            const collectorName = this.collectorNameMap[collectorType] || '--';
            return {
              namespaces,
              namespaces_exclude,
              data_encoding,
              container,
              collectorName,
              containerName,
              label_selector: labelSelector,
              match_annotations: Annotations,
              params,
            };
          });
        } catch (error) {
          console.warn(error);
        }
      },
      getContainerNameList(containerName = '') {
        const splitList = containerName.split(',');
        if (splitList.length === 1 && splitList[0] === '') return [];
        return splitList;
      },
      async getLinkData(collectorData) {
        try {
          const res = await this.$http.request('linkConfiguration/getLinkList', {
            query: {
              bk_biz_id: this.$store.state.bkBizId,
            },
          });
          this.dataLinkName =
            res.data.find(item => item.data_link_id === collectorData.data_link_id)?.link_group_name || '--';
        } catch (e) {
          console.warn(e);
        }
      },
      getFromCharCode(index) {
        return String.fromCharCode(index + 65);
      },
      async getYamlConfigData(yamlConfig) {
        const defaultConfigData = {
          configs: [],
          extra_labels: [],
        };
        try {
          const res = await this.$http.request('container/yamlJudgement', {
            data: {
              bk_biz_id: this.$store.state.bkBizId,
              bcs_cluster_id: this.collectorData.bcs_cluster_id,
              yaml_config: yamlConfig,
            },
          });
          const { parse_result: parseResult, parse_status: parseStatus } = res.data;
          if (Array.isArray(parseResult) && !parseStatus) return defaultConfigData; // 返回值若是数组则表示yaml解析出错
          if (parseStatus)
            return {
              configs: parseResult.configs,
              extra_labels: parseResult.extra_labels,
            };
        } catch (error) {
          console.warn(error);
          return defaultConfigData;
        }
      },
      handleLeave() {
        this.instance?.destroy(true);
      },
      isSelectorHaveValue(labelSelector = []) {
        return Object.values(labelSelector)?.some(item => item?.length) || false;
      },
      isContainerHaveValue(container = []) {
        return Object.values(container)?.some(item => !!item) || false;
      },
      /**
       * @desc: 获取bcs集群列表名
       */
      async getBcsClusterName(bcsID) {
        try {
          const query = { bk_biz_id: this.$store.state.bkBizId };
          const res = await this.$http.request('container/getBcsList', { query });
          return res.data.find(item => item.id === bcsID)?.name || '--';
        } catch (error) {
          return '--';
        }
      },
      showOperatorObj(params) {
        return Object.keys(operatorMappingObj).reduce((pre, acc) => {
          let newKey = acc;
          if ((this.isMatchType(params) && acc === 'include') || (!this.isMatchType(params) && acc === 'eq'))
            newKey = '=';
          pre[newKey] = operatorMappingObj[acc];
          return pre;
        }, {});
      },
      isHaveFilter(params) {
        if (params.type === 'none') return false;
        return !!params.conditions?.separator_filters?.length;
      },
      isMatchType(params) {
        return params.conditions.type === 'match';
      },
      filterGroup(params) {
        const filters = params.conditions?.separator_filters;
        return this.splitFilters(filters ?? []);
      },
      groupKey(params) {
        return this.isMatchType(params) ? this.groupList.slice(1) : this.groupList;
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
      nameSpaceType(configItem) {
        return configItem.namespaces_exclude?.length ? '!=' : '=';
      },
      showNameSpace(configItem) {
        return configItem.namespaces_exclude?.length ? configItem.namespaces_exclude : configItem.namespaces;
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '@/scss/mixins/flex.scss';
  @import '@/scss/basic.scss';

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
      margin-bottom: 33px;
      color: #63656e;

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
    }

    .label-title {
      margin-top: 7px;
    }

    .content-style {
      display: flex;
      align-items: center;

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

      .container {
        flex-wrap: wrap;

        .container-item {
          padding: 4px 10px;
          margin-right: 8px;
          color: #63656e;
          background: #f0f1f5;
          border-radius: 2px;
        }
      }
    }

    .config-box {
      margin-bottom: 20px;
      margin-left: 24px;
      border: 1px solid #dcdee5;
      border-radius: 2px;

      .deploy-sub {
        padding: 12px 43px 0 0;

        > div {
          margin-bottom: 20px;
        }
      }

      .config-title {
        width: 100%;
        height: 30px;
        padding-left: 11px;
        line-height: 30px;
        color: #63656e;
        background: #f0f1f5;
        border-bottom: 1px solid #dcdee5;
      }
    }

    .section-operator,
    %section-operator {
      height: 24px;
      padding: 0 6px;
      font-size: 14px;
      font-weight: 700;
      line-height: 24px;
      color: #ff9c01;
      text-align: center;
      background: #fff;
      border-radius: 2px;
    }

    .specify-box {
      display: flex;
      flex-flow: wrap;
      min-width: 700px;
      padding: 2px 16px;
      margin-bottom: 8px;
      margin-left: 24px;
      background: #f5f7fa;
      border-radius: 2px;

      .specify-container {
        width: 50%;
        height: 30px;
        overflow: hidden;
        line-height: 28px;
        text-overflow: ellipsis;
        white-space: nowrap;

        span {
          font-size: 14px;
          color: #63656e;
        }

        .operator {
          @extend %section-operator;
        }

        :last-child {
          margin-left: 12px;
        }
      }
    }
  }

  .span-warp {
    display: flex;
    flex-wrap: wrap;
    line-height: 24px;
  }

  .justify-bt {
    align-items: center;

    @include flex-justify(space-between);
  }
</style>
