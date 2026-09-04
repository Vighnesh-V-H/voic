"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { ArrowUpRightIcon } from "lucide-react";

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
import { ReceiptTextIcon } from "lucide-react";

const STATUS_OPTIONS = ["ALL", "COMPLETED", "PENDING", "CREATED", "FAILED", "CANCELLED"] as const;

type StatusFilter = (typeof STATUS_OPTIONS)[number];

function paymentType(payment: Payment) {
  return payment.provider_payment_link_id ? "Payment Link" : "PaymentIntent";
}

/**
 * Filterable table of every Voic payment.
 *
 * Receives server-fetched payments plus a price -> product label map so each
 * row shows the product name alongside its Stripe price ID.
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
  const [status, setStatus] = useState<StatusFilter>("ALL");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return payments.filter((payment) => {
      if (status !== "ALL" && payment.status !== status) return false;
      if (!needle) return true;
      const label = priceLabels[payment.provider_price_id]?.name.toLowerCase() ?? "";
      return (
        payment.id.toLowerCase().includes(needle) ||
        payment.provider_price_id.toLowerCase().includes(needle) ||
        label.includes(needle) ||
        (payment.provider_payment_id ?? "").toLowerCase().includes(needle)
      );
    });
  }, [payments, priceLabels, query, status]);

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
            <Select value={status} onValueChange={(value) => setStatus(value as StatusFilter)}>
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
      {filtered.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyTitle>No matching payments</EmptyTitle>
            <EmptyDescription>Adjust the status filter or search term.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Amount</TableHead>
              <TableHead>Product</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Link</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.map((payment) => {
              const product = priceLabels[payment.provider_price_id];
              return (
                <TableRow key={payment.id}>
                  <TableCell className="font-mono font-semibold tabular-nums">
                    {formatMoney(payment.amount, payment.currency)}
                  </TableCell>
                  <TableCell>
                    <div className="flex max-w-55 flex-col">
                      <span className="truncate font-medium">{product?.name ?? "Unknown product"}</span>
                      <span className="truncate font-mono text-xs text-muted-foreground" title={payment.provider_price_id}>
                        {payment.provider_price_id}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{paymentType(payment)}</TableCell>
                  <TableCell>
                    <Badge variant={paymentStatusVariant(payment.status)}>{payment.status}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(payment.created_at)}</TableCell>
                  <TableCell className="text-right">
                    {payment.url ? (
                      <Button
                        variant="link"
                        size="sm"
                        nativeButton={false}
                        render={
                          <Link href={payment.url} target="_blank" rel="noreferrer">
                            Open
                            <ArrowUpRightIcon data-icon="inline-end" />
                          </Link>
                        }
                      />
                    ) : (
                      <span className="font-mono text-xs text-muted-foreground" title={payment.id}>
                        {shortId(payment.id)}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
