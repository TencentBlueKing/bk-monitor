export type GrepRequestResult = {
  offset: number;
  is_loading: boolean;
  list: any[];
  has_more: boolean;
  is_error: boolean;
  exception_msg: string;
};
