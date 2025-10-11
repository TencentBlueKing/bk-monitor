import { Ref, ref } from "vue";
import { IAssitantInstance, IAssitantOptions, IRowSendData } from ".";

/**
 * AI 助手工具类
 */
class AiAssitantHelper {
  aiAssitantRef: Ref<IAssitantInstance | null>;
  activePosition: 'search-bar' | 'row-box' | 'text-selection';
  constructor() {
    this.aiAssitantRef = ref<IAssitantInstance>(null);
    this.activePosition = 'search-bar';
  }

  /**
   * 获取 AI 助手实例
   * 这里返回的是一个 Ref 对象，对象为AI助手组件实例
   * @returns 
   */
  getAiAssitantInstance() {
    return this.aiAssitantRef;
  }

  /**
   * 设置 AI 助手实例
   * @param aiAssitantRef 
   */
  setAiAssitantRef(aiAssitantRef: Ref<any | null>) {
    this.aiAssitantRef = aiAssitantRef;
  }

  /**
   * 搜索栏显示 AI 助手
   * @param options 
   */
  showAiAssitant(options: Partial<IAssitantOptions> = {}) {
    this.updateAiAssitantOptions(options).then(() => {
      this.activePosition = 'search-bar';
      this.aiAssitantRef.value?.show();
    });
  }

  /**
   * 更新 AI 助手实例的选项
   * @param options 
   */
  updateAiAssitantOptions(options: Partial<IAssitantOptions> = {}) {
    return this.aiAssitantRef.value?.updateOptions(options);
  }

  /**
   * 打开 AI 助手并带有上下文信息
   * @param sendMsg 
   * @param args 
   */
  openAiAssitant(sendMsg: boolean, args: IRowSendData) {
    this.updateAiAssitantOptions().then(() => {
      this.activePosition = 'row-box';
      this.aiAssitantRef.value?.open(sendMsg, args);
    });
  }

  /**
   * 设置引用文本
   * @param text 
   */
  setCiteText(text: string) {
    this.updateAiAssitantOptions().then(() => {
      this.activePosition = 'text-selection';
      this.aiAssitantRef.value?.setCiteText(text);
    });
  }

  /**
   * 判断是否点击了 AI 助手
   * @param e 
   * @returns 
   */
  isClickAiAssitant(e: MouseEvent) {
    const target = e.target as HTMLElement;
    return target.closest('.ai-blueking-container-wrapper');
  }

  /**
   * 搜索栏使用AI助手时，点击其他位置关闭 AI 助手
   * @param e 
   */
  closeAiAssitantWithSearchBar(e: MouseEvent) {
    if (this.aiAssitantRef.value?.isShown() && this.activePosition === 'search-bar' && !this.isClickAiAssitant(e)) {
      this.aiAssitantRef.value?.close();
    }
  }

  /**
   * 设置位置
   * @param x x轴坐标
   * @param y y轴坐标
   * @param width 宽度
   * @param height 高度
   */
  setPosition(x?: number, y?: number, width?: number, height?: number) {
    this.aiAssitantRef.value?.setPosition(x, y, width, height);
  }

  /**
   * 判断 AI 助手是否显示
   * @returns 
   */
  isShown() {
    return this.aiAssitantRef.value?.isShown();
  }
}

/**
 * 单例
 */
export default new AiAssitantHelper();