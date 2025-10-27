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

import { computed, defineComponent, ref } from "vue";
import Stratege from "./strategy";
import QuickFilter from "./quick-filter";
import useLocale from "@/hooks/use-locale";
import EmailSubscription from "./email-subscription";
import ClusterConfig from "./cluster-config";

import "./index.scss";

export default defineComponent({
  name: "TopOperation",
  components: {
    EmailSubscription,
    Stratege,
    QuickFilter,
    ClusterConfig,
  },
  props: {
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    isShowClusterStep: {
      type: Boolean,
      default: true,
    },
    fingerOperateData: {
      type: Object,
      require: true,
    },
    requestData: {
      type: Object,
      require: true,
    },
    totalFields: {
      type: Array,
      require: true,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const clusterConfigRef = ref<any>(null);
    /** 是否创建过策略 */
    const strategyHaveSubmit = ref(false);

    const getDimensionStr = computed(() =>
      props.fingerOperateData?.dimensionList.length
        ? `${t("聚合维度")} : ${props.fingerOperateData.dimensionList.join(
            ", "
          )}`
        : ""
    );
    const getGroupStr = computed(() =>
      props.fingerOperateData?.selectGroupList.length
        ? `${t("分组")} : ${props.fingerOperateData.selectGroupList.join(", ")}`
        : ""
    );
    const getYearStr = computed(() =>
      props.requestData?.year_on_year_hour
        ? `${t("同比")} : ${props.requestData.year_on_year_hour}h`
        : ""
    );

    const isShowGroupTag = computed(
      () =>
        props.clusterSwitch &&
        !props.isShowClusterStep &&
        (getGroupStr.value || getDimensionStr.value || getYearStr.value)
    );

    const isExternal = window.IS_EXTERNAL === true;

    const handleStrategySubmitStatus = (v) => {
      strategyHaveSubmit.value = v;
    };

    const handleCloseGroupTag = () => {
      emit("close-group-tag");
    };
    const handleCloseYearTag = () => {
      emit("close-year-tag");
    };

    const handleFingerOperate = (
      operateType: string,
      val: any,
      isQuery: boolean
    ) => {
      emit("handle-finger-operate", operateType, val, isQuery);
    };

    expose({
      openClusterConfig: () => clusterConfigRef.value?.show(),
    });

    return () => (
      <div class="clustering-nav">
        <div class="operations-main">
          <stratege
            indexId={props.indexId}
            cluster-switch={props.clusterSwitch}
            is-cluster-active={props.isClusterActive}
            strategy-submit-status={handleStrategySubmitStatus}
          />
          <div class="right-operation-main">
            <QuickFilter
              indexId={props.indexId}
              finger-operate-data={props.fingerOperateData}
              request-data={props.requestData}
              total-fields={props.totalFields}
              cluster-switch={props.clusterSwitch}
              strategy-have-submit={strategyHaveSubmit.value}
              is-cluster-active={props.isClusterActive}
              on-handle-finger-operate={handleFingerOperate}
            />
            {!isExternal && (
              <email-subscription
                style="margin: 0 8px"
                indexId={props.indexId}
                isClusterActive={props.isClusterActive}
              />
            )}
            {!isExternal && (
              <ClusterConfig
                ref={clusterConfigRef}
                indexId={props.indexId}
                total-fields={props.totalFields}
              />
            )}
          </div>
        </div>
        {isShowGroupTag.value && (
          <div class="tags-main">
            {getDimensionStr.value && (
              <bk-tag type="stroke">{getDimensionStr.value}</bk-tag>
            )}
            {getGroupStr.value && (
              <bk-tag type="stroke" closable on-close={handleCloseGroupTag}>
                {getGroupStr.value}
              </bk-tag>
            )}
            {getYearStr.value && (
              <bk-tag type="stroke" closable on-close={handleCloseYearTag}>
                {getYearStr.value}
              </bk-tag>
            )}
          </div>
        )}
      </div>
    );
  },
});
