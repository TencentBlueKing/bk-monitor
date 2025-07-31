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
  <div class="alarm-shield-scope">
    <!-- 所属start -->
    <div class="set-shield-config-item">
      <div class="item-label item-required">
        {{ $t('所属') }}
      </div>
      <div class="item-container">
        <bk-select
          v-model="biz.value"
          :clearable="false"
          readonly
        >
          <bk-option
            v-for="(item, index) in biz.list"
            :id="item.id"
            :key="index"
            :name="item.text"
          />
        </bk-select>
      </div>
    </div>
    <!-- 所属end -->

    <!-- 屏蔽范围start -->
    <div
      class="set-shield-config-item shield-scope"
      :class="{ edit: isEdit }"
    >
      <div class="item-label item-required">
        {{ $t('屏蔽维度') }}
      </div>
      <div class="item-container">
        <div
          v-if="!isEdit"
          class="bk-button-group"
        >
          <bk-button
            v-for="(item, index) in bkGroup.list"
            :key="index"
            class="scope-item"
            :class="{ 'is-selected': bkGroup.value === item.id }"
            @click.stop="handleScopeChange(item.id)"
          >
            {{ item.name }}
          </bk-button>
        </div>
        <bk-table
          v-else-if="bkGroup.value !== 'biz'"
          ref="bkTable"
          class="static-table"
          :data="tableData"
          :max-height="450"
        >
          <bk-table-column
            :label="labelMap[bkGroup.value]"
            prop="name"
          />
        </bk-table>
        <span v-else> {{ $t('业务') }} </span>
      </div>
    </div>

    <!-- 提示信息start -->
    <div
      v-if="!isEdit"
      class="set-shield-config-item tips-wrapper"
      :class="{ 'tab-biz': bkGroup.value === 'biz' }"
    >
      <div class="item-label" />
      <div class="item-container">
        <span class="tips-text"><i class="icon-monitor icon-tips item-icon" />{{ tips[bkGroup.value] }}</span>
      </div>
    </div>
    <!-- 提示信息end -->

    <div
      v-show="bkGroup.value !== 'biz' && !isEdit"
      class="set-shield-config-item topo-selector"
    >
      <div class="item-label" />
      <div
        style="width: 80%"
        class="item-container"
      >
        <alarm-shield-ipv6
          v-if="initialized"
          :checked-value="ipv6Value"
          :origin-checked-value="originIpv6Value"
          :shield-dimension="bkGroup.value"
          :show-dialog="showIpv6Dialog"
          :show-view-diff="isClone"
          @change="handleValueChange"
          @closeDialog="handleIpv6DialogChange"
        />
        <div
          v-if="targetError"
          class="item-container-error"
        >
          {{ $t('选择屏蔽目标') }}
        </div>
      </div>
    </div>

    <!-- 屏蔽范围end -->
    <shield-date-config
      ref="noticeDate"
      v-model="commonDateData"
      :is-clone="isClone"
    />
    <div class="set-shield-config-item">
      <div class="item-label cause-label">
        {{ $t('屏蔽原因') }}
      </div>
      <div class="item-container shield-cause">
        <bk-input
          v-model="shieldDesc"
          :maxlength="100"
          :row="3"
          type="textarea"
        />
      </div>
    </div>
    <shiled-notice ref="shieldNotice" />
    <div class="set-shield-config-item">
      <div class="item-label" />
      <div class="item-container mb20">
        <bk-button
          theme="primary"
          @click="handleSubmit"
        >
          {{ $t('提交') }}
        </bk-button>
        <bk-button
          class="ml10"
          @click="handleCancel"
        >
          {{ $t('取消') }}
        </bk-button>
      </div>
    </div>
  </div>
</template>
<script>
import { addShield, editShield } from 'monitor-api/modules/shield';
import { deepClone } from 'monitor-common/utils';

import { transformMonitorToValue, transformValueToMonitor } from '../../../../components/monitor-ip-selector/utils';
import ShieldDateConfig from '../../alarm-shield-components/alarm-shield-date';
import ShiledNotice from '../../alarm-shield-components/alarm-shield-notice';
import AlarmShieldIpv6, {
  Ipv6FieldMap,
  ShieldDetailTargetFieldMap,
  ShieldDimension2NodeType,
} from './alarm-shield-ipv6';

export default {
  name: 'AlarmShieldScope',
  components: {
    ShieldDateConfig,
    ShiledNotice,
    AlarmShieldIpv6,
    // ShieldTarget
  },
  model: {
    prop: 'commonDateData',
    event: 'changeCommonDateData',
  },
  props: {
    shieldData: {
      type: Object,
      default: () => ({}),
    },
    commonDateData: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    const defaultData = this.generationDefaultData();
    return {
      isEdit: false,
      isClone: false,
      isCreate: false,
      tips: {
        instance: this.$t('服务实例屏蔽: 屏蔽告警中包含该实例的通知'),
        ip: this.$t('主机屏蔽: 屏蔽告警中包含该IP通知,包含对应的实例'),
        node: this.$t('节点屏蔽: 屏蔽告警中包含该节点下的所有IP和实例的通知'),
        biz: this.$t('业务屏蔽: 屏蔽告警中包含该业务的所有通知'),
      },
      ...defaultData,
    };
  },
  computed: {
    isInstance() {
      return this.bkGroup.value === 'instance';
    },
    prop() {
      return this.bkGroup.value === 'ip' ? 'ip' : 'name';
    },
  },
  watch: {
    shieldData: {
      handler(newVal) {
        switch (this.$route.name) {
          case 'alarm-shield-edit':
            this.handleSetEditOrCloneData(newVal);
            break;
          case 'alarm-shield-clone':
            this.initialized = false;
            this.handleSetEditOrCloneData(newVal);
            this.$nextTick(() => (this.initialized = true));
            break;
          default:
            break;
        }
      },
      deep: true,
    },
  },
  mounted() {
    switch (this.$route.name) {
      case 'alarm-shield-edit':
        this.isEdit = true;
        this.isCreate = false;
        break;
      case 'alarm-shield-clone':
        this.isClone = true;
        this.isCreate = false;
        break;
      default:
        this.isCreate = true;
        break;
    }
  },
  activated() {
    const defaultData = this.generationDefaultData();
    Object.keys(defaultData).forEach(key => {
      this[key] = defaultData[key];
    });
    this.biz.list = this.$store.getters.bizList;
    this.biz.value = this.$store.getters.bizId;
  },
  methods: {
    generationDefaultData() {
      return {
        biz: {
          list: [],
          value: '',
        },
        tableData: [],
        labelMap: {
          ip: this.$t('主机'),
          instance: this.$t('服务实例'),
          node: this.$t('节点名称'),
          biz: this.$t('业务'),
        },
        shieldDesc: '',
        bkGroup: {
          list: [
            { name: this.$t('button-服务实例'), id: 'instance' },
            { name: this.$t('button-主机'), id: 'ip' },
            { name: this.$t('button-拓扑节点'), id: 'node' },
            { name: this.$t('button-业务'), id: 'biz' },
          ],
          value: 'ip',
        },
        targetError: false,
        showIpv6Dialog: false,
        ipv6Value: {},
        originIpv6Value: {},
        initialized: true,
      };
    },
    handleScopeChange(v) {
      this.bkGroup.value = v;
      this.showIpv6Dialog = v !== 'biz';
    },
    // 处理编辑和克隆的数据
    handleSetEditOrCloneData(data) {
      const cycleConfig = data.cycle_config;
      const cycleMap = { 1: 'single', 2: 'day', 3: 'week', 4: 'month' };
      const type = cycleMap[cycleConfig.type];
      const isSingle = cycleConfig.type === 1;
      const shieldDate = {};
      shieldDate.typeEn = type;
      shieldDate[type] = {
        list: [...cycleConfig.day_list, ...cycleConfig.week_list],
        range: isSingle ? [data.begin_time, data.end_time] : [cycleConfig.begin_time, cycleConfig.end_time],
      };
      shieldDate.dateRange = isSingle ? [] : [data.begin_time, data.end_time];
      this.$refs.noticeDate.setDate(shieldDate);
      if (data.shield_notice) {
        const shieldNoticeData = {
          notificationMethod: data.notice_config.notice_way,
          noticeNumber: data.notice_config.notice_time,
          member: {
            value: data.notice_config.notice_receiver.map(item => item.id),
          },
        };
        this.$refs.shieldNotice.setNoticeData(shieldNoticeData);
      }
      this.biz.value = data.bk_biz_id;
      this.shieldDesc = data.description;
      this.bkGroup.value = data.scope_type;
      if (this.bkGroup.value !== 'biz') {
        this.tableData = data.dimension_config.target.map(item => ({ name: item }));
        const targetList = data.dimension_config?.[ShieldDetailTargetFieldMap[data.scope_type]] || [];
        this.ipv6Value =
          data.scope_type === 'instance'
            ? {
                [Ipv6FieldMap[data.scope_type]]: targetList.map(id => ({ service_instance_id: id })),
              }
            : transformMonitorToValue(targetList, ShieldDimension2NodeType[data.scope_type]);
        this.originIpv6Value = deepClone(this.ipv6Value);
      }
    },
    handleGetShieldCycle() {
      const result = this.$refs.noticeDate.getDateData();
      if (!result) return;
      const cycleDate = result[result.typeEn];
      const isSingle = result.typeEn === 'single';
      const params = {
        begin_time: isSingle ? '' : cycleDate.range[0],
        end_time: isSingle ? '' : cycleDate.range[1],
        day_list: result.typeEn === 'month' ? result.month.list : [],
        week_list: result.typeEn === 'week' ? result.week.list : [],
        type: result.type,
      };
      return {
        begin_time: isSingle ? cycleDate.range[0] : result.dateRange[0],
        end_time: isSingle ? cycleDate.range[1] : result.dateRange[1],
        cycle_config: params,
      };
    },
    handleDimensionConfig() {
      const dimension = this.bkGroup.value;
      const dimensionConfig = { scope_type: dimension };
      if (dimension !== 'biz') {
        const data = this.ipv6Value?.[Ipv6FieldMap[dimension]];
        if (!data?.length) {
          this.targetError = true;
          return;
        }
        dimensionConfig.target = transformValueToMonitor(this.ipv6Value, ShieldDimension2NodeType[dimension]);
      }
      return dimensionConfig;
    },
    handleParams() {
      const cycleConfig = this.handleGetShieldCycle();
      const noticeData = this.$refs.shieldNotice.getNoticeConfig();
      if (!cycleConfig || !noticeData) return;
      const params = {
        category: 'scope',
        ...cycleConfig,
        shield_notice: typeof noticeData !== 'boolean',
        notice_config: {},
        description: this.shieldDesc,
      };
      if (params.shield_notice) {
        params.notice_config = {
          notice_time: noticeData.notice_time,
          notice_way: noticeData.notice_way,
          notice_receiver: noticeData.notice_receiver,
        };
      }
      if (this.isEdit) {
        params.id = this.$route.params.id;
      } else {
        const config = this.handleDimensionConfig();
        if (!config) return;
        params.dimension_config = config;
      }
      return params;
    },
    handleSubmit() {
      const params = this.handleParams();
      if (!params) return;
      this.$emit('update:loading', true);
      const ajax = this.isEdit ? editShield : addShield;
      let text = this.$t('创建屏蔽成功');
      if (this.isEdit) {
        text = this.isEdit && this.$t('编辑屏蔽成功');
      } else if (this.isClone) {
        text = this.isClone && this.$t('克隆屏蔽成功');
      }
      ajax(params)
        .then(() => {
          this.$router.push({ name: 'alarm-shield', params: { refresh: true } });
          this.$bkMessage({ theme: 'success', message: text, ellipsisLine: 0 });
        })
        .catch(() => {})
        .finally(() => {
          this.$emit('update:loading', false);
        });
    },
    handleCancel() {
      this.$router.back();
    },
    handleIpv6DialogChange() {
      this.targetError = false;
      this.showIpv6Dialog = false;
    },
    handleValueChange({ value }) {
      this.ipv6Value = { ...this.ipv6Value, ...value };
    },
  },
};
</script>
<style lang="scss" scoped>
.alarm-shield-scope {
  padding: 40px 0 0 30px;

  .set-shield-config-item {
    display: flex;
    flex-direction: row;
    align-items: center;
    margin-bottom: 20px;
    font-size: 14px;
    color: #63656e;

    .item-label {
      position: relative;
      flex: 0 0;
      min-width: 110px;
      margin-right: 24px;
      text-align: right;

      &.cause-label {
        position: relative;
        top: -18px;
      }
    }

    &.shield-scope {
      margin-bottom: 8px;
    }

    &.topo-selector {
      margin-bottom: 26px;
    }

    &.edit {
      align-items: flex-start;
      margin-bottom: 26px;

      .item-label {
        top: 4px;
      }
    }

    &.tips-wrapper {
      margin-bottom: 10px;
    }

    &.tab-biz {
      margin-bottom: 28px;
    }

    .tips-text {
      display: flex;
      align-items: center;
      font-size: 12px;
    }

    .icon-tips {
      margin-right: 6px;
      font-size: 14px;
      line-height: 1;
      color: #979ba5;
    }

    .item-required::after {
      position: absolute;
      top: 2px;
      right: -9px;
      color: red;
      content: '*';
    }

    .item-container {
      // width: 836px;
      .scope-item {
        width: 168px;
      }

      :deep(.bk-textarea-wrapper .bk-form-textarea.textarea-maxlength) {
        margin-bottom: 0px;
      }

      :deep(.bk-form-textarea) {
        min-height: 60px;
      }

      :deep(.bk-table::before) {
        height: 0;
      }

      .static-table {
        width: 836px;

        :deep(.cell) {
          padding-left: 30px;
        }

        &:before {
          height: 1px;
        }
      }

      &.shield-cause {
        width: 836px;
      }

      &-error {
        font-size: 12px;
        color: #ea3636;
      }
    }

    .bk-select {
      width: 413px;
    }
  }

  :deep(.views-container) {
    /* stylelint-disable-next-line declaration-no-important */
    width: 100% !important;

    .ip-selector-view-host {
      /* stylelint-disable-next-line declaration-no-important */
      width: 88% !important;
    }
  }
}
</style>
