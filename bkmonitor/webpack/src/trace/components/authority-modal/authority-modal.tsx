/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { computed, defineComponent, ref, watch } from 'vue';

import { Button, Dialog, Loading } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import lockImg from '../../static/img/lock-radius.svg';
import { useAuthorityStore } from '../../store/modules/authority';

import './authority-modal.scss';

export default defineComponent({
  name: 'AuthorityModal',
  setup() {
    const authorityStore = useAuthorityStore();
    const { t } = useI18n();

    const isModalShow = ref<boolean>(false);

    const loading = computed<boolean>(() => authorityStore.loading);
    const show = computed<boolean>(() => authorityStore.showDialog);
    const applyUrl = computed<string>(() => authorityStore.applyUrl);
    const authorityDetail = computed<any>(() => authorityStore.authorityDetail);

    const getResource = (resoures: any) => {
      if (resoures.length === 0) {
        return ['--'];
      }

      const data: any = [];
      resoures.forEach((resource: any) => {
        if (resource.instances.length > 0) {
          const instances = resource.instances
            .map((instanceItem: any) => instanceItem.map((item: any) => item.name).join('，'))
            .join('，');
          const resourceItemData = `${resource.typeName}：${instances}`;
          data.push(resourceItemData);
        }
      });
      return data;
    };
    const goToApply = () => {
      try {
        if (self === top) {
          window.open(applyUrl.value, '_blank');
        } else {
          (top as any).BLUEKING.api.open_app_by_other('bk_iam', applyUrl.value);
        }
      } catch {
        // 防止跨域问题
        window.open(applyUrl.value, '_blank');
      }
    };
    const handleCloseDialog = () => {
      isModalShow.value = false;
      authorityStore.setShowAuthortyDialog(false);
    };

    watch(show, val => {
      isModalShow.value = val;
    });

    return {
      isModalShow,
      loading,
      show,
      applyUrl,
      authorityDetail,
      handleCloseDialog,
      getResource,
      goToApply,
      t,
    };
  },
  render() {
    const permissionModal = () => (
      <div class='permission-modal'>
        <Loading loading={this.loading}>
          <div class='permission-header'>
            <span class='title-icon'>
              <img
                class='lock-img'
                alt='permission-lock'
                src={lockImg}
              />
            </span>
            <h3>{this.t('该操作需要以下权限')}</h3>
          </div>
          <table class='permission-table table-header'>
            <thead>
              <tr>
                <th>{this.t('需要申请的权限')}</th>
                <th>{this.t('关联的资源实例')}</th>
              </tr>
            </thead>
          </table>
          <div class='table-content'>
            <table class='permission-table'>
              <tbody>
                {this.authorityDetail?.actions && this.authorityDetail.actions.length > 0 ? (
                  this.authorityDetail.actions.map((action: any, index: number) => (
                    <tr key={index}>
                      <td>{action.name}</td>
                      <td>
                        {this.getResource(action.relatedResourceTypes).map((reItem: string, reIndex: number) => (
                          <p
                            key={reIndex}
                            class='resource-type-item'
                          >
                            {reItem}
                          </p>
                        ))}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      class='no-data'
                      colspan='2'
                    >
                      {this.t('无数据')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Loading>
      </div>
    );

    const modalFooter = () => (
      <div class='permission-footer'>
        <div class='button-group'>
          <Button
            theme='primary'
            onClick={() => this.goToApply()}
          >
            {this.t('去申请')}
          </Button>
          <Button onClick={() => this.handleCloseDialog()}>{this.t('取消')}</Button>
        </div>
      </div>
    );

    return (
      <Dialog
        width='768'
        height={380} // todo
        v-slots={{
          default: () => permissionModal(),
          footer: () => modalFooter(),
        }}
        headerAlign='left'
        isShow={this.isModalShow}
        title=''
        onClosed={this.handleCloseDialog}
      />
    );
  },
});
