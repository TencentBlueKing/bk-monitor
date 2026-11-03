import { request } from '../base';

export const createChatSession = request('POST', 'ai_whale/chat/session/');
export const retrieveChatSession = request('GET', 'ai_whale/chat/session/');
export const createChatSessionContent = request('POST', 'ai_whale/chat/session_content/');
export const getChatSessionContents = request('GET', 'ai_whale/chat/session_content/content/');

export default {
  createChatSession,
  retrieveChatSession,
  createChatSessionContent,
  getChatSessionContents
};
