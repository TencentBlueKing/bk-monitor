/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Ref, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { proxyHostInfo, type ICustomTimeSeriesDetail } from '../../../service';

import './index.scss';

/**
 * 组件属性接口
 */
interface IProps {
  /** 是否显示帮助面板 */
  isShow: boolean;
  /** 详情数据，包含数据通道ID、访问令牌等信息 */
  detailData: ICustomTimeSeriesDetail;
}
@Component
export default class HelpInfo extends tsc<IProps> {
  /** 是否显示帮助面板 */
  @Prop({ default: false }) isShow: IProps['isShow'];
  /** 详情数据，包含数据通道ID、访问令牌、协议类型等信息 */
  @Prop({ default: () => ({}) }) detailData: IProps['detailData'];
  /** 用于复制JSON数据上报样例的隐藏文本域引用 */
  @Ref('textCopy') readonly textCopy!: HTMLTextAreaElement;
  /** 用于复制Golang Prometheus SDK代码的隐藏文本域引用 */
  @Ref('golangCopy') readonly golangCopy!: HTMLTextAreaElement;
  /** 用于复制Python Prometheus SDK代码的隐藏文本域引用 */
  @Ref('pythonCopy') readonly pythonCopy!: HTMLTextAreaElement;

  /** 是否显示右侧帮助栏 */
  isShowHelpPanel = true;
  /** 云区域分类数据，包含各云区域的IP和ID信息 */
  proxyInfo: ServiceReturnType<typeof proxyHostInfo> = [];
  /** 数据上报格式样例（JSON协议） */
  preData = '';
  /** SDK接入数据，包含各语言的示例代码 */
  sdkData: {
    /** Golang语言的Prometheus SDK接入示例代码 */
    preGoOne?: string;
    /** Python语言的Prometheus SDK接入示例代码 */
    prePythonOne?: string;
  } = {};

  /**
   * 获取当前页面类型：自定义事件或自定义时序
   */
  get type(): string {
    return this.$route.name === 'custom-detail-event' ? 'customEvent' : 'customTimeSeries';
  }

  /**
   * 监听isShow属性变化，更新帮助面板显示状态
   * @param val 是否显示帮助面板
   */
  @Watch('isShow', { immediate: true })
  handleIsShowChange(val: boolean): void {
    this.isShowHelpPanel = val;
  }

  /**
   * 监听detailData属性变化，生成数据上报样例和SDK接入代码
   * @param detailData 详情数据对象
   */
  @Watch('detailData', { immediate: true })
  handleDetailDataChange(detailData: ICustomTimeSeriesDetail): void {
    // 生成指标部分的JSON字符串模板
    const str = `# ${this.$t('指标，必需项')}
        "metrics": {
            "cpu_load": 10
        },`;

    this.preData = `{
        # ${this.$t('数据通道标识，必需项')}
        "data_id": ${detailData.bk_data_id},
        # ${this.$t('数据通道标识验证码，必需项')}
        "access_token": "${detailData.access_token}",
        "data": [{
            ${str}
            # ${this.$t('来源标识如IP，必需项')}
            "target": "127.0.0.1",
            # ${this.$t('自定义维度，非必需项')}
            "dimension": {
                "module": "db",
                "location": "guangdong",
                # ${this.$t('event_type 为非必须项，用于标记事件类型，默认为异常事件')}
                # ${this.$t('recovery:恢复事件，abnormal:异常事件')}
                "event_type": "abnormal"
            },
            # ${this.$t('数据时间，精确到毫秒，非必需项')}
            "timestamp": ${new Date().getTime()}
        }]
    }`;

    // 处理 Prometheus 类型的特殊内容
    if (detailData.protocol === 'prometheus') {
      this.sdkData.preGoOne = `type bkClient struct{}
func (c *bkClient) Do(r *http.Request) (*http.Response, error) {
	r.Header.Set("X-BK-TOKEN", "$TOKEN")
  // TOKEN 即在 saas 侧申请的 token
	return http.DefaultClient.Do(r)
}

func main() {
	register := prometheus.NewRegistry()
	register.MustRegister(promcollectors.NewGoCollector())

	name := "reporter"
	// 1) 指定蓝鲸上报端点 $bk.host:$bk.port
	pusher := push.New("\${PROXY_IP}:4318", name).
  Gatherer(register)

	// 2) 传入自定义 Client
	pusher.Client(&bkClient{})

	ticker := time.Tick(15 * time.Second)
	for {
		<-ticker
		if err := pusher.Push(); err != nil {
			log.Println("failed to push records to the server,
      error:", err)
			continue
		}
		log.Println("push records to the server successfully")
	}
}`;

      this.sdkData.prePythonOne = `from prometheus_client.exposition import
default_handler

# 定义基于监控 token 的上报 handler 方法
def bk_handler(url, method, timeout, headers, data):
    def handle():
        headers.append(['X-BK-TOKEN', '$TOKEN'])
        # TOKEN 即在 saas 侧申请的 token
        default_handler(url, method, timeout, headers, data)()
    return handle

from prometheus_client import CollectorRegistry,
Gauge, push_to_gateway
from prometheus_client.exposition
import bk_token_handler

registry = CollectorRegistry()
g = Gauge('job_last_success_unixtime',
'Last time a batch job successfully finished', registry=registry)
g.set_to_current_time()
push_to_gateway('\${PROXY_IP}:4318', job='batchA',
registry=registry, handler=bk_handler) # 上述自定义 handler`;
    }
  }

  /**
   * 加载静态数据（云区域和单位列表）
   */
  async loadStaticData(): Promise<void> {
    try {
      const proxyInfo = await proxyHostInfo();

      this.proxyInfo = proxyInfo;
    } catch (error) {
      console.error('加载静态数据失败:', error);
    }
  }

  /**
   * 组件创建时的初始化
   */
  async created(): Promise<void> {
    await this.loadStaticData();
  }

  /**
   * 复制数据上报样例到剪贴板
   * 将JSON格式的数据上报示例复制到剪贴板，并显示成功提示
   */
  handleCopyData(): void {
    // 指标数据部分的JSON字符串
    const str = `"metrics": {
            "cpu_load": 10
        },`;
    // 完整的数据上报示例JSON
    const example = `{
      "data_id": ${this.detailData.bk_data_id},
      "access_token": "${this.detailData.access_token}",
      "data": [{
          ${str}
          "target": "127.0.0.1",
          "dimension": {
              "module": "db",
              "location": "guangdong"
          },
          "timestamp": ${new Date().getTime()}
      }]
    }`;

    this.textCopy.value = example;
    this.textCopy.select();
    document.execCommand('copy');

    this.$bkMessage({
      theme: 'success',
      message: this.$t('样例复制成功'),
    });
  }

  /**
   * 复制Prometheus SDK接入流程代码到剪贴板
   * @param type 复制类型，'golangCopy'表示Golang代码，其他值表示Python代码
   */
  handleCopyPrometheus(type: string): void {
    // 根据类型选择对应的文本域引用
    const textarea = type === 'golangCopy' ? this.golangCopy : this.pythonCopy;
    // 根据类型选择对应的示例代码
    const text = type === 'golangCopy' ? this.sdkData.preGoOne : this.sdkData.prePythonOne;
    if (textarea && text) {
      textarea.value = text;
      textarea.select();
      document.execCommand('copy');

      this.$bkMessage({
        theme: 'success',
        message: this.$t('样例复制成功'),
      });
    }
  }

  /**
   * 渲染帮助信息组件
   * 根据协议类型（JSON或Prometheus）显示不同的帮助内容
   * @returns 组件JSX结构
   */
  render() {
    return (
      <div class={['right-window-main', this.isShowHelpPanel ? 'active' : '']}>
        {/* 右边展开收起按钮 */}
        <div
          class={['right-button', this.isShowHelpPanel ? 'active-buttom' : '']}
          onClick={() => this.handleIsShowChange(!this.isShowHelpPanel)}
        >
          {this.isShowHelpPanel ? (
            <i class='icon-monitor icon-arrow-right icon' />
          ) : (
            <i class='icon-monitor icon-arrow-left icon' />
          )}
        </div>

        {/* 帮助标题 */}
        <div class='right-window-title'>
          <span>{this.type === 'customEvent' ? this.$t('自定义事件帮助') : this.$t('自定义指标帮助')}</span>
          <span
            class='title-right'
            onClick={() => this.handleIsShowChange(!this.isShowHelpPanel)}
          >
            <span class='line' />
          </span>
        </div>

        {/* 帮助内容 */}
        <div class='right-window-content'>
          {/* JSON协议注意事项 */}
          {this.detailData.protocol !== 'prometheus' && (
            <div>
              <div class='content-title'>{this.$t('注意事项')}</div>
              <span>{this.$t('API频率限制 1000/min，单次上报Body最大为500KB')}</span>
            </div>
          )}

          <div class={['content-title', this.detailData.protocol !== 'prometheus' ? 'content-interval' : '']}>
            {this.$t('使用方法')}
          </div>

          {/* 云区域信息 */}
          <div class='content-row'>
            <span>
              {this.detailData.protocol === 'prometheus'
                ? this.$t('不同云区域上报端点信息')
                : this.$t('不同云区域Proxy信息')}
            </span>
            <div class='content-example'>
              {this.proxyInfo.map((item, index) => (
                <div key={index}>
                  {this.$t('管控区域')} {item.bkCloudId}
                  <span style={{ marginLeft: '10px' }}>{item.ip}</span>
                </div>
              ))}
            </div>
          </div>

          {/* JSON协议调用样例 */}
          {this.detailData.protocol !== 'prometheus' && (
            <div class='content-row'>
              <span>{this.$t('命令行直接调用样例')}</span>
              <div class='content-example'>
                curl -g -X POST http://$&#123;PROXY_IP&#125;:10205/v2/push/ -d "$&#123;REPORT_DATA&#125;"
              </div>
            </div>
          )}

          {/* Prometheus协议相关内容 */}
          {this.detailData.protocol === 'prometheus' ? (
            <div>
              <div class='content-title content-interval'>{this.$t('数据上报端点样例')}</div>
              <div class='content-row'>
                <pre class='content-example'>http://$&#123;PROXY_IP&#125;:4318</pre>
              </div>
              <div class='content-row mt10'>
                <div class='content-title content-interval'>{this.$t('sdk接入流程')}</div>
                <div>
                  {this.$t(
                    '用户使用 prometheus 原始 SDK 上报即可，不过需要指定蓝鲸的上报端点（$host:$port）以及 HTTP Headers。'
                  )}
                </div>
                <pre class='content-example'>X-BK-TOKEN=$TOKEN</pre>
                <div class='mt10'>
                  {this.$t('prometheus sdk 库：https://prometheus.io/docs/instrumenting/clientlibs/')}
                </div>
                <div class='mt10'>
                  {this.$t(
                    '如果上报渠道不支持加入自定义 headers, 也可以使用 BasicAuth 进行验证, user: bkmonitor, password: $TOKEN'
                  )}
                </div>
              </div>

              {/* Golang 示例部分 */}
              <div class='content-row mt10'>
                <div>{this.$t('各语言接入示例')} :</div>
                <div class='mt5'>Golang</div>
                <div class='mt5'>
                  {this.$t(
                    '1. 补充 headers，用于携带 token 信息。定义 Client 行为，由于 prometheus sdk 没有提供新增或者修改 Headers 的方法，所以需要实现 Do() interface，代码示例如下：'
                  )}
                </div>
                <div class='mt5'>
                  {this.$t(
                    '2. 填写上报端点，在 `push.New("$endpoint", name)` 里指定。然后需要将自定义的 client 传入到 `pusher.Client($bkClient{})` 里面。'
                  )}
                </div>
                <div class='content-prometheus'>
                  <pre class='content-example'>{this.sdkData.preGoOne}</pre>
                  <div
                    class='content-copy-prometheus'
                    onClick={() => this.handleCopyPrometheus('golangCopy')}
                  >
                    <i class='icon-monitor icon-mc-copy' />
                  </div>
                  <textarea
                    ref='golangCopy'
                    class='copy-textarea'
                    style='display: none;'
                  />
                </div>
              </div>

              {/* Python 示例部分 */}
              <div class='content-row'>
                <div>Python</div>
                <div class='mt5'>{this.$t('1. 补充 headers，用于携带 token 信息。实现一个自定义的 handler。')}</div>
                <div>
                  {this.$t(
                    '2. 填写上报端点，在 `push_to_gateway("$endpoint", ...)` 里指定。然后将自定义的 handler 传入到函数里。'
                  )}
                </div>
                <div class='content-prometheus'>
                  <pre class='content-example'>{this.sdkData.prePythonOne}</pre>
                  <div
                    class='content-copy-prometheus'
                    onClick={() => this.handleCopyPrometheus('pythonCopy')}
                  >
                    <i class='icon-monitor icon-mc-copy' />
                  </div>
                  <textarea
                    ref='pythonCopy'
                    class='copy-textarea'
                    style='display: none;'
                  />
                </div>
              </div>
            </div>
          ) : (
            <div class='content-row'>
              <span>{this.$t('数据上报格式样例')}</span>
              <pre class='content-example'>{this.preData}</pre>
              <div
                class='content-copy'
                onClick={this.handleCopyData}
              >
                <i class='icon-monitor icon-mc-copy' />
              </div>
              <textarea
                ref='textCopy'
                class='copy-textarea'
              />
            </div>
          )}
        </div>
      </div>
    );
  }
}
