import { base64Decode } from '@/common/util';

export function base64ToRuleArr(str: string) {
  if (!str) return [];
  try {
    const ruleList = JSON.parse(base64Decode(str));
    const ruleNewList = ruleList.reduce((pre, cur, index) => {
      const itemObj = {} as any;
      const matchVal = cur.match(/:(.*)/);
      const key = cur.substring(0, matchVal.index);
      itemObj[key] = matchVal[1];
      itemObj.__Index__ = index;
      pre.push(itemObj);
      return pre;
    }, []);
    return ruleNewList;
  } catch (e) {
    return [];
  }
}
