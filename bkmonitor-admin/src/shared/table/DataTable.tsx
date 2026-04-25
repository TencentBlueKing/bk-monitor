import React from 'react';
import { flexRender, getCoreRowModel, useReactTable, type ColumnDef } from '@tanstack/react-table';

import { cn } from '../utils/cn';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from '../components/ui/table';

interface DataTableProps<TData> {
  data: TData[];
  columns: Array<ColumnDef<TData>>;
  emptyText?: string;
  striped?: boolean;
  renderExpandedRow?: (row: TData) => React.ReactNode;
}

function formatCellValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="muted-text">{'\u2013'}</span>;
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value);
}

export function DataTable<TData>({
  data,
  columns,
  emptyText = '暂无数据',
  striped,
  renderExpandedRow
}: DataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel()
  });

  return (
    <div className="w-full max-h-[calc(100vh-280px)] overflow-auto rounded-lg border border-border bg-card">
      <Table className="min-w-[920px]">
        <TableHeader className="[&_tr]:bg-muted/50">
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length > 0 ? (
            table.getRowModel().rows.map((row, rowIndex) => {
              const expandedContent = renderExpandedRow ? renderExpandedRow(row.original) : null;

              return (
                <React.Fragment key={row.id}>
                  <TableRow
                    className={cn(
                      'hover:bg-muted/30',
                      striped && rowIndex % 2 === 0 && 'bg-muted/20'
                    )}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const rendered = flexRender(cell.column.columnDef.cell, cell.getContext());
                      const accessorKey = (
                        cell.column.columnDef as unknown as Record<string, unknown>
                      ).accessorKey as string | undefined;

                      if (!accessorKey) {
                        return <TableCell key={cell.id}>{rendered}</TableCell>;
                      }

                      const value = (row.original as Record<string, unknown>)[accessorKey];
                      return <TableCell key={cell.id}>{formatCellValue(value)}</TableCell>;
                    })}
                  </TableRow>
                  {expandedContent ? (
                    <TableRow className="bg-muted/30 hover:bg-muted/30">
                      <TableCell colSpan={columns.length} className="p-4">
                        {expandedContent}
                      </TableCell>
                    </TableRow>
                  ) : null}
                </React.Fragment>
              );
            })
          ) : (
            <TableRow>
              <TableCell
                colSpan={columns.length}
                className="h-24 text-center text-muted-foreground"
              >
                {emptyText}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
