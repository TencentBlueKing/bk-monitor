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

import { Component, Mixins, Prop } from 'vue-property-decorator';
import * as tsx from 'vue-tsx-support';

import { destroyActionConfig, listActionConfig, partialUpdateActionConfig } from 'monitor-api/modules/model';
import { commonPageSizeGet, commonPageSizeSet } from 'monitor-common/utils';
import { isZh } from 'monitor-pc/common/constant';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import DeleteSubtitle from 'monitor-pc/pages/strategy-config/strategy-config-common/delete-subtitle';
import authorityMixinCreate from 'monitor-ui/mixins/authorityMixin';

import debounce from '../../../common/debounce-decorator';
import TableSkeleton from '../../../components/skeleton/table-skeleton';
import setMealAddModule from '../../../store/modules/set-meal-add';
import OperateOptions from '../components/operate-options';
import SetMealDetail, { type ISetMealDetail } from '../set-meal-detail/set-meal-detail';
import * as ruleAuth from './authority-map';

import type { EmptyStatusOperationType, EmptyStatusType } from 'monitor-pc/components/empty-status/types';

import './set-meal.scss';

interface IContainerProps {
  name: string;
  id?: string;
}
interface IRowData {
  id: number;
  plugin_id: string;
  name: string;
  update_user: string;
  update_time: string;
  is_enabled: boolean;
  plugin_name: string;
  stragies_count: number;
  executions_count: number;
}
Component.registerHooks(['beforeRouteLeave']);
@Component({
  name: 'set-meal',
})
class Container extends Mixins(authorityMixinCreate(ruleAuth)) {
  @Prop() public name!: string;
  @Prop({ default: '', type: String }) public id: string;

  private data: IRowData[] = [];
  private detailData: ISetMealDetail = {
    id: 0,
    isShow: false,
    width: 610,
  };
  private pagination = {
    current: 1,
    count: 1,
    limit: 10,
    // 'limit-list': [1, 2, 5, 10]
  };
  private loading = false;
  private keyword = '';

  private emptyType: EmptyStatusType = 'empty';

  /** 搜索的时候前端过滤出来的数据 */
  get filterData() {
    return this.data.filter(
      item =>
        String(item.name).toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()) ||
        String(item.plugin_name).toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase()) ||
        String(item.update_user).toLocaleLowerCase().includes(this.keyword.toLocaleLowerCase())
    );
  }
  /** 表格中每一页需要展示的数据 */
  get tableData() {
    return this.filterData.slice(
      this.pagination.limit * (this.pagination.current - 1),
      this.pagination.limit * this.pagination.current
    );
  }

  activated() {
    this.pagination.limit = commonPageSizeGet();
    this.getListActionConfig();
    if (this.id) {
      // 打开详情
      this.loading = false;
      this.detailData.id = +this.id;
      this.detailData.isShow = true;
    }
  }

  beforeRouteLeave(to, from, next) {
    this.detailData.isShow = false;
    next();
  }

  // 获取自愈列表数据
  async getListActionConfig() {
    this.loading = true;
    await setMealAddModule.getNoticeWay();
    await this.actionConfigInit();
    // this.data = configList
    this.loading = false;
  }

  async actionConfigInit() {
    this.data = await listActionConfig().catch(() => {
      this.emptyType = '500';
      return [];
    });
    this.pagination.count = this.data.length;
  }

  handlePageChange(page: number) {
    this.pagination.current = page;
  }
  handlePageLimitChange(limit: number) {
    this.pagination.current = 1;
    this.pagination.limit = limit;
    commonPageSizeSet(limit);
  }
  @debounce(300)
  handleSearch(v: string) {
    this.pagination.current = 1;
    this.keyword = v;
    this.pagination.count = this.filterData.length;
    this.emptyType = v ? 'search-empty' : 'empty';
  }
  // message组件
  headerMessage() {
    return (
      <div class='header-message'>
        <i class='icon-monitor icon-tips' />
        <i18n path='处理套餐说明： 通过告警策略可以触发处理套餐，处理套餐可以与周边系统打通完成复杂的功能，甚至是达到自愈的目的。'>
          {/* <span class="message-link">{this.$t('查看文档')}</span> */}
        </i18n>
      </div>
    );
  }
  // 跳转新增套餐
  handleGoAddMeal() {
    this.$router.push({ name: 'set-meal-add' });
  }
  // title组件
  headerTitle() {
    return (
      <div class='header-title'>
        <bk-button
          class='add-btn'
          v-authority={{ active: !this.authority.MANAGE_ACTION_CONFIG }}
          theme='primary'
          onClick={() =>
            this.authority.MANAGE_ACTION_CONFIG
              ? this.handleGoAddMeal()
              : this.handleShowAuthorityDetail(ruleAuth.MANAGE_ACTION_CONFIG)
          }
        >
          <span class='icon-monitor icon-plus-line mr-6' />
          {this.$t('添加套餐')}
        </bk-button>
        <bk-input
          class='search-input'
          behavior='simplicity'
          placeholder={this.$t('搜索套餐名称 / 类型 / 修改人')}
          right-icon='bk-icon icon-search'
          value={this.keyword}
          on-change={this.handleSearch}
        />
      </div>
    );
  }
  handleDeleteRow(row: IRowData) {
    const h = this.$createElement;
    this.$bkInfo({
      type: 'warning',
      title: this.$t('确认删除该套餐？'),
      subHeader: h(DeleteSubtitle, {
        props: {
          title: this.$tc('套餐名称'),
          name: row.name,
        },
      }),
      confirmLoading: true,

      confirmFn: async () => {
        const ret = await destroyActionConfig(row.id)
          .then(() => true)
          .catch(() => false);
        if (ret) this.getListActionConfig();
      },
    });
  }
  handleSwichChange({ id, is_enabled: isEnabled }) {
    return new Promise((resolve, reject) => {
      this.$bkInfo({
        title: this.$t('确定{status}此套餐吗？', { status: !isEnabled ? this.$t('启用') : this.$t('停用') }),

        confirmFn: async () => {
          const result = await partialUpdateActionConfig(id, {
            is_enabled: !isEnabled,
          })
            .then(() => true)
            .catch(() => false);
          if (result) {
            this.data.find(item => item.id === id).is_enabled = !isEnabled;
          }
          result ? resolve(true) : reject();
        },
        cancelFn: reject,
      });
    });
  }
  handleShowDetail(id: number, pluginType: string) {
    this.detailData.id = id;
    this.detailData.isShow = true;
    this.detailData.width = pluginType === 'webhook' ? 700 : 540;
  }
  /**
   * @description: 格式化id展示
   * @param {object} row 表格行数据
   * @return {*}
   */
  idFormatter(row: { id: number }) {
    return `#${row.id}`;
  }
  /**
   * @description: 跳转策略列表
   * @param {*} row 表格行数据
   * @return {*}
   */
  handleToStrategyList(row) {
    if (!row.strategy_count) return;
    this.$router.push({
      name: 'strategy-config',
      params: {
        actionName: row.name,
      },
    });
  }

  // 权限
  isAuth(bkBizId: number): {
    authority: boolean;
    authorityType: string;
  } {
    return {
      authority: bkBizId === 0 ? this.authority.MANAGE_PUBLIC_ACTION_CONFIG : this.authority.MANAGE_ACTION_CONFIG,
      authorityType: bkBizId === 0 ? ruleAuth.MANAGE_PUBLIC_ACTION_CONFIG : ruleAuth.MANAGE_ACTION_CONFIG,
    };
  }
  handleToEventCenter(id) {
    this.$router.push({
      name: 'event-center',
      query: {
        searchType: 'action',
        activeFilterId: 'action',
        from: 'now-7d',
        to: 'now',
        queryString: isZh() ? `套餐ID: ${id}` : `action_config_id: ${id}`,
      },
    });
  }

  handleOperate(type, id) {
    if (type === 'clone') {
      this.$router.push({ path: `/clone-meal/${id}` });
    }
  }

  handleEmptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.keyword = '';
      return;
    }

    if (type === 'refresh') {
      this.emptyType = 'empty';
      this.actionConfigInit();
      return;
    }
  }

  protected render() {
    const enableScopedSlots = {
      default: ({ row }) => (
        <bk-switcher
          v-authority={{ active: !this.isAuth(Number.parseInt(row.bk_biz_id)).authority }}
          preCheck={() =>
            this.isAuth(Number.parseInt(row.bk_biz_id)).authority
              ? this.handleSwichChange(row)
              : this.handleShowAuthorityDetail(this.isAuth(Number.parseInt(row.bk_biz_id)).authorityType)
          }
          size='small'
          theme='primary'
          value={row.is_enabled}
        />
      ),
    };
    const oprateScopedSlots = {
      default: ({ row }) => (
        <div class='operate-wrap'>
          {/* <bk-button text theme="primary">{this.$t('关联策略')} </bk-button> */}
          <bk-button
            class='mr-10'
            v-authority={{ active: !this.isAuth(Number.parseInt(row.bk_biz_id)).authority }}
            disabled={!row.edit_allowed}
            theme='primary'
            text
            onClick={() =>
              this.isAuth(Number.parseInt(row.bk_biz_id)).authority
                ? this.$router.push({ path: `/set-meal-edit/${row.id}` })
                : this.handleShowAuthorityDetail(this.isAuth(Number.parseInt(row.bk_biz_id)).authorityType)
            }
          >
            {this.$t('button-编辑')}
          </bk-button>
          <bk-button
            class='mr-10'
            v-authority={{ active: !this.isAuth(Number.parseInt(row.bk_biz_id)).authority }}
            disabled={!row.delete_allowed}
            theme='primary'
            text
            onClick={() =>
              this.isAuth(Number.parseInt(row.bk_biz_id)).authority
                ? this.handleDeleteRow(row)
                : this.handleShowAuthorityDetail(this.isAuth(Number.parseInt(row.bk_biz_id)).authorityType)
            }
          >
            {this.$t('删除')}
          </bk-button>
          <OperateOptions
            options={
              {
                outside: [],
                popover: [
                  {
                    id: 'clone',
                    name: window.i18n.t('克隆'),
                    authority: this.isAuth(Number.parseInt(row.bk_biz_id)).authority,
                    authorityDetail: this.isAuth(Number.parseInt(row.bk_biz_id)).authorityType,
                  },
                ],
              } as any
            }
            onOptionClick={type => this.handleOperate(type, row.id)}
          />
        </div>
      ),
    };
    return (
      <div
        class='fta-set-meal'
        // v-bkloading={{ isLoading: this.loading }}
      >
        {this.headerTitle()}
        <div class='set-table'>
          {this.headerMessage()}
          {this.loading ? (
            <TableSkeleton type={1} />
          ) : (
            <bk-table
              data={this.tableData}
              header-border={false}
              outer-border={false}
              pagination={this.pagination}
              on-page-change={this.handlePageChange}
              on-page-limit-change={this.handlePageLimitChange}
            >
              <div slot='empty'>
                <EmptyStatus
                  type={this.emptyType}
                  onOperation={this.handleEmptyOperation}
                />
              </div>
              <bk-table-column
                width={80}
                formatter={this.idFormatter}
                label={'ID'}
              />
              <bk-table-column
                width='140'
                scopedSlots={{
                  default: ({ row: { name, id, plugin_type, bk_biz_id } }) => (
                    <div class='meal-name-div'>
                      <div
                        class='meal-name'
                        onClick={() => this.handleShowDetail(id, plugin_type)}
                      >
                        {name}
                      </div>
                      {!bk_biz_id && (
                        <span
                          class='default-msg'
                          v-bk-tooltips={{ content: this.$t('默认策略不允许删除') }}
                        >
                          {this.$t('默认')}
                        </span>
                      )}
                    </div>
                  ),
                }}
                label={this.$t('套餐名称')}
                show-overflow-tooltip
              />
              <bk-table-column
                width='110'
                label={this.$t('套餐类型')}
                prop='plugin_name'
                show-overflow-tooltip
              />
              <bk-table-column
                width='110'
                scopedSlots={{
                  default: ({ row }) => (
                    <bk-button
                      class={{ 'is-empty': !row.strategy_count }}
                      text
                      onClick={() => this.handleToStrategyList(row)}
                    >
                      {row.strategy_count || '--'}
                    </bk-button>
                  ),
                }}
                align='center'
                label={this.$t('关联策略')}
              />
              <bk-table-column
                width='170'
                scopedSlots={{
                  default: ({ row }) => (
                    <bk-button
                      class={{ 'is-empty': !row.execute_count }}
                      text
                      onClick={() => row.execute_count && this.handleToEventCenter(row.id)}
                    >
                      {row.execute_count || '--'}
                    </bk-button>
                  ),
                }}
                align='center'
                label={this.$t('触发次数(近 7 天)')}
              />
              <bk-table-column
                align='left'
                formatter={row => (row.update_user ? <bk-user-display-name user-id={row.update_user} /> : '--')}
                label={this.$t('最近更新人')}
                prop='update_user'
              />
              <bk-table-column
                width='180'
                align='left'
                label={this.$t('最近更新时间')}
                prop='update_time'
              />
              <bk-table-column
                width='150'
                align='left'
                label={this.$t('配置来源')}
                scopedSlots={{ default: ({ row }) => row.config_source || '--' }}
              />
              <bk-table-column
                width='160'
                align='left'
                label={this.$t('配置分组')}
                scopedSlots={{ default: ({ row }) => row.app || '--' }}
              />
              <bk-table-column
                align='center'
                label={this.$t('启/停')}
                scopedSlots={enableScopedSlots}
              />
              <bk-table-column
                width='150'
                label={this.$t('操作')}
                scopedSlots={oprateScopedSlots}
              />
            </bk-table>
          )}
        </div>
        <SetMealDetail
          id={this.detailData.id}
          width={this.detailData.width}
          isShow={this.detailData.isShow}
          onShowChange={v => (this.detailData.isShow = v)}
        />
      </div>
    );
  }
}
export default tsx.ofType<IContainerProps>().convert(Container);
