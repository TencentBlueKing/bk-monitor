/* Copyright (C) 2021 THL A29 Limited, a Tencent company. MIT License. */
/** Existing favorite API fields. Query state is forwarded without narrowing it. */
export type FavoriteGroupId = string | number | null;
export interface FavoriteRecord {
  id: number;
  name: string;
  keyword: string;
  group_id: FavoriteGroupId;
  group_name: string | undefined;
  search_fields: unknown;
  visible_type: string;
  display_fields: unknown;
  is_enable_display_fields: boolean;
  search_mode: string;
  params: { ip_chooser?: unknown; addition?: unknown };
  updated_by: string;
  updated_at: string;
  editName?: boolean;
  editGroup?: boolean;
  groupName?: string;
}
export interface FavoriteGroup {
  id: FavoriteGroupId;
  name: string;
  favorites?: FavoriteRecord[];
}
export interface FavoriteResponse<T> {
  result: boolean;
  data: T;
}
