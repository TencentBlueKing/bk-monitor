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

import { defineComponent, ref, computed, watch, onMounted } from "vue";
import $http from "@/api";
import useStore from "@/hooks/use-store";
import { type ClusteringInfo } from "@/services/retrieve";
import { type IResponseData } from "@/services/type";
import ConfigItem from "./config-item";

import "./index.scss";

export const enum StrategyType {
  NEW_CLASS = "new_cls_strategy",
  SUDDEN_INCREASE = "normal_strategy",
}

export default defineComponent({
  name: "Strategy",
  components: {
    ConfigItem,
  },
  props: {
    strategySubmitStatus: {
      type: Function, // (v: boolean) => boolean
    },
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, {}) {
    let baseAlarmConfigData = {
      interval: "30",
      threshold: "1",
      level: 2,
      user_groups: [],
      label_name: [],
    };
    let baseIncreaseConfigData = {
      level: 2,
      sensitivity: 5,
      user_groups: [],
      label_name: [],
    };

    const store = useStore();

    const strategyConfigData = ref({
      /** 新类策略初始数据 */
      [StrategyType.NEW_CLASS]: structuredClone(baseAlarmConfigData),
      /** 数据突增策略初始数据 */
      [StrategyType.SUDDEN_INCREASE]: structuredClone(baseIncreaseConfigData),
    });
    const labelName = ref([]);
    /** 新类告警策略是否保存过 */
    const alarmIsSubmit = ref(false);
    /** 数量突增告警告警是否保存过 */
    const increaseIsSubmit = ref(false);

    const bkBizId = computed(() => store.state.bkBizId);

    watch(alarmIsSubmit, () => {
      props.strategySubmitStatus?.(alarmIsSubmit.value);
    });

    /** 重置表单参数 */
    const resetStrategyConfigData = (type = StrategyType.NEW_CLASS) => {
      Object.assign(
        strategyConfigData.value[type],
        type === StrategyType.NEW_CLASS
          ? baseAlarmConfigData
          : baseIncreaseConfigData,
      );
    };

    /** 获取信息 */
    const requestStrategyInfo = async (
      strategyType: StrategyType = StrategyType.NEW_CLASS,
    ) => {
      try {
        const res = (await $http.request("retrieve/getClusteringInfo", {
          params: {
            index_set_id: props.indexId,
            strategy_type: strategyType,
          },
        })) as IResponseData<ClusteringInfo>;
        return { data: res.data, type: strategyType };
      } catch (error) {
        return { type: strategyType };
      }
    };

    const initStrategyInfo = async () => {
      try {
        const values = await Promise.all([
          requestStrategyInfo(StrategyType.NEW_CLASS),
          requestStrategyInfo(StrategyType.SUDDEN_INCREASE),
        ]);
        values.forEach((vItem) => {
          const isSubmit = Object.keys(vItem.data!).length > 0;
          if (vItem.type === StrategyType.NEW_CLASS) {
            alarmIsSubmit.value = isSubmit;
          } else {
            increaseIsSubmit.value = isSubmit;
          }
          if (isSubmit) {
            Object.assign(strategyConfigData.value[vItem.type], vItem.data);
          } else {
            resetStrategyConfigData(vItem.type);
          }
        });
      } catch (error) {
        resetStrategyConfigData(error.type);
      } finally {
        labelName.value = [
          ...new Set(
            ...Object.values(strategyConfigData.value).map(
              (item) => item.label_name,
            ),
          ),
        ];
      }
    };

    onMounted(() => {
      if (!props.clusterSwitch || !props.isClusterActive) {
        return;
      }
      initStrategyInfo();
    });

    return () => (
      <div class="strategy-container">
        <config-item
          configData={strategyConfigData.value}
          bkBizId={bkBizId.value}
          configured={alarmIsSubmit.value}
          indexId={props.indexId}
          labelName={labelName.value}
          type={StrategyType.NEW_CLASS}
          on-refresh-strategy-info={initStrategyInfo}
        />
        <config-item
          configData={strategyConfigData.value}
          bkBizId={bkBizId.value}
          configured={increaseIsSubmit.value}
          indexId={props.indexId}
          labelName={labelName.value}
          type={StrategyType.SUDDEN_INCREASE}
          on-refresh-strategy-info={initStrategyInfo}
        />
      </div>
    );
  },
});
