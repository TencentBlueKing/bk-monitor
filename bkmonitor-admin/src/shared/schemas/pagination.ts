import { z } from 'zod';

export const paginationQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(20)
});

export const paginationResponseSchema = z.object({
  page: z.number().int().min(1),
  page_size: z.number().int().min(1),
  total: z.number().int().min(0)
});

export type PaginationQuery = z.infer<typeof paginationQuerySchema>;
export type PaginationResponse = z.infer<typeof paginationResponseSchema>;

export function toBackendPagination(query: PaginationQuery) {
  return {
    page: query.page,
    page_size: query.pageSize
  };
}
