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
  <div class="advanced-option">
    <div class="advanced-form-item">
      <div
        v-en-style="'flex: 0 0 170px'"
        class="item-label"
      >
        {{ $t('周期') }}
      </div>
      <div class="item-container cycle">
        <!-- <bk-select class="cycle-select" v-model="cycle.value" :clearable="false">
          <bk-option v-for="(time, index) in cycle.list" :key="index" :name="time.name" :id="time.id"></bk-option>
        </bk-select> -->
        <cycle-input
          v-model="cycle.value"
          :need-auto="false"
          class="cycle-input"
          :min-sec="10"
        />
      </div>
    </div>
    <div
      v-show="isHttp"
      class="advanced-form-item"
    >
      <div
        v-en-style="'flex: 0 0 170px'"
        class="item-label"
      >
        {{ $t('期待返回码') }}
      </div>
      <div class="item-container code">
        <bk-input
          v-model="response.code"
          class="code-input"
          :placeholder="$t('HTTP请求返回码，如200，304，404等...')"
        />
      </div>
    </div>
    <div
      v-if="isUdp"
      class="advanced-form-item"
    >
      <div
        v-en-style="'flex: 0 0 170px'"
        class="item-label"
      >
        {{ $t('等待响应') }}
      </div>
      <div class="item-container flex-center response">
        <bk-switcher
          v-model="waitEmptyResponse"
          theme="primary"
          @change="handleWaitEmptyResponse"
        />
        <div
          v-bk-tooltips.top="$t('拨测节点采集器版本低于2.7.3.184时该配置不生效，默认等待响应')"
          class="hint-icon ml10"
        >
          <span class="icon-monitor icon-tips icon" />
        </div>
      </div>
    </div>
    <div
      v-if="isUdp && waitEmptyResponse"
      class="advanced-form-item"
    >
      <div
        v-en-style="'flex: 0 0 170px'"
        class="item-label"
      >
        {{ $t('期待响应格式') }}
      </div>
      <div class="item-container response-format flex-center">
        <bk-select
          v-model="resFormat"
          class="format-select"
        >
          <bk-option
            v-for="item in responseFormatOptions"
            :id="item.id"
            :key="item.id"
            :name="item.name"
          />
        </bk-select>
      </div>
    </div>
    <div
      v-if="!isIcmp && (isUdp ? waitEmptyResponse : true)"
      class="advanced-form-item"
    >
      <div
        v-en-style="'flex: 0 0 170px'"
        class="item-label"
      >
        {{ $t('期待响应信息') }}
      </div>
      <div class="item-container response">
        <bk-select
          v-model="response.relation.value"
          class="response-select"
          :style="{ 'border-right-color': focusInput ? '#3c96ff' : focusSelect ? '#3a84ff' : '#c4c6cc' }"
          :clearable="false"
          @click.native="handleFocus(true)"
          @toggle="handleFocus"
        >
          <bk-option
            v-for="(item, index) in response.relation.list"
            :id="item.id"
            :key="index"
            :name="item.name"
          />
        </bk-select>
        <bk-input
          v-model="response.message"
          :class="['response-input', focusSelect ? 'hide-border' : '']"
          :placeholder="$t('通过指定匹配内容来检查响应是否正确，为空则不做匹配检查')"
          @focus="handleFocusInput"
          @blur="focusInput = false"
        />
        <div
          v-bk-tooltips.top="$t('系统会自动创建该告警策略，响应信息匹配失败将会产生告警。')"
          class="hint-icon"
        >
          <span class="icon-monitor icon-tips" />
        </div>
      </div>
    </div>
    <!-- <div class="advanced-form-item" v-show="isHttp">
      <div class="item-label">{{ $t('SSL证书校验') }}</div>
      <div class="item-container">
        <bk-radio-group v-model="isSSL">
          <bk-radio :value="true">{{ $t('是') }}</bk-radio>
          <bk-radio :value="false">{{ $t('否') }}</bk-radio>
        </bk-radio-group>
      </div>
    </div> -->
    <div
      v-if="!isIcmp"
      class="advanced-form-item"
    >
      <div
        v-en-style="'flex: 0 0 170px'"
        class="item-label"
      >
        {{ $t('地理位置') }}
      </div>
      <div class="item-container location">
        <bk-select
          v-model="location.value"
          class="location-select"
          searchable
        >
          <bk-option
            v-for="(item, index) in location.list"
            :id="item.cn"
            :key="index"
            style="width: 212px"
            :name="item.cn"
          />
        </bk-select>
        <bk-select
          v-show="citys.length"
          v-model="location.city"
          class="location-select"
        >
          <bk-option
            v-for="(city, index) in citys"
            :id="city.cn"
            :key="index"
            style="width: 212px"
            :name="city.cn"
          />
        </bk-select>
      </div>
    </div>
    <!-- <div :class="['advanced-form-item', headers.length > 1 ? 'headers' : '']" v-show="isHttp">
      <div class="item-label">{{ $t('头信息') }}</div>
      <div class="item-container">
        <div
          :class="['item-header', headers.length > 1 ? 'item-bottom' : '']"
          v-for="(item, index) in headers"
          :key="index"
        >
          <bk-select class="header-select" v-model="item.name">
            <bk-option
              style="width: 218px"
              v-for="(header, headerIndex) in item.list"
              :key="headerIndex"
              :id="header"
              :name="header"
            ></bk-option>
          </bk-select>
          <bk-input class="header-input" v-model="item.value"></bk-input>
          <div class="operation">
            <span class="bk-icon icon-plus-circle" @click="addHttpHeader"></span>
            <span v-show="headers.length > 1" class="bk-icon icon-minus-circle" @click="removeHttpHeader(index)"></span>
          </div>
        </div>
      </div>
    </div> -->
    <template v-if="isIcmp">
      <div class="advanced-form-item">
        <div
          v-en-style="'flex: 0 0 200px'"
          class="item-label"
        >
          {{ $t('周期内连续探测') }}
        </div>
        <div class="item-container response">
          <bk-input
            v-model="response.totalNum"
            type="number"
            :min="1"
            :max="20"
            style="width: 160px"
          />
        </div>
      </div>
      <div class="advanced-form-item">
        <div
          v-en-style="'flex: 0 0 170px'"
          class="item-label"
        >
          {{ $t('探测包大小') }}
        </div>
        <div class="item-container response">
          <bk-input
            v-model="response.size"
            type="number"
            :min="24"
            :max="65507"
            style="width: 160px"
          />
        </div>
      </div>
    </template>
  </div>
</template>
<script>
import { countryList } from 'monitor-api/modules/commons';
import { getHttpHeaders } from 'monitor-api/modules/uptime_check';

import CycleInput from '../../../../components/cycle-input/cycle-input.tsx';

const DEFAULT_INTERVAL = 60; // 默认周期 单位:秒
const JOINER = '|';
/** 响应格式可选项 */
export const RESPONSE_FORMAT_OPTIONS = [
  {
    id: 'raw',
    name: 'raw',
  },
  {
    id: 'hex',
    name: 'hex',
  },
];
export default {
  name: 'AdvancedOption',
  components: {
    CycleInput,
  },
  props: {
    protocol: {
      type: String,
      default: 'HTTP',
    },
    options: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      focusSelect: false,
      focusInput: false,
      cycle: {
        list: [
          {
            id: 1,
            name: this.$t('1 分钟'),
          },
          {
            id: 5,
            name: this.$t('5 分钟'),
          },
        ],
        value: DEFAULT_INTERVAL,
      },
      response: {
        code: '',
        message: '',
        size: 68,
        totalNum: 3,
        relation: {
          list: [
            {
              id: 'in',
              name: this.$t('包含'),
            },
            {
              id: 'nin',
              name: this.$t('不包含'),
            },
            {
              id: 'reg',
              name: this.$t('正则'),
            },
          ],
          value: 'nin',
        },
      },
      isSSL: false,
      location: {
        list: [],
        value: '',
        city: '',
      },
      headers: [
        {
          list: [],
          name: '',
          value: '',
        },
      ],
      responseFormatOptions: RESPONSE_FORMAT_OPTIONS,
      resFormat: 'hex',
      waitEmptyResponse: true,
    };
  },
  computed: {
    citys() {
      const country = this.location.list.find(item => item.cn === this.location.value);
      if (country?.children.length) {
        return country.children;
      }
      return [];
    },
    isHttp() {
      return this.protocol === 'HTTP';
    },
    isIcmp() {
      return this.protocol === 'ICMP';
    },
    isUdp() {
      return this.protocol === 'UDP';
    },
  },
  watch: {
    options: {
      handler(val) {
        this.setAdvancedOptionsData(val);
      },
      deep: true,
    },
  },
  created() {
    this.getHttpHeaders();
    this.getLocation();
  },
  methods: {
    handleFocus(val) {
      this.focusSelect = val;
      this.focusInput = false;
    },
    handleFocusInput() {
      this.focusSelect = false;
      this.focusInput = true;
    },
    getHttpHeaders() {
      getHttpHeaders().then(data => {
        this.headers[0].list = data;
      });
    },
    getLocation() {
      countryList().then(data => {
        if (data.length) {
          this.location.list = data;
        }
      });
      // .fail(() => {
      //     this.$bkMessage({
      //         theme: 'error',
      //         message: '获取地理位置数据失败'
      //     })
      // })
    },
    addHttpHeader() {
      const header = JSON.parse(JSON.stringify(this.headers[0].list));
      this.headers.push({
        list: header,
        name: '',
        value: '',
      });
    },
    removeHttpHeader(index) {
      this.headers.splice(index, 1);
    },
    getValue() {
      const headers = JSON.parse(JSON.stringify(this.headers));
      const header =
        headers[0].name && headers[0].value ? headers.map(item => ({ name: item.name, value: item.value })) : [];
      const { response } = this;
      const params = {
        total_num: response.totalNum,
        size: response.size,
        period: this.cycle.value,
        response_code: response.code.trim(),
        response: response.message || null,
        response_format: this.isUdp
          ? `${this.resFormat || 'hex'}${JOINER}${response.relation.value}`
          : response.relation.value,
        insecure_skip_verify: this.isSSL,
        headers: header,
        location: { bk_state_name: this.location.value, bk_province_name: this.location.city },
      };
      if (this.isUdp) {
        params.wait_empty_response = this.waitEmptyResponse;
      }
      return params;
    },
    setAdvancedOptionsData(data) {
      let responseFormat = 'nin';
      if (data.response_format) {
        const res = data.response_format.split(JOINER);
        if (res.length > 1) {
          this.resFormat = res[0];
          responseFormat = res[1];
        } else {
          responseFormat = res[0];
        }
      }
      this.cycle.value = data.period || DEFAULT_INTERVAL;
      this.response.code = data.response_code || '';
      // this.response.relation.value = data.response_format || 'nin';
      this.response.relation.value = responseFormat;
      this.response.message = data.response || '';
      this.response.totalNum = data.total_num || 3;
      this.response.size = data.size || 68;
      this.isSSL = Boolean(data.insecure_skip_verify);
      if (!this.isIcmp) {
        try {
          const { headers = [] } = data;
          const headerTemplate = JSON.parse(JSON.stringify(this.headers[0]));
          headers.forEach((item, index) => {
            if (!this.headers[index]) {
              this.headers.push(headerTemplate);
            }
            this.headers[index].name = item.name;
            this.headers[index].value = item.value;
          });
        } catch (error) {
          console.error(error);
        }
        this.location.value = data.location?.bk_state_name || '';
        this.location.city = data.location?.bk_province_name || '';
      }
      if (this.isUdp) {
        this.waitEmptyResponse = data.wait_empty_response;
      }
    },
    setDefaultData() {
      this.cycle.value = DEFAULT_INTERVAL;
      this.response.code = '';
      this.response.message = '';
      this.isSSL = true;
      this.response.relation.value = 'nin';
      this.location.city = '';
      this.location.value = '';
      this.response.size = 68;
      this.response.totalNum = 3;
      this.headers = [
        {
          list: [],
          name: '',
          value: '',
        },
      ];
      this.getHttpHeaders();
    },
    /* 关闭等待响应重置以下数据 */
    handleWaitEmptyResponse(value) {
      if (!value) {
        this.resFormat = 'hex';
        this.response.relation.value = 'nin';
        this.response.message = '';
      }
    },
  },
};
</script>
<style lang="scss" scoped>
/* stylelint-disable-next-line at-rule-no-unknown */
@mixin hint-icon {
  display: inline-block;
  width: 18px;
  height: 18px;
  margin-left: 10px;
  font-size: 16px;
  line-height: 18px;
  cursor: pointer;
  fill: #fff;
}

.advanced-option {
  width: 100%;

  .advanced-form-item {
    display: flex;
    flex-direction: row;
    align-items: center;
    margin-bottom: 20px;
    color: #63656e;

    &.headers {
      align-items: start;
    }

    .item-label {
      flex: 0 0 102px;
      margin-right: 15px;
      font-size: 12px;
      text-align: right;
    }

    .item-container {
      &.response {
        display: inline-flex;
        align-items: center;

        .response-select {
          width: 94px;
          border-radius: 2px 0 0 2px;
        }

        .response-input {
          width: 409px;

          :deep(.bk-form-input) {
            border-left: 0;
            border-radius: 0 2px 2px 0;
          }
        }

        .hint-icon {
          /* stylelint-disable-next-line at-rule-no-unknown */
          @include hint-icon();
        }
      }

      &.response-format {
        &.flex-center {
          display: flex;
          align-items: center;

          .item-checkbox {
            margin-left: 16px;
          }
        }

        .format-select {
          width: 120px;
        }

        .hint-icon {
          /* stylelint-disable-next-line at-rule-no-unknown */
          @include hint-icon();
        }
      }

      .item-label {
        flex: 0 0 100px;
        margin-right: 15px;
        font-size: 14px;
        text-align: right;
      }

      .icon-tips:hover {
        color: #3a84ff;
      }

      .item-header {
        display: flex;

        .operation {
          display: inline-flex;
          align-items: center;
          justify-content: space-between;
          width: 42px;

          .bk-icon {
            font-size: 18px;
            cursor: pointer;
          }
        }

        &.item-bottom {
          margin-bottom: 10px;
        }

        .header-select,
        .header-input {
          width: 220px;
          margin-right: 10px;
        }
      }

      :deep(.bk-form-radio) {
        margin-right: 62px;
        margin-bottom: 0;

        .icon-check {
          &::before {
            content: none;
          }
        }
      }

      :deep(.bk-select) {
        background-color: #fff;
      }

      &.location {
        display: inline-flex;
        align-items: center;

        .location-select {
          width: 218px;

          &:first-child {
            margin-right: 10px;
          }
        }

        .hint-icon {
          /* stylelint-disable-next-line at-rule-no-unknown */
          @include hint-icon();
        }
      }

      .code-input {
        width: 503px;
      }

      .cycle-select {
        width: 160px;
      }

      :deep(.cycle-input) {
        width: 120px;

        .cycle-unit {
          min-width: 34px;

          &::before {
            background-color: #c4c6cc;
          }

          &.line-active {
            &::before {
              background-color: #3a84ff;
            }
          }
        }
      }
    }
  }
}
</style>
