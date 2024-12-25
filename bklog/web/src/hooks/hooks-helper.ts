import { isElement } from 'lodash';
import { Ref } from 'vue';

export const getTargetElement = (
  target: String | HTMLElement | (() => HTMLElement) | Ref<HTMLElement>,
): HTMLElement => {
  if (typeof target === 'string') {
    return document.querySelector(target);
  }

  if (isElement(target)) {
    return target as HTMLElement;
  }

  if (typeof target === 'function') {
    return target?.();
  }

  return (target as Ref<HTMLElement>)?.value;
};
