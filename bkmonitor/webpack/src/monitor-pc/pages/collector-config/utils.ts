/**
 * @description 获取维度注入参数
 * @param configData 配置数据
 * @returns 维度注入参数
 */
export const getCustomDmsInsertParams = (configData: {
  mode: string;
  name: string;
  default: any;
  type: string;
}):
  | {
      error: boolean;
      message: string;
      params: any;
    }
  | undefined => {
  if (configData.mode === 'dms_insert') {
    const params = {};
    let errorMessage = '';
    if (Array.isArray(configData.default)) {
      for (const item of configData.default) {
        if (typeof item === 'string' && item.includes(':')) {
          const [key, value] = item.split(':');
          if (key && value) {
            params[key] = value;
          }
        } else {
          errorMessage = `${item} 维度注入标签格式应为 key:value`;
          break;
        }
      }
      if (errorMessage) {
        return {
          error: true,
          message: errorMessage,
          params: {},
        };
      }
      return {
        error: false,
        message: '',
        params,
      };
    }
    return {
      error: false,
      message: '',
      params: configData.default,
    };
  }
  return;
};
