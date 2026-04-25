import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

import { Button } from './ui/button';
import { Select } from './ui/select';

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  const pageNumbers = getPageNumbers(page, totalPages);

  return (
    <div className="flex items-center justify-end gap-3 p-3 text-sm text-muted-foreground">
      <Select
        className="h-8 w-20"
        value={String(pageSize)}
        onChange={(event) => onPageSizeChange(Number(event.target.value))}
      >
        <option value="20">20</option>
        <option value="50">50</option>
        <option value="100">100</option>
      </Select>

      <span>
        第 {start}-{end} 条 / 共 {total} 条
      </span>

      <div className="flex items-center gap-1">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(1)}>
          <ChevronsLeft aria-hidden="true" size={14} />
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" size={14} />
        </Button>

        {pageNumbers.map((p, i) => {
          if (p === '...') {
            return (
              <span key={`ellipsis-${i}`} className="px-1 text-xs">
                ...
              </span>
            );
          }
          return (
            <Button
              key={p}
              variant={p === page ? 'default' : 'outline'}
              size="sm"
              onClick={() => onPageChange(p)}
            >
              {p}
            </Button>
          );
        })}

        <Button
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          <ChevronRight aria-hidden="true" size={14} />
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(totalPages)}
        >
          <ChevronsRight aria-hidden="true" size={14} />
        </Button>
      </div>
    </div>
  );
}

function getPageNumbers(current: number, total: number): Array<number | '...'> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: Array<number | '...'> = [];

  if (current <= 3) {
    pages.push(1, 2, 3, 4, '...', total);
  } else if (current >= total - 2) {
    pages.push(1, '...', total - 3, total - 2, total - 1, total);
  } else {
    pages.push(1, '...', current - 1, current, current + 1, '...', total);
  }

  return pages;
}
