import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import './code-remarks-dialog.scss';
import { setCodeRemark } from 'monitor-api/modules/apm_service';
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

  handleConfirm() {
    this.loading = true;
    setCodeRemark({
      remark: this.remark,
      code: this.code,
      ...this.params,
    })
      .then(() => {
        this.$bkMessage({
          theme: 'success',
          message: this.$tc('修改备注成功')
        })
        this.$emit('success');
      })
      .finally(() => {
        this.loading = false;
      });
  }

  @Emit('showChange')
  handleCancel(show: boolean) {
    return show;
  }

  render() {
    return (
      <bk-dialog
        value={this.isShow}
        theme='primary'
        width={480}
        ext-cls='code-remarks-dialog'
        header-position='left'
        confirm-fn={this.handleConfirm}
        title={this.$tc('返回码备注说明')}
        onCancel={this.handleCancel}
        loading={this.loading}
      >
        <div class='code'>{this.code}</div>
        <bk-input
          class='remark-input'
          v-model={this.remark}
        />
      </bk-dialog>
    );
  }
}
