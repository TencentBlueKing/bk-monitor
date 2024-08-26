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

import { Component, ModelSync, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Dialog, Table } from 'bk-magic-vue';

interface IProps {
  value: boolean;
}

@Component({
  components: { Dialog, Table },
})
export default class IndexImportModal extends tsc<IProps> {
  @ModelSync('value', 'change', { type: Boolean })
  localIshowValue!: boolean;

  syncTypeList = [
    { name: this.$t('同步源日志信息'), id: 'source_log_info' },
    { name: this.$t('同步字段清洗配置'), id: 'field_clear_config' },
    { name: this.$t('同步存储配置'), id: 'storage_config' },
    { name: this.$t('同步采集目标'), id: 'acquisition_target' },
  ];
  syncType = ['source_log_info'];
  isTableLoading = false;
  collectList = [];
  emptyType = '';

  @Watch('localIshowValue')
  handleIsShowChange(val) {
    if (val) {
      this.requestData();
    }
  }

  requestData = () => {
    this.isTableLoading = true;
    const ids = this.$route.query.ids as string; // 根据id来检索
    const collectorIdList = ids ? decodeURIComponent(ids) : [];
    this.collectList.length = 0;
    this.collectList = [];
    (this as any).$http
      .request('collect/getAllCollectors', {
        query: {
          bk_biz_id: this.$store.state.bkBizId,
          collector_id_list: collectorIdList,
          have_data_id: 1,
          not_custom: 1,
        },
      })
      .then(res => {
        const { data } = res;

        if (data?.length) {
          this.collectList.push(...data);
          console.log('result', this.collectList);
        }
      })
      .catch(() => {
        this.emptyType = '500';
      })
      .finally(() => {
        this.isTableLoading = false;
      });
  };

  render() {
    return (
      <bk-dialog
        width={1200}
        ext-cls='index-import-modal'
        v-model={this.localIshowValue}
        header-position='left'
        mask-close={false}
        theme='primary'
        title={this.$t('索引配置导入')}
      >
        <div class='content'>
          <bk-form
            form-type='vertical'
            label-width={200}
          >
            <bk-form-item required={true}>
              <bk-checkbox-group v-model={this.syncType}>
                {this.syncTypeList.map(item => (
                  <bk-checkbox
                    key={item.id}
                    style='margin-right: 24px;'
                    value={item.id}
                  >
                    {item.name}
                  </bk-checkbox>
                ))}
              </bk-checkbox-group>
            </bk-form-item>
            <bk-form-item label={this.$t('请选择目标索引集')}>
              <bk-table
                v-bkloading={{ isLoading: this.isTableLoading }}
                data={this.collectList}
              >
                <bk-table-column
                  label='索引集'
                  prop='collector_config_name'
                ></bk-table-column>
                <bk-table-column
                  label='采集路径'
                  prop='status'
                ></bk-table-column>
                <bk-table-column
                  label='采集模式'
                  prop='status'
                ></bk-table-column>
                <bk-table-column
                  label='存储集群'
                  prop='status'
                ></bk-table-column>
                <bk-table-column
                  label='存储时长'
                  prop='status'
                ></bk-table-column>
              </bk-table>
            </bk-form-item>
          </bk-form>
        </div>
      </bk-dialog>
    );
  }
}
