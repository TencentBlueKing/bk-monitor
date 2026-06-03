import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { setCodeRemark } from 'monitor-api/modules/apm_service';

import './code-remarks-dialog.scss';

interface CodeRemarksDialogProps {
  isShow: boolean;
  code: string;
  value: string;
  params: {
    app_name: string;
    service_name: string;
    kind: string;
  };
}

interface CodeRemarksDialogEvents {
  onShowChange(isShow: boolean): void;
  onSuccess(): void;
}

@Component
export default class CodeRemarksDialog extends tsc<CodeRemarksDialogProps, CodeRemarksDialogEvents> {
  @Prop({ default: false }) isShow: boolean;
  @Prop({ default: '' }) code: string;
  @Prop({ default: '' }) value: string;
  @Prop({ default: () => ({}) }) params: CodeRemarksDialogProps['params'];

  remark = '';
  loading = false;

  @Watch('isShow')
  handleShowChange(isShow: boolean) {
    if (isShow) {
      this.remark = this.value;
    } else {
      this.remark = '';
    }
  }

  /**
   * 确认修改备注
   * @param isGlobal 保存并应用为全局
   */
  handleConfirm(isGlobal = false) {
    this.loading = true;
    setCodeRemark({
      remark: this.remark,
      code: this.code,
      is_global: isGlobal || undefined,
      ...this.params,
    })
      .then(() => {
        this.$bkMessage({
          theme: 'success',
          message: this.$tc('修改备注成功'),
        });
        this.$emit('success');
      })
      .finally(() => {
        this.loading = false;
      });
  }

  handleGoToAppConfig() {
    const { query } = this.$route;
    const routeData = this.$router.resolve({
      name: 'application-config',
      params: {
        appName: query['filter-app_name'] as string,
      },
      query: {
        active: 'codeRedefine',
        type: 'remark',
      },
    });
    window.open(routeData.href, '_blank');
  }

  @Emit('showChange')
  handleCancel(show: boolean) {
    return show;
  }

  render() {
    return (
      <bk-dialog
        draggable={false}
        value={this.isShow}
        theme='primary'
        width={480}
        ext-cls='code-remarks-dialog'
        header-position='left'
        onCancel={this.handleCancel}
        loading={this.loading}
      >
        <div
          class='code-remarks-dialog-header'
          slot='header'
        >
          <div class='code-remarks-dialog-header-title'>{this.$tc('返回码备注说明')}</div>
          <bk-button
            ext-cls='log-config-btn'
            theme='primary'
            text
            onClick={this.handleGoToAppConfig}
          >
            <i class='icon-monitor icon-fenxiang' />
            <span class='code-remarks-dialog-header-text'>{this.$t('应用配置')}</span>
          </bk-button>
        </div>
        <div class='code'>{this.code}</div>
        <bk-input
          class='remark-input'
          v-model={this.remark}
        />
        <div
          class='code-remarks-dialog-footer'
          slot='footer'
        >
          <bk-button
            class='save-global-btn'
            loading={this.loading}
            outline={true}
            theme='primary'
            onClick={() => this.handleConfirm(true)}
          >
            {this.$tc('保存并应用为全局')}
          </bk-button>
          <bk-button
            loading={this.loading}
            theme='primary'
            onClick={() => this.handleConfirm()}
          >
            {this.$tc('确定')}
          </bk-button>
          <bk-button
            theme='default'
            onClick={() => this.handleCancel(false)}
          >
            {this.$tc('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
