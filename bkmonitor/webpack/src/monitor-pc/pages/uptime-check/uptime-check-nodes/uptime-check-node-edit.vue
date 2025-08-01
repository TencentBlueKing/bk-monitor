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
    v-bkloading="{ isLoading: isInitLoading }"
    class="node-edit"
  >
    <div v-if="isShow">
      <div class="node-edit-item">
        <div class="item-label label-required">
          {{ $t('所属') }}
        </div>
        <div class="item-container">
          <div class="business-container">
            <verify-input :show-validate.sync="rules.bk_biz_id.validate">
              <bk-select
                v-model="node.bk_biz_id"
                :style="{ background: canSelectBusiness ? '#fafafa' : '#FFFFFF' }"
                class="business-select"
                :clearable="false"
                :disabled="canSelectBusiness"
                :list="businessList"
                :placeholder="$t('选择业务')"
                display-key="text"
                id-key="id"
                enable-virtual-scroll
                @change="handleBusinessOptClick"
                @toggle="handleBusinessToggle"
              >
                <!-- <bk-option
                  v-for="item in businessList"
                  :id="item.id"
                  :key="item.id"
                  :name="item.text"
                >
                  <div @click="handleBusinessOptClick(item.id)">
                    {{ item.text }}
                  </div>
                </bk-option> -->
              </bk-select>
            </verify-input>
            <bk-checkbox
              v-model="node.is_common"
              v-authority="{ active: !authority.MANAGE_NODE_AUTH }"
              :class="[
                'business-checkbox',
                {
                  'auth-disabled': !authority.MANAGE_NODE_AUTH,
                },
              ]"
              :disabled="!authority.MANAGE_NODE_AUTH"
              @click.native="!authority.MANAGE_NODE_AUTH && handleShowAuthorityDetail(uptimeAuth.MANAGE_NODE_AUTH)"
            >
              {{ $t('设为公共节点') }}
            </bk-checkbox>
          </div>
        </div>
      </div>
      <div class="node-edit-item">
        <div class="item-label label-required target-item">
          {{ $t('IP目标') }}
        </div>
        <div class="item-container">
          <div class="target-container">
            <verify-input
              :show-validate.sync="rules.host_list.validate"
              :validator="{ content: rules.host_list.message }"
            >
              <node-target
                v-if="node.host_list"
                :disable-host-method="disableHostMethod"
                :target="node"
                @change="handleTargetChange"
              />
            </verify-input>
          </div>
        </div>
      </div>
      <div class="node-edit-item">
        <div class="item-label">
          {{ $t('地区') }}
        </div>
        <div class="item-container">
          <div class="area-container">
            <bk-select
              v-model="node.country"
              class="area-select"
              :placeholder="$t('选择国家')"
              searchable
              @change="handleCountryChange"
            >
              <bk-option
                v-for="item in countryList"
                :id="item.cn"
                :key="item.code"
                :name="isEn ? item.en : item.cn"
              >
                <div @click="handleCountryOptClick(item)">
                  {{ isEn ? item.en : item.cn }}
                </div>
              </bk-option>
            </bk-select>
            <bk-select
              v-model="node.city"
              class="area-select"
              :placeholder="$t('选择省份')"
              searchable
            >
              <bk-option
                v-for="item in cityList"
                :id="item.cn"
                :key="item.code"
                :name="isEn ? item.en : item.cn"
              />
            </bk-select>
            <svg
              v-bk-tooltips.right="$t('从配置平台过滤地区和运营商')"
              class="hint-icon"
              viewBox="0 0 64 64"
            >
              <g>
                <circle
                  cx="32"
                  cy="32"
                  fill="#63656E"
                  r="25"
                />
              </g>
              <g>
                <path
                  d="M32,4C16.5,4,4,16.5,4,32s12.5,28,28,28s28-12.5,28-28S47.5,4,32,4z M32,56C18.7,56,8,45.3,8,32S18.7,8,32,8s24,10.7,24,24S45.3,56,32,56z"
                />
                <path
                  d="M30.9,25.2c-1.8,0.4-3.5,1.3-4.8,2.6c-1.5,1.4,0.1,2.8,1,1.7c0.6-0.8,1.5-1.4,2.5-1.8c0.7-0.1,1.1,0.1,1.2,0.6c0.1,0.9,0,1.7-0.3,2.6c-0.3,1.2-0.9,3.2-1.6,5.9c-1.4,4.8-2.1,7.8-1.9,8.8c0.2,1.1,0.8,2,1.8,2.6c1.1,0.5,2.4,0.6,3.6,0.3c1.9-0.4,3.6-1.4,5-2.8c1.6-1.6-0.2-2.7-1.1-1.8c-0.6,0.8-1.5,1.4-2.5,1.6c-0.9,0.2-1.4-0.2-1.6-1c-0.1-0.9,0.1-1.8,0.4-2.6c2.5-8.5,3.6-13.3,3.3-14.5c-0.2-0.9-0.8-1.7-1.6-2.1C33.3,24.9,32,24.9,30.9,25.2z"
                />
                <circle
                  cx="35"
                  cy="19"
                  r="3"
                />
              </g>
            </svg>
          </div>
        </div>
      </div>
      <div class="node-edit-item">
        <div class="item-label">
          {{ $t('运营商') }}
        </div>
        <div class="item-container">
          <div class="operator-container">
            <bk-radio-group
              v-model="node.carrieroperator"
              @change="handleOpearatorChange"
            >
              <bk-radio
                v-for="(item, index) in operatorList"
                :key="index"
                class="operator-radio"
                :value="item.cn"
              >
                {{ isEn ? item.en : item.cn }}
              </bk-radio>
              <bk-radio
                class="operator-radio"
                :value="$t('自定义')"
              >
                <div ref="customCarrieroperator">
                  <span v-if="node.carrieroperator !== $t('自定义')"> {{ $t('自定义') }} </span>
                  <verify-input
                    v-else
                    :show-validate.sync="rules.carrieroperator.validate"
                    :validator="{ content: rules.carrieroperator.message }"
                  >
                    <bk-input
                      ref="operatorInput"
                      v-model.trim="customCarrieroperator"
                      class="operator-input"
                      @blur="validateField(node.carrieroperator, rules.carrieroperator)"
                      @focus="handleOperatorFocus(...arguments, $event)"
                      @input="handleOperatorInput"
                    />
                  </verify-input>
                </div>
              </bk-radio>
            </bk-radio-group>
          </div>
        </div>
      </div>
      <div class="node-edit-item">
        <div class="item-label label-required">
          {{ $t('节点名称') }}
        </div>
        <div class="item-container">
          <verify-input
            class="name-container"
            :show-validate.sync="rules.name.validate"
          >
            <bk-input
              v-model.trim="node.name"
              @blur="validateField(node.name, rules.name)"
            />
          </verify-input>
        </div>
      </div>
      <div class="node-edit-item">
        <div class="item-label label-required">
          {{ $t('节点类型') }}
        </div>
        <div class="item-container">
          <verify-input
            class="name-container"
            :show-validate.sync="rules.ip_type.validate"
            :validator="{ content: rules.ip_type.message }"
          >
            <!-- eslint-disable-next-line vue/camelcase -->
            <bk-checkbox-group
              v-model="node.ip_type"
              @change="() => (rules.ip_type.validate = false)"
            >
              <bk-checkbox
                style="margin-right: 48px"
                value="IPv4"
                >IPv4</bk-checkbox
              >
              <bk-checkbox value="IPv6"> IPv6 </bk-checkbox>
            </bk-checkbox-group>
          </verify-input>
        </div>
      </div>
      <div class="node-edit-item">
        <div class="item-label" />
        <div class="item-container">
          <bk-button
            v-authority="{ active: !authority.MANAGE_AUTH }"
            class="button-submit"
            :disabled="isSubmitLoading"
            :icon="isSubmitLoading ? 'loading' : ''"
            theme="primary"
            @click="authority.MANAGE_AUTH ? handleSubmit() : handleShowAuthorityDetail(uptimeAuth.MANAGE_AUTH)"
          >
            {{ submitBtnText }}
          </bk-button>
          <bk-button @click="handleBack">
            {{ $t('取消') }}
          </bk-button>
        </div>
      </div>
    </div>
    <uptime-check-node-done
      v-else
      class="uptime-check-node-done"
      :options="options"
      @cancel="handleCancel"
      @confirm="handleBack"
    />
    <div v-show="false">
      <div
        ref="operatorPopoverContent"
        class="operator-popover-container"
      >
        <ul
          v-show="filterCustomOperatorList.length"
          class="operator-popover"
        >
          <li
            v-for="item in filterCustomOperatorList"
            :key="item"
            class="operator-popover-item"
            @click.stop="handleOperatorOptClick(item)"
          >
            <span class="item-text">{{ item }}</span>
          </li>
        </ul>
        <div
          v-show="!filterCustomOperatorList.length"
          class="no-data"
        >
          {{ $t('无匹配选项') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// import uptimeCheckNodeEditTable from './uptime-check-node-edit-table'
import { countryList, ispList } from 'monitor-api/modules/commons';
import {
  createUptimeCheckNode,
  fixNameConflictUptimeCheckNode,
  isExistUptimeCheckNode,
  retrieveUptimeCheckNode,
  updateUptimeCheckNode,
} from 'monitor-api/modules/model';
import { selectCarrierOperator, selectUptimeCheckNode } from 'monitor-api/modules/uptime_check';
import { debounce } from 'throttle-debounce';

import VerifyInput from '../../../components/verify-input/verify-input.vue';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import formLabelMixin from '../../../mixins/formLabelMixin';
import { SET_NAV_ROUTE_LIST } from '../../../store/modules/app';
import * as uptimeAuth from '../authority-map';
import NodeTarget from './node-target';
import UptimeCheckNodeDone from './uptime-check-node-done';

export default {
  name: 'UptimeCheckNodeEdit',
  components: {
    VerifyInput,
    UptimeCheckNodeDone,
    NodeTarget,
  },
  mixins: [formLabelMixin, authorityMixinCreate(uptimeAuth)],
  beforeRouteEnter(to, from, next) {
    next(vm => {
      if (from.name === 'uptime-check-task-add' || from.name === 'uptime-check-task-edit') {
        vm.isFromTask = true;
      }
    });
  },
  props: {
    id: [String, Number],
  },
  data() {
    return {
      uptimeAuth,
      isShow: true,
      isInitLoading: false,
      isSubmitLoading: false,
      node: {
        id: '',
        bk_biz_id: +this.$store.getters.bizId,
        country: '',
        city: '',
        name: '',
        carrieroperator: '',
        is_common: false,
        plat_id: '',
        ip_type: ['IPv4'],
        host_list: null,
      },
      rules: {
        bk_biz_id: {
          validate: false,
          message: this.$t('必填项'),
          rule: [{ required: true }],
        },
        host_list: {
          validate: false,
          message: this.$t('选择IP目标'),
          rule: [{ required: true, message: this.$t('选择IP目标'), validator: this.validateHostList }],
        },
        name: {
          validate: false,
          message: this.$t('必填项'),
          rule: [
            { required: true, message: this.$t('输入节点名称') },
            { required: true, message: this.$t('注意: 名字冲突'), validator: this.validateNameIsExist },
          ],
        },
        ip_type: {
          validate: false,
          message: this.$t('选择节点类型'),
          rule: [{ required: true, message: this.$t('选择节点类型'), validator: this.validateIpType }],
        },
        carrieroperator: {
          validate: false,
          message: this.$t('必填项'),
          rule: [
            // { required: true, message: this.$t('输入运营商名称'), validator: this.validateOperatorEmpty },
            { required: true, message: this.$t('注意：最大值为10个字符'), validator: this.validateOperatorLength },
            {
              required: true,
              message: `${this.$t('不允许包含如下特殊字符：')}" / \\ [ ] ' : ; | = , + * ? < > { }${this.$t('空格')}`,
              validator: this.validateOperatorFormat,
            },
          ],
        },
      },
      countryList: [],
      cityList: [],
      operatorList: [],
      businessList: this.$store.getters.bizList,
      ipList: [],
      filterIpList: [],
      customOperatorList: [],
      filterCustomOperatorList: [],
      ipPattern: /^(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])(\.(\d{1,2}|1\d\d|2[0-4]\d|25[0-5])){3}$/,
      options: {
        isLoading: false,
        status: true,
        statusTitle: this.$t('创建拨测节点成功'),
        cancelText: this.$t('返回列表'),
        confirmText: this.$t('添加拨测任务'),
      },
      operatorPopover: {
        instance: null,
      },
      handleIpInput: null,
      handleOperatorInput: null,
      customCarrieroperator: '',
      isFromTask: false,
      isEn: false,
    };
  },
  computed: {
    // 只要存在节点id，下一步时，走编辑接口。
    isEdit: {
      get() {
        return this.id !== undefined || Number.isInteger(this.node.id);
      },
      set(newValue) {
        this.isEdit = newValue;
      },
    },
    isSuperUser() {
      return this.$store.getters.isSuperUser;
    },
    // 能否选择 `所属空间`
    canSelectBusiness() {
      // 全业务时可选
      return this.node.bk_biz_id !== 0;
    },
    submitBtnText() {
      const res = this.isEdit ? this.$t('执行中...') : this.$t('创建中...');
      return this.isSubmitLoading ? res : this.$t('提交');
    },
  },
  created() {
    this.isEn = window.i18n.locale === 'enUS';
    this.node.bk_biz_id = +this.$store.getters.bizId;
    this.businessList = this.$store.getters.bizList;
    this.isInitLoading = true;
    const bizId = this.$route.params.bizId === undefined ? this.$store.getters.bizId : this.$route.params.bizId;
    if (this.isEdit) {
      this.updateNavData(this.$t('编辑'));
      Promise.all([
        this.getAreaList(),
        this.getNodeDetail(this.id, bizId),
        this.getOperatorList(),
        this.getHostRegionIspList(bizId),
      ])
        .then(res => {
          if (res[1]) {
            this.handleNodeInfo(res[1]);
          }
        })
        .finally(() => {
          this.updateNavData(`${this.$t('编辑')} ${this.node.ip || ''}`);
          this.isInitLoading = false;
        });
    } else {
      this.updateNavData(this.$t('新建拨测节点'));
      Promise.all([this.getAreaList(), this.getOperatorList(), this.getHostRegionIspList(bizId)]).finally(() => {
        this.isInitLoading = false;
      });
      this.node.host_list = [];
    }
    this.handleOperatorInput = debounce(300, v => {
      this.filterCustomOperatorList = this.customOperatorList.filter(item => item.indexOf(v) > -1);
    });
  },
  mounted() {
    this.initFormLabelWidth({ safePadding: 12 });
  },
  beforeDestroy() {
    this.operatorPopover.instance?.destroy();
  },
  methods: {
    handleTargetChange(v) {
      this.node.host_list = v?.host_list || [];
      this.rules.host_list.validate = !this.node.host_list.length;
      this.handleIpOptClick(v?.host_list[0]);
    },
    disableHostMethod(host) {
      return this.ipList.some(
        item =>
          item.is_built &&
          ((item.bk_host_id && item.bk_host_id.toString() === host.host_id.toString()) ||
            (item.ip && item.plat_id === host.cloud_id && item.ip === host.ip))
      );
    },
    validateHostList(hostList) {
      return hostList.length === 1;
    },
    validateIpType(val) {
      return val.length > 0;
    },
    updateNavData(name = '') {
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, [{ name, id: '' }]);
    },
    async validateField(value, ruleMap) {
      const { rule } = ruleMap;
      for (const item of rule) {
        if (item.required && !value && !item.validator) {
          // 空值
          ruleMap.validate = true;
          ruleMap.message = item.message;
          return true;
        }
        if (item.required && item.validator && typeof item.validator === 'function') {
          // 非空有校验器
          const res = item.validator(value);
          if (this.isPromise(res)) {
            ruleMap.validate = await res;
          } else {
            ruleMap.validate = !res;
          }
          if (ruleMap.validate) {
            ruleMap.message = item.message;
            return true;
          }
        }
      }
      ruleMap.validate = false;
      return false;
    },
    async validate() {
      const { node } = this;
      const { rules } = this;
      let keys = Object.keys(this.rules);
      if (this.node.carrieroperator !== this.$t('自定义')) {
        keys = keys.filter(item => item !== 'carrieroperator');
      }
      for (const item of keys) {
        if (!rules[item].validate) {
          await this.validateField(node[item], rules[item]);
        }
      }
      return keys.every(item => rules[item].validate === false);
    },
    validateOperatorEmpty(val) {
      if (val === this.$t('自定义')) {
        return this.customCarrieroperator !== '';
      }
      return true;
    },
    validateOperatorLength(val) {
      if (val === this.$t('自定义')) {
        return !this.validateStrLength(this.customCarrieroperator);
      }
      return true;
    },
    validateOperatorFormat(val) {
      if (val === this.$t('自定义')) {
        return !/["/[\]':;|=,+*?<>{}.\\]+/g.test(this.customCarrieroperator);
      }
      return true;
    },
    validateStrLength(str, length = 10) {
      const cnLength = (str.match(/[\u4e00-\u9fa5]/g) || []).length;
      const enLength = (str || '').length - cnLength;
      return cnLength * 2 + enLength > length;
    },
    handleCountryChange(newVal) {
      if (!newVal) {
        this.cityList = [];
        this.node.city = '';
      }
    },
    handleCountryOptClick(option) {
      this.cityList = option.children;
      this.node.city = '';
    },
    setCity(code) {
      const country = this.countryList.find(item => item.cn === code) || {};
      if (country.children?.length) {
        this.cityList = country.children;
      }
    },
    async handleSubmit() {
      if (await this.validate()) {
        const { node, isEdit } = this;
        const params = this.getParams(node);
        if (isEdit) {
          await this.update(node.id, params);
        } else {
          await this.create(params);
        }
        this.isSubmitLoading = false;
        if (this.isFromTask) {
          this.$router.push({ name: 'uptime-check-task-add', params: { taskId: node.id } });
        } else {
          this.isShow = false;
          this.handleSubmitRes(true, isEdit ? this.$t('编辑拨测节点成功') : this.$t('创建拨测节点成功'));
        }
      }
    },
    getParams(node) {
      let ipType = 4;
      if (node.ip_type.length > 1) {
        ipType = 0;
      } else if (node.ip_type[0] === 'IPv6') {
        ipType = 6;
      }
      return {
        location: {
          country: node.country,
          city: node.city,
        },
        bk_biz_id: node.bk_biz_id,
        carrieroperator:
          node.carrieroperator === this.$t('自定义') ? this.customCarrieroperator : node.carrieroperator || '',
        bk_host_id: node.host_list[0]?.host_id,
        is_common: node.is_common,
        name: node.name,
        plat_id: node.plat_id,
        ip: node.ip || node.ipv6,
        ip_type: ipType,
      };
    },
    create(params) {
      this.isSubmitLoading = true;
      return createUptimeCheckNode(params)
        .then(data => {
          this.node.id = data.id;
        })
        .finally(() => {
          this.isSubmitLoading = false;
        });
    },
    update(id, params) {
      this.isSubmitLoading = true;
      return updateUptimeCheckNode(id, params).finally(() => {
        this.isSubmitLoading = false;
      });
    },
    handleBack() {
      if (location.hash === '#create') {
        location.hash = '';
      }
      if (this.isFromTask) {
        this.$router.back();
      } else {
        this.$router.push({
          name: 'uptime-check',
          query: {
            dashboardId: 'uptime-check-node',
          },
        });
      }
    },
    handleCancel() {
      this.handleBack();
    },
    getAreaList() {
      return countryList().then(data => {
        this.countryList = data;
      });
    },
    getOperatorList() {
      return ispList().then(data => {
        this.operatorList = data;
      });
    },
    getHostRegionIspList(id) {
      return selectUptimeCheckNode({ bk_biz_id: id }).then(data => {
        this.ipList = data;
      });
    },

    handleNodeInfo(info) {
      const { node } = this;
      Object.keys(node).forEach(key => {
        if (key === 'ip_type') {
          let ipType = ['IPv4'];
          if (info[key] === 0) {
            ipType = ['IPv4', 'IPv6'];
          } else if (info[key] === 6) {
            ipType = ['IPv6'];
          }
          node[key] = ipType;
        } else {
          node[key] = info[key];
        }
      });
      const { location } = info;
      node.country = location.country;
      node.city = location.city;
      node.host_list = [{ host_id: info.bk_host_id }];
      this.setCity(location.country);
      if (node.carrieroperator && ![this.$t('移动'), this.$t('电信'), this.$t('联通')].includes(node.carrieroperator)) {
        this.customCarrieroperator = node.carrieroperator;
        node.carrieroperator = this.$t('自定义');
      }
    },
    handleSubmitRes(result, title) {
      const { options } = this;
      options.isLoading = false;
      options.status = result;
      options.statusTitle = title;
    },
    handleBusinessToggle(toggle) {
      !toggle && this.validateField(this.node.bk_biz_id, this.rules.bk_biz_id);
    },
    getNodeDetail(id, businessId) {
      return retrieveUptimeCheckNode(id, { bk_biz_id: businessId });
    },
    handleBusinessOptClick(val) {
      const { node } = this;
      if (val && val !== node.bk_biz_id) {
        if (!this.validateField(node.bk_biz_id, this.rules.bk_biz_id)) {
          this.getHostRegionIspList(node.bk_biz_id);
        }
        node.country = '';
        node.city = '';
        node.name = '';
        node.host_list = [];
      }
    },
    handleIpOptClick(host) {
      if (!host) return;
      const { node } = this;
      node.plat_id = host.cloud_id;
      host.country && (node.country = host.country);
      host.city && (node.city = host.city);
      if (host.carrieroperator) {
        if (
          host.carrieroperator &&
          ![this.$t('移动'), this.$t('电信'), this.$t('联通')].includes(host.carrieroperator)
        ) {
          this.customCarrieroperator = host.carrieroperator;
          node.carrieroperator = this.$t('自定义');
        } else {
          node.carrieroperator = host.carrieroperator;
        }
      }
      this.setCity(node.country);
    },
    handleIpToggle(toggle) {
      !toggle && this.validateField(this.node.ip, this.rules.ip);
    },
    getIPIsExist(businessId, ip) {
      return isExistUptimeCheckNode({ bk_biz_id: businessId, ip });
    },
    isPromise(value) {
      return value && Object.prototype.toString.call(value) === '[object Promise]';
    },
    async validateNameIsExist() {
      const { node } = this;
      return fixNameConflictUptimeCheckNode({
        bk_biz_id: node.bk_biz_id,
        id: node.id,
        name: node.name,
      }).then(data => {
        node.name = data.name;
      });
    },
    handleOpearatorChange(v) {
      if (v === this.$t('自定义')) {
        this.$nextTick(() => {
          this.$refs.customCarrieroperator.focus();
        });
      }
    },
    async handleOperatorFocus(v, e) {
      // this.$nextTick(() => {
      //   this.$refs.operatorInput.focus();
      // });
      if (!this.customOperatorList.length) {
        await this.getCustomOperatorList();
      }
      this.handleOperatorPopoverShow(e);
    },
    handleOperatorPopoverShow(e) {
      const { operatorPopover } = this;
      const { operatorPopoverContent, customCarrieroperator } = this.$refs;
      const { target } = e;
      operatorPopover.width = target.width;
      if (!operatorPopover.instance) {
        operatorPopover.instance = this.$bkPopover(target, {
          content: operatorPopoverContent,
          arrow: false,
          trigger: 'click',
          placement: 'bottom',
          maxWidth: 120,
          theme: 'light edit-operator-node',
          duration: [275, 0],
          appendTo: () => customCarrieroperator,
        });
        // .instances[0]
      } else {
        operatorPopover.instance.reference = customCarrieroperator;
        operatorPopover.instance.content = operatorPopoverContent;
      }
      this.operatorPopover.instance?.show(100);
    },
    handleOperatorOptClick(opreator) {
      this.customCarrieroperator = opreator;
    },
    getCustomOperatorList() {
      return selectCarrierOperator().then(data => {
        this.filterCustomOperatorList = data.filter(item => !!item);
        this.customOperatorList = data.filter(item => !!item);
      });
    },
  },
};
</script>

<style lang="scss" scoped>
@mixin fix-bk-checkbox {
  &:after {
    top: 2px;
    left: 5px;
  }
}

.node-edit {
  height: 100%;
  padding-top: 20px;
  margin: 20px 24px;
  background-color: white;

  .node-edit-item {
    display: flex;
    align-items: center;
    margin-bottom: 20px;

    .item-label {
      min-width: 74px;
      height: 32px;
      margin-right: 20px;
      font-size: 14px;
      line-height: 32px;
      color: #63656e;
      text-align: right;

      &.label-required:after {
        position: relative;
        margin: 2px -7px 0 2px;
        font-size: 12px;
        color: red;
        content: '*';
      }

      &.target-item {
        align-self: flex-start;
      }
    }

    .item-container {
      line-height: 1;

      :deep(.bk-form-radio) {
        .icon-check:before {
          content: '';
        }
      }

      .name-container {
        width: 490px;

        :deep(.tooltips-icon) {
          top: 8px;
          right: 10px;
        }
      }

      .operator-radio {
        margin-right: 48px;
        margin-bottom: 0;

        .operator-input {
          :deep(.bk-form-input) {
            width: 120px;
            background-color: #fafbfd;
            border-top: 0;
            border-right: 0;
            border-left: 0;

            &:focus {
              /* stylelint-disable-next-line declaration-no-important */
              background-color: #fafbfd !important;

              /* stylelint-disable-next-line declaration-no-important */
              border-color: #c4c6cc !important;
            }
          }
        }
      }

      .target-container {
        width: 720px;

        :deep(.add-btn) {
          display: flex;
          align-items: center;

          /* stylelint-disable-next-line declaration-no-important */
          height: 32px !important;
        }
      }

      .business-container {
        display: flex;
        align-items: center;

        .business-select {
          width: 320px;
          // background: #FFFFFF;
        }

        .business-checkbox {
          margin-bottom: 0;
          margin-left: 16px;

          &.auth-disabled {
            cursor: pointer;
          }
        }

        .is-empty {
          .business-select {
            border-color: #f00;
          }

          :deep(.tooltips-icon) {
            top: 8px;
            right: 30px;
          }
        }
      }

      .area-container {
        display: inline-flex;
        align-items: center;
        width: 514px;

        .area-select {
          width: 240px;
          margin-right: 10px;
          background-color: #fff;
        }

        .hint-icon {
          width: 21px;
          height: 21px;
          cursor: pointer;
          fill: #fff;
        }
      }

      .operator-container {
        display: flex;
        align-items: center;
        height: 32px;
        line-height: 32px;
      }

      .default-container {
        .default-checkbox {
          :deep(.bk-checkbox) {
            @include fix-bk-checkbox();
          }
        }
      }

      .button-submit {
        margin-right: 10px;

        :deep(.icon-loading:before) {
          content: '';
        }
      }
    }
  }

  .uptime-check-node-done {
    margin-top: 31px;
  }

  :deep(.tippy-tooltip) {
    padding: 0;

    .ip-popover-container,
    .operator-popover-container {
      max-height: 204px;
      overflow-y: auto;

      .ip-popover,
      .operator-popover {
        padding: 0;
        margin: 0;

        .ip-popover-item,
        .operator-popover-item {
          display: list-item;
          width: 100%;
          height: 32px;
          padding-left: 15px;
          line-height: 32px;
          cursor: pointer;

          .item-text {
            display: inline-block;
            height: 16px;
            font-size: 12px;
            line-height: 16px;
            color: #63656e;
          }

          &:hover {
            background: #e1ecff;

            .item-text {
              color: #3a84ff;
            }
          }

          .item-status {
            display: inline-block;
            height: 16px;
            margin-left: 5px;
            font-size: 12px;
            line-height: 16px;
            color: #c4c6cc;
          }
        }
      }

      .no-data {
        height: 32px;
        padding-left: 15px;
        font-size: 12px;
        line-height: 32px;
        color: #63656e;
      }
    }

    .operator-popover-container {
      width: 120px;
    }
  }
}
</style>
