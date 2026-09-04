"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import {
  type ColumnDef,
  type ColumnFiltersState,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import {
  ArrowUpRightIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
  ChevronsUpDownIcon,
  ReceiptTextIcon,
} from "lucide-react";

import type { Payment } from "@/lib/api";
import { formatDateTime, formatMoney, paymentStatusVariant, shortId } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const STATUS_OPTIONS = ["ALL", "COMPLETED", "PENDING", "CREATED", "FAILED", "CANCELLED"] as const;

type StatusFilter = (typeof STATUS_OPTIONS)[number];

const PAGE_SIZE_OPTIONS = [5, 10, 25, 50] as const;

function paymentType(payment: Payment) {
  return payment.provider_payment_link_id ? "Payment Link" : "PaymentIntent";
}

/**
 * Paginated data table of Voic payments.
 *
 * Built on TanStack Table (shadcn data-table pattern): sortable columns,
 * status filter, search, page-size selector, and page navigation. Receives
 * server-fetched payments plus a price -> product label map so each row
 * shows the product name alongside its Stripe price ID.
 */
export function PaymentsTable({
  payments,
  priceLabels,
  compact = false,
}: {
  payments: Payment[];
  priceLabels: Record<string, { name: string; productId: string | null }>;
  compact?: boolean;
}) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [query, setQuery] = useState("");

  const columns = useMemo<ColumnDef<Payment>[]>(() => {
    return [
      {
        accessorKey: "amount",
        header: "Amount",
        cell: ({ row }) => (
          <span className="font-mono font-semibold tabular-nums">
            {formatMoney(row.original.amount, row.original.currency)}
          </span>
        ),
      },
      {
        id: "product",
        accessorFn: (payment) => priceLabels[payment.provider_price_id]?.name ?? "Unknown product",
        header: "Product",
        cell: ({ row }) => (
          <div className="flex max-w-55 flex-col">
            <span className="truncate font-medium">{priceLabels[row.original.provider_price_id]?.name ?? "Unknown product"}</span>
            <span
              className="truncate font-mono text-xs text-muted-foreground"
              title={row.original.provider_price_id}
            >
              {row.original.provider_price_id}
            </span>
          </div>
        ),
      },
      {
        id: "type",
        accessorFn: (payment) => paymentType(payment),
        header: "Type",
        cell: ({ row }) => <span className="text-muted-foreground">{paymentType(row.original)}</span>,
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => (
          <Badge variant={paymentStatusVariant(row.original.status)}>{row.original.status}</Badge>
        ),
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: ({ row }) => (
          <span className="text-muted-foreground">{formatDateTime(row.original.created_at)}</span>
        ),
      },
      {
        id: "link",
        header: () => <span className="sr-only">Link</span>,
        enableSorting: false,
        cell: ({ row }) => (
          <div className="text-right">
            {row.original.url ? (
              <Button
                variant="link"
                size="sm"
                nativeButton={false}
                render={
                  <Link href={row.original.url ?? ""} target="_blank" rel="noreferrer">
                    Open
                    <ArrowUpRightIcon data-icon="inline-end" />
                  </Link>
                }
              />
            ) : (
              <span className="font-mono text-xs text-muted-foreground" title={row.original.id}>
                {shortId(row.original.id)}
              </span>
            )}
          </div>
        ),
      },
    ];
  }, [priceLabels]);

  const table = useReactTable({
    data: payments,
    columns,
    state: {
      sorting,
      columnFilters,
      globalFilter: query,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    globalFilterFn: (row, _columnId, filterValue) => {
      const needle = String(filterValue ?? "").trim().toLowerCase();
      if (!needle) return true;
      const payment = row.original;
      const label = (priceLabels[payment.provider_price_id]?.name ?? "").toLowerCase();
      return (
        payment.id.toLowerCase().includes(needle) ||
        payment.provider_price_id.toLowerCase().includes(needle) ||
        label.includes(needle) ||
        (payment.provider_payment_id ?? "").toLowerCase().includes(needle)
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const statusColumn = table.getColumn("status");
  const filteredCount = table.getFilteredRowModel().rows.length;

  if (payments.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <ReceiptTextIcon />
          </EmptyMedia>
          <EmptyTitle>No payments yet</EmptyTitle>
          <EmptyDescription>
            Payments created from a Stripe product will appear here with their status.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {!compact ? (
        <div className="grid gap-3 sm:grid-cols-[200px_1fr]">
          <Field>
            <FieldLabel htmlFor="payment-status">Status</FieldLabel>
            <Select
              value={status}
              onValueChange={(value) => {
                const next = value as StatusFilter;
                setStatus(next);
                statusColumn?.setFilterValue(next === "ALL" ? undefined : next);
              }}
            >
              <SelectTrigger id="payment-status" className="w-full">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectLabel>Status</SelectLabel>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option === "ALL" ? "All statuses" : option}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
          </Field>
          <Field>
            <FieldLabel htmlFor="payment-search">Search</FieldLabel>
            <Input
              id="payment-search"
              placeholder="Search product, price, or payment ID"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </Field>
        </div>
      ) : null}
      {filteredCount === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>No matching payments</EmptyTitle>
            <EmptyDescription>Adjust the status filter or search term.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <>
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => {
                    if (header.column.id === "link") {
                      return <TableHead key={header.id} className="text-right" />;
                    }
                    return (
                      <TableHead key={header.id}>
                        {header.isPlaceholder ? null : header.column.getCanSort() ? (
                          <button
                            type="button"
                            className="flex items-center gap-1.5"
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {header.column.getIsSorted() === "asc" ? (
                              <ChevronDownIcon className="rotate-180" />
                            ) : header.column.getIsSorted() === "desc" ? (
                              <ChevronDownIcon />
                            ) : (
                              <ChevronsUpDownIcon className="opacity-50" />
                            )}
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </TableHead>
                    );
                  })}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              {filteredCount} {filteredCount === 1 ? "payment" : "payments"}
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Select
                value={String(table.getState().pagination.pageSize)}
                onValueChange={(value) => table.setPageSize(Number(value))}
              >
                <SelectTrigger className="w-[110px]" aria-label="Rows per page">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZE_OPTIONS.map((size) => (
                    <SelectItem key={size} value={String(size)}>
                      {size} / page
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="font-mono text-sm tabular-nums text-muted-foreground">
                Page {table.getState().pagination.pageIndex + 1} of {Math.max(1, table.getPageCount())}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => table.setPageIndex(0)}
                  disabled={!table.getCanPreviousPage()}
                >
                  <ChevronsLeftIcon />
                  <span className="sr-only">First page</span>
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => table.previousPage()}
                  disabled={!table.getCanPreviousPage()}
                >
                  <ChevronLeftIcon />
                  <span className="sr-only">Previous page</span>
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => table.nextPage()}
                  disabled={!table.getCanNextPage()}
                >
                  <ChevronRightIcon />
                  <span className="sr-only">Next page</span>
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => table.setPageIndex(table.getPageCount() - 1)}
                  disabled={!table.getCanNextPage()}
                >
                  <ChevronsRightIcon />
                  <span className="sr-only">Last page</span>
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
