import { defineComponent, ref } from 'vue';
import AIBlueking, { ChatHelper, MessageStatus, RoleType } from '@blueking/ai-blueking/vue2';
import { random } from '../common/util';
import '@blueking/ai-blueking/dist/vue2/style.css';
interface ISendData {
  content: string; // 用户输入的内容
  cite?: string; // 引用的内容
  prompt?: string; // 使用的 prompt 模板
}

interface IRowSendData {
  space_uid: string;
  index_set_id: string;
  log_data: unknown;
  message: string;
  index: number;
  chat_context: unknown;
  'chat_context.role': RoleType;
  'chat_context.content': string;
}
export default defineComponent({
  setup(props, { expose }) {
    const loading = ref(false);
    const messages = ref([]);
    // const positionLimit = ref({ bottom: 100, right: 100 });
    const prompts = ref([]);
    let chatid = random(10);
    const sizeLimit = ref({
      height: 400,
      width: 800,
    });

    const top = window.innerHeight - 700;
    const left = window.innerWidth - 900;

    const startPosition = ref({ top: top > 0 ? top : 20, bottom: 100, left: left > 0 ? left : 100, right: 40 });
    const isShow = ref(false);
    const aiFixedLinkArgs = { index: null, id: null };

    const handleStart = () => {
      loading.value = true;
      messages.value.push({
        role: RoleType.Assistant,
        content: '正在分析当前日志',
        status: MessageStatus.Loading,
      });
    };

    // 接收消息
    const handleReceiveMessage = (message: string, id: number | string) => {
      const currentMessage = messages.value.at(-1);

      if (currentMessage.status === MessageStatus.Loading) {
        // 如果是loading状态，直接覆盖
        currentMessage.content = message;
        currentMessage.status = MessageStatus.Success;
      } else if (currentMessage.status === MessageStatus.Success) {
        // 如果是后续消息，就追加消息
        currentMessage.content += message;
      }
    };

    // 聊天结束
    const handleEnd = (id: number | string, message?: string) => {
      loading.value = false;
      const currentMessage = messages.value.at(-1);
      if (message) {
        // done 的情况下，返回 message，直接覆盖
        currentMessage.content = message;
        currentMessage.status = MessageStatus.Success;
      } else if (currentMessage.status === MessageStatus.Loading) {
        // loading 情况下终止
        currentMessage.content = '聊天内容已中断';
        currentMessage.status = MessageStatus.Error;
      }
    };

    // 错误处理
    const handleError = (message: string, code: string | number, id: number | string) => {
      if (message.includes('user authentication failed')) {
        // 未登录，跳转登录
        const loginUrl = new URL(process.env.BK_LOGIN_URL);
        loginUrl.searchParams.append('c_url', location.origin);
        window.location.href = loginUrl.href;
      } else {
        // 处理错误消息
        const currentMessage = messages.value.at(-1);
        currentMessage.status = MessageStatus.Error;
        currentMessage.content = message;
        loading.value = false;
      }
    };

    const prefix = window.AJAX_URL_PREFIX || '/api/v1';
    const chatHelper = new ChatHelper(
      `${prefix}ai_assistant/interpret_log/`,
      handleStart,
      handleReceiveMessage,
      handleEnd,
      handleError,
    );

    const handleChoosePrompt = prompt => {};
    const handleClose = () => {
      isShow.value = false;
    };
    // 清空消息
    const handleClear = () => {
      messages.value = [];
      messages.value.push({
        role: RoleType.User,
        content: `<span  data-ai="{ type: 'link', data: '[${aiFixedLinkArgs.index}, ${aiFixedLinkArgs.id}]' }" class="ai-clickable" >分析当前日志...</span >`,
        status: MessageStatus.Success,
        isFixedMsg: true,
      });
    };

    // 发送消息
    const handleSend = (args: ISendData) => {
      // 记录当前消息记录
      const chatHistory = [...messages.value];
      // 添加一条消息
      messages.value.push({
        role: 'user',
        content: args.content,
        cite: args.cite,
      });

      // 根据参数构造输入内容
      const input = args.prompt
        ? args.prompt // 如果有 prompt，直接使用
        : args.cite
          ? `${args.content}: ${args.cite}` // 如果有 cite，拼接 content 和 cite
          : args.content; // 否则只使用 content

      const streamArgs = {
        messages: input,
        chat_context: chatHistory,
        'chat_context.role': RoleType.User,
      };

      // ai 消息，id是唯一标识当前流，调用 chatHelper.stop 的时候需要传入
      chatHelper.stream(streamArgs, chatid, { 'X-Requested-With': 'XMLHttpRequest' });
    };

    // 外部调用启动首次聊天
    // args：Partial<IRowSendData>
    const handleSendRowAi = (args: Partial<IRowSendData>) => {
      // 记录当前消息记录
      const chatHistory = [...messages.value];
      args.chat_context = chatHistory;
      args['chat_context.role'] = RoleType.User;
      args.message = '帮我分析这条日志';

      messages.value.push({
        role: RoleType.User,
        content: `<span  data-ai="{ type: 'link', data: '[${aiFixedLinkArgs.index}, ${aiFixedLinkArgs.id}]' }" class="ai-clickable" >分析当前日志...</span >`,
        status: MessageStatus.Success,
        isFixedMsg: true,
      });

      // ai 消息，id是唯一标识当前流，调用 chatHelper.stop 的时候需要传入
      chatHelper.stream(args, chatid, { 'X-Requested-With': 'XMLHttpRequest' });
    };

    // 暂停聊天
    const handleStop = () => {
      chatHelper.stop(chatid);
    };
    const handleScroll = () => {};
    const showAiAssistant = (sendMsg = false, args: IRowSendData) => {
      // Object.assign(startPosition.value, {
      //   bottom: 100,
      //   right: 100,
      // });

      if (isShow.value) {
        handleStop();
        handleClear();
      }

      chatid = random(10);
      isShow.value = true;
      if (sendMsg) {
        Object.assign(aiFixedLinkArgs, { index: args.index, id: chatid });
        handleSendRowAi(args);
      }
    };

    const hiddenAiAssistant = () => {
      isShow.value = false;
    };

    const handleAiClick = args => {
      console.log(args);
    };

    expose({
      open: showAiAssistant,
      close: hiddenAiAssistant,
    });

    return () => (
      <AIBlueking
        background='#f5f7fa'
        head-background='linear-gradient(267deg, #2dd1f4 0%, #1482ff 95%)'
        loading={loading.value}
        messages={messages.value}
        prompts={prompts.value}
        is-show={isShow.value}
        enable-popup={false}
        startPosition={startPosition.value}
        on-choose-prompt={handleChoosePrompt}
        on-clear={handleClear}
        on-close={handleClose}
        on-send={handleSend}
        on-scroll={handleScroll}
        on-stop={handleStop}
        on-ai-click={handleAiClick}
      />
    );
  },
});
