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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { checkDuplicateName, getDataEncoding } from '../../../../monitor-api/modules/apm_meta';
import { Debounce, deepClone } from '../../../../monitor-common/utils/utils';
import { IIpV6Value, INodeType } from '../../../../monitor-pc/components/monitor-ip-selector/typing';
import { transformValueToMonitor } from '../../../../monitor-pc/components/monitor-ip-selector/utils';
import StrategyIpv6 from '../../../../monitor-pc/pages/strategy-config/strategy-ipv6/strategy-ipv6';
import { ICreateAppFormData } from '../../home/app-list';

import { IDescData, ThemeType } from './select-card-item';

import './select-system.scss';

export interface IListDataItem {
  title: string;
  list?: ICardItem[];
  children?: IListDataItem[];
  multiple?: boolean;
  other?: {
    title: string;
    checked: boolean;
    value: string;
  };
}
export interface ICardItem {
  id: string;
  title: string;
  theme: ThemeType;
  img: string;
  descData?: IDescData;
  hidden: boolean;
  checked: boolean;
}
interface IProps {
  loading: boolean;
  listData: IListDataItem[];
}
interface IEvents {
  onNextStep: void;
  onChange: ICreateAppFormData;
}
@Component
export default class SelectSystem extends tsc<IProps, IEvents> {
  @Prop({ type: Boolean }) loading: false;
  @Prop({ type: Array, default: () => [] }) listData: IListDataItem[];

  @Ref() addForm: any;

  isEmpy = false;
  localListData: IListDataItem[] = [];
  canNextStep = false;
  formData: ICreateAppFormData = {
    pluginId: 'opentelemetry',
    name: '',
    enName: '',
    desc: '',
    enableProfiling: false,
    enableTracing: true,
    plugin_config: {
      target_node_type: 'INSTANCE',
      target_object_type: 'HOST',
      target_nodes: [],
      data_encoding: '',
      paths: ['']
    }
  };
  rules = {
    name: [
      {
        required: true,
        validator: val => val.length >= 1 && val.length <= 50,
        message: window.i18n.tc('输入1-50个字符'),
        trigger: 'blur'
      },
      {
        validator: val => /^[a-z0-9_-]+$/.test(val),
        message: window.i18n.t('仅支持小写字母、数字、_- 中任意一条件即可'),
        trigger: 'change'
      }
    ],
    enName: [
      {
        validator: val => val.length >= 1 && val.length <= 50,
        message: window.i18n.t('输入1-50个字符'),
        trigger: 'blur'
      }
    ],
    'plugin_config.target_nodes': [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'change'
      }
    ],
    'plugin_config.paths': [
      {
        required: true,
        validator: (val: []) => val.every(item => !!item),
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ],
    'plugin_config.data_encoding': [
      {
        required: true,
        message: window.i18n.tc('必填项'),
        trigger: 'blur'
      }
    ]
  };
  /** 英文名是否重名 */
  existedName = false;
  /** 点击提交触发 */
  clickSubmit = false;
  /** TODO: 这里先写死，看看后续会不会有接口 */
  pluginList = [
    {
      id: 'opentelemetry',
      name: 'OpenTelemetry',
      img: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9Ii0xMi43IC0xMi43IDEwMjQuNCAxMDI0LjQiPjxwYXRoIGZpbGw9IiNmNWE4MDAiIGQ9Ik01MjguNyA1NDUuOWMtNDIgNDItNDIgMTEwLjEgMCAxNTIuMXMxMTAuMSA0MiAxNTIuMSAwIDQyLTExMC4xIDAtMTUyLjEtMTEwLjEtNDItMTUyLjEgMHptMTEzLjcgMTEzLjhjLTIwLjggMjAuOC01NC41IDIwLjgtNzUuMyAwLTIwLjgtMjAuOC0yMC44LTU0LjUgMC03NS4zIDIwLjgtMjAuOCA1NC41LTIwLjggNzUuMyAwIDIwLjggMjAuNyAyMC44IDU0LjUgMCA3NS4zem0zNi42LTY0M2wtNjUuOSA2NS45Yy0xMi45IDEyLjktMTIuOSAzNC4xIDAgNDdsMjU3LjMgMjU3LjNjMTIuOSAxMi45IDM0LjEgMTIuOSA0NyAwbDY1LjktNjUuOWMxMi45LTEyLjkgMTIuOS0zNC4xIDAtNDdMNzI1LjkgMTYuN2MtMTIuOS0xMi45LTM0LTEyLjktNDYuOSAwek0yMTcuMyA4NTguOGMxMS43LTExLjcgMTEuNy0zMC44IDAtNDIuNWwtMzMuNS0zMy41Yy0xMS43LTExLjctMzAuOC0xMS43LTQyLjUgMEw3Mi4xIDg1MmwtLjEuMS0xOS0xOWMtMTAuNS0xMC41LTI3LjYtMTAuNS0zOCAwLTEwLjUgMTAuNS0xMC41IDI3LjYgMCAzOGwxMTQgMTE0YzEwLjUgMTAuNSAyNy42IDEwLjUgMzggMHMxMC41LTI3LjYgMC0zOGwtMTktMTkgLjEtLjEgNjkuMi02OS4yeiIvPjxwYXRoIGZpbGw9IiM0MjVjYzciIGQ9Ik01NjUuOSAyMDUuOUw0MTkuNSAzNTIuM2MtMTMgMTMtMTMgMzQuNCAwIDQ3LjRsOTAuNCA5MC40YzYzLjktNDYgMTUzLjUtNDAuMyAyMTEgMTcuMmw3My4yLTczLjJjMTMtMTMgMTMtMzQuNCAwLTQ3LjRMNjEzLjMgMjA1LjljLTEzLTEzLjEtMzQuNC0xMy4xLTQ3LjQgMHptLTk0IDMyMi4zbC01My40LTUzLjRjLTEyLjUtMTIuNS0zMy0xMi41LTQ1LjUgMEwxODQuNyA2NjMuMmMtMTIuNSAxMi41LTEyLjUgMzMgMCA0NS41bDEwNi43IDEwNi43YzEyLjUgMTIuNSAzMyAxMi41IDQ1LjUgMEw0NTggNjk0LjFjLTI1LjYtNTIuOS0yMS0xMTYuOCAxMy45LTE2NS45eiIvPjwvc3ZnPg=='
    },
    {
      id: 'log_trace',
      name: 'Logs to Traces',
      img: 'data:image/png;base64,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'
    }
  ];

  selectorDialog: { isShow: boolean } = {
    isShow: false
  };

  selectedTargetTips = {
    INSTANCE: '已选择{0}个静态主机',
    TOPO: '已动态选择{0}个节点',
    SERVICE_TEMPLATE: '已选择{0}个服务模板',
    SET_TEMPLATE: '已选择{0}个集群模板'
  };

  // 日志字符集
  logAsciiList = [];
  isFetchingEncodingList = false;

  get isShowLog2TracesFormItem() {
    return this.formData.pluginId === 'log_trace';
  }

  created() {
    this.initData();
  }

  mounted() {
    this.canNextStep = this.validate();
    this.listenPluginChange();
  }

  @Watch('listData', { deep: true, immediate: true })
  listDataUpdate(list: IListDataItem[]) {
    this.localListData = deepClone(list);
  }

  /** 初始化页面数据 */
  initData() {
    this.rules.name.push({
      message: window.i18n.tc('注意: 名字冲突'),
      trigger: 'none',
      validator: val => !this.existedName && !!val
    });
  }

  /** 批量修改整行卡片的选中状态 */
  handleRowChecked(row: IListDataItem, bool = false) {
    // eslint-disable-next-line no-param-reassign
    row.list.forEach(item => (item.checked = bool));
    if (!!row.other) {
      // eslint-disable-next-line no-param-reassign
      row.other.checked = bool;
      // eslint-disable-next-line no-param-reassign
      row.other.value = '';
    }
  }

  /** 点击卡片操作 单选 */
  // handleCheckedCardItem(cardItem: ICardItem, row: IListDataItem, val: boolean) {
  //   !row.multiple && this.handleRowChecked(row);
  //   cardItem.checked = val;
  //   this.canNextStep = this.validate();
  // }

  /** 选中其他选项 */
  handleOtherChecked(row: IListDataItem, val: boolean) {
    !row.multiple && this.handleRowChecked(row);
    // eslint-disable-next-line no-param-reassign
    row.other.checked = val;
  }

  /** 处理SelectCardItem的现隐 */
  @Debounce(200)
  handleSearch(keyword: string) {
    let isEmpy = true;
    const fn = (list: IListDataItem[]) => {
      list.forEach(row => {
        if (!!row.children?.length) {
          fn(row.children);
        } else {
          row.list?.forEach?.(cardItem => {
            const isMatch = cardItem.title.toLocaleLowerCase().includes(keyword.toLocaleLowerCase());
            // eslint-disable-next-line no-param-reassign
            cardItem.hidden = !isMatch;
            if (isMatch) isEmpy = false;
          });
        }
      });
    };
    fn(this.localListData);
    this.isEmpy = isEmpy;
  }

  /** 是否展示该行卡片 */
  handleShowRow(row: IListDataItem) {
    return (
      row.list?.some?.(item => !item.hidden) || row.children?.some?.(child => child.list?.some?.(item => !item.hidden))
    );
  }

  /** 校验数据 */
  validate(checkedList?: IListDataItem[]): boolean {
    const localCheckList = checkedList || this.getCheckedList();
    return localCheckList.every(
      row =>
        !!row.list?.length ||
        (row.other?.checked && !!row.other?.value) ||
        row.children?.some?.(child => !!child.list.length)
    );
  }

  /** 下一步操作 */
  async handleNextStep() {
    // const checkedList: IListDataItem[] = this.getCheckedList();
    // const isPass = this.validate(checkedList);
    // if (isPass) this.handleNext();

    /** 校验重名 */
    this.clickSubmit = true;
    const noExistedName = await this.handleCheckDuplicateName(true);
    if (noExistedName) {
      const isPass = await this.addForm.validate();
      if (isPass) {
        // this.$router.replace({
        //   name: this.$route.name,
        //   params: {
        //     appInfo: JSON.stringify({ ...this.formData, ...{ pluginId: '' } })
        //   }
        // });
        this.handleNext();
      }
    }
  }

  @Emit('nextStep')
  @Emit('change')
  handleNext() {
    return deepClone(this.formData);
  }

  /** 筛选被选中的数据 */
  getCheckedList(): IListDataItem[] {
    const fn = (list: IListDataItem[]) =>
      list.map(row => {
        if (row.children) {
          return {
            ...row,
            children: fn(row.children)
          };
        }
        // eslint-disable-next-line no-param-reassign
        row.list = row.list.filter(item => item.checked);

        return row;
      });
    return fn(deepClone(this.localListData));
  }
  handleCancel() {
    this.$router.back();
  }
  /** 检查 应用名 是否重名 */
  handleCheckDuplicateName(isSubmit = false) {
    return new Promise((resolve, reject) => {
      if (!this.formData.name) return resolve(true);
      if (this.formData.name.length < 1) return reject(false);
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      setTimeout(async () => {
        if (this.clickSubmit && !isSubmit) {
          resolve(true);
        } else {
          this.clickSubmit = false;
          const { exists } = await checkDuplicateName({ app_name: this.formData.name });
          this.existedName = exists;
          if (exists) {
            this.addForm.validateField('name');
            reject(false);
          } else {
            resolve(true);
          }
        }
      }, 100);
    });
  }

  handleSelectorChange(data: { value: IIpV6Value; nodeType: INodeType }) {
    // TODO: 将数据拍平，不知道最后是否用得着
    const value = transformValueToMonitor(data.value, data.nodeType);
    this.formData.plugin_config.target_nodes = value.map(item => ({
      bk_host_id: item.bk_host_id
    }));
    // 这里利用 nodeType 控制显示哪种类型的提示文本。
    this.formData.plugin_config.target_node_type = data.nodeType;
  }

  /**
   * 监听插件选中值的变化。
   */
  listenPluginChange() {
    // 第一次选择 Logs to Traces 的插件时，需要加载 日志字符集 列表。
    this.$once('selectLogTrace', async () => {
      this.isFetchingEncodingList = true;
      const encodingList = await getDataEncoding()
        .catch(console.log)
        .finally(() => (this.isFetchingEncodingList = false));
      if (Array.isArray(encodingList)) this.logAsciiList = encodingList;
    });
  }

  render() {
    /** 一行卡片 */
    // 20230919 暂不需要
    // const cardList = (list: ICardItem[], row: IListDataItem) =>
    //   list.map(
    //     cardItem =>
    //       !cardItem.hidden && (
    //         <SelectCardItem
    //           class='app-add-card-item'
    //           mode='small'
    //           title={cardItem.title}
    //           // theme={cardItem.theme}
    //           theme={'intro'}
    //           img={cardItem.img}
    //           multiple={row.multiple}
    //           checked={cardItem.checked}
    //           descData={cardItem.descData}
    //           // onClick={() => this.handleCheckedCardItem(cardItem, row, !cardItem.checked)}
    //         />
    //       )
    //   );
    return (
      <div
        class='select-system-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='app-add-desc'>
          <div class='app-add-question'>{this.$t('什么是应用？')}</div>
          <div class='app-add-answer'>
            {this.$t('应用一般是拥有独立的站点，由多个Service共同组成，提供完整的产品功能，拥有独立的软件架构。 ')}
          </div>
          <div class='app-add-answer'>
            {this.$t(
              '从技术方面来说应用是Trace数据的存储隔离，在同一个应用内的数据将进行统计和观测。更多请查看产品文档。'
            )}
          </div>
        </div>

        {/* <bk-input
          class="card-item-search"
          onChange={this.handleSearch}
          placeholder={this.$t('输入搜索或筛选')}
          right-icon="bk-icon icon-search"></bk-input> */}
        {/* 20230919 暂时不要 */}
        {/* {!this.isEmpy ? (
          [
            <div>
              {this.localListData.map(
                item =>
                  this.handleShowRow(item) && (
                    <div class='app-add-row'>
                      <div class='app-add-row-title'>{item.title}</div>
                      <div class='app-add-row-content'>
                        <div>
                          {!!item.list?.length && <div class='row-content-list'>{cardList(item.list, item)}</div>}
                          {!!item.children?.length &&
                            item.children.map(child =>
                              child.list.length ? (
                                <div class='app-add-row-child'>
                                  <div class='child-title'>{child.title}</div>
                                  <div class='child-row-content'>
                                    <div class='row-content-list'>
                                      {!!child.list?.length && cardList(child.list, child)}
                                    </div>
                                  </div>
                                </div>
                              ) : undefined
                            )}
                        </div>
                        {!!item.other && (
                          <div class='app-add-row-other'>
                            <bk-checkbox
                              v-model={item.other.checked}
                              onChange={val => this.handleOtherChecked(item, val)}
                            >
                              {item.other.title}
                            </bk-checkbox>
                            <bk-input
                              class='other-input simplicity-input'
                              v-model={item.other.value}
                              behavior='simplicity'
                            ></bk-input>
                          </div>
                        )}
                      </div>
                    </div>
                  )
              )}
            </div>
            // <div class="select-btn-row">
            // eslint-disable-next-line max-len
            //   <bk-button class="btn" theme="primary" onClick={this.handleNextStep} disabled={!this.canNextStep}>{this.$t('下一步')}</bk-button>
            //   <bk-button class="btn" onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
            // </div>
          ]
        ) : (
          <bk-exception
            class='empty-page'
            type='search-empty'
          ></bk-exception>
        )} */}

        <bk-form
          class='app-add-form'
          {...{
            props: {
              model: this.formData,
              rules: this.rules
            }
          }}
          label-width={104}
          ref='addForm'
        >
          <bk-form-item
            label={this.$t('应用名')}
            required
            property='name'
            error-display-type='normal'
          >
            <bk-input
              v-model={this.formData.name}
              maxlength={50}
              placeholder={this.$t('输入1-50个字符，且仅支持小写字母、数字、_- 中任意一条件即可')}
              onBlur={() => this.handleCheckDuplicateName()}
            />
          </bk-form-item>
          <bk-form-item
            label={this.$t('应用别名')}
            required
            property='enName'
            error-display-type='normal'
          >
            <bk-input
              v-model={this.formData.enName}
              maxlength={50}
              placeholder={this.$t('输入1-50个字符')}
            />
          </bk-form-item>
          <bk-form-item label={this.$t('描述')}>
            <bk-input
              type='textarea'
              v-model={this.formData.desc}
            ></bk-input>
          </bk-form-item>
          <bk-form-item
            label='Profiling'
            required
          >
            <bk-switcher
              theme='primary'
              v-model={this.formData.enableProfiling}
            ></bk-switcher>
            <span class='form-item-tips'>
              <i class='icon-monitor icon-tishi'></i>
              <i18n
                path='如何开启持续 Profiling ，请查看 {0}'
                class='flex-center'
              >
                <span class='link-text'>
                  {this.$t('使用文档')}
                  <i class='icon-monitor icon-fenxiang'></i>
                </span>
              </i18n>
            </span>
          </bk-form-item>
          <bk-form-item
            label='Tracing'
            required
          >
            <bk-switcher
              theme='primary'
              disabled
              v-model={this.formData.enableTracing}
            ></bk-switcher>
          </bk-form-item>
          <bk-form-item label={this.$t('支持插件')}>
            {this.pluginList.map(item => (
              <div
                class={{
                  'app-add-plugin-radio': true,
                  selected: item.id === this.formData.pluginId
                }}
                onClick={() => {
                  this.formData.pluginId = item.id;
                  if (item.id === 'log_trace') {
                    this.$emit('selectLogTrace');
                  }
                }}
              >
                <div class='plugin-info'>
                  <img src={item.img} />
                  <div class='plugin-name'>
                    <span>{item.name}</span>
                    <span class='desc'>
                      说明文案
                      <span class='link-text'>{this.$t('接入指引')}</span>
                    </span>
                  </div>
                </div>
                <bk-checkbox value={item.id === this.formData.pluginId} />
              </div>
            ))}
          </bk-form-item>
          {this.isShowLog2TracesFormItem && (
            <div class='log2Trace-container'>
              <bk-form-item
                label={this.$t('采集目标')}
                required
                property='plugin_config.target_nodes'
                error-display-type='normal'
              >
                <div style='display: flex;align-items: center;'>
                  <bk-button
                    theme='default'
                    icon='plus'
                    class='btn-target-collect'
                    onClick={() => (this.selectorDialog.isShow = true)}
                  >
                    {this.$t('选择目标')}
                  </bk-button>
                  {this.formData.plugin_config.target_nodes.length > 0 && (
                    <i18n
                      path={this.selectedTargetTips[this.formData.plugin_config.target_node_type]}
                      style='margin-left: 8px;'
                    >
                      <span style='color: #4e99ff;'>{this.formData.plugin_config.target_nodes.length}</span>
                    </i18n>
                  )}
                </div>
              </bk-form-item>
              <bk-form-item
                label={this.$t('日志路径')}
                required
                property='plugin_config.paths'
                error-display-type='normal'
              >
                {this.formData.plugin_config.paths.map((path, index) => (
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        marginBottom: index > 0 && index < this.formData.plugin_config.paths.length - 1 && '20px'
                      }}
                    >
                      <bk-input
                        v-model={this.formData.plugin_config.paths[index]}
                        placeholder={this.$t('请输入')}
                      />
                      <bk-icon
                        class='log-path-icon log-path-icon-plus'
                        type='plus-circle-shape'
                        onClick={() => this.formData.plugin_config.paths.push('')}
                      />
                      <bk-icon
                        class={{
                          'log-path-icon': true,
                          'log-path-icon-minus': true,
                          disabled: this.formData.plugin_config.paths.length <= 1
                        }}
                        type='minus-circle-shape'
                        onClick={() =>
                          this.formData.plugin_config.paths.length > 1 &&
                          this.formData.plugin_config.paths.splice(index, 1)
                        }
                      />
                    </div>
                    {index === 0 && <div class='log-path-hint'>{this.$t('日志文件为绝对路径，可使用通配符')}</div>}
                  </div>
                ))}
              </bk-form-item>
              <bk-form-item
                label={this.$t('日志字符集')}
                required
                property='plugin_config.data_encoding'
                error-display-type='normal'
              >
                <bk-select
                  v-model={this.formData.plugin_config.data_encoding}
                  disabled={this.isFetchingEncodingList}
                >
                  {this.logAsciiList.map(item => (
                    <bk-option
                      key={item.id}
                      id={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>
              </bk-form-item>
            </div>
          )}
          <bk-form-item>
            <bk-button
              class='btn mr10'
              theme='primary'
              onClick={this.handleNextStep}
              // disabled={!this.canNextStep}
            >
              {this.$t('下一步')}
            </bk-button>
            <bk-button
              class='btn'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </bk-form-item>
        </bk-form>

        <StrategyIpv6
          showDialog={this.selectorDialog.isShow}
          nodeType={this.formData.plugin_config.target_node_type}
          objectType={this.formData.plugin_config.target_object_type}
          checkedNodes={this.formData.plugin_config.target_nodes}
          onChange={this.handleSelectorChange}
          onCloseDialog={v => (this.selectorDialog.isShow = v)}
        ></StrategyIpv6>
      </div>
    );
  }
}
