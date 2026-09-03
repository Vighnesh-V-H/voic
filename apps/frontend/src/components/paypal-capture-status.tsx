"use client";

import { useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";

type PaymentStatus = {
  order_id: string;
  status: string;
  capture_id: string | null;
  amount: string;
  currency: string;
};

export function PayPalCaptureStatus({ orderId, cancelled = false }: { orderId: string | null; cancelled?: boolean }) {
  const [payment, setPayment] = useState<PaymentStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderId) {
      return;
    }

    let isCurrent = true;
    const action = cancelled ? "cancel" : "capture";
    const actionRequest = apiRequest<PaymentStatus>(
      `/api/v1/payments/paypal/orders/${encodeURIComponent(orderId)}/${action}`,
      { method: "POST" },
    ).catch(() => apiRequest<PaymentStatus>(
      `/api/v1/payments/paypal/orders/${encodeURIComponent(orderId)}`,
    ));
    actionRequest
      .then((result) => {
        if (isCurrent) {
          setPayment(result);
        }
      })
      .catch((requestError) => {
        if (isCurrent) {
          setError(requestError instanceof Error ? requestError.message : "Payment capture failed.");
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [orderId, cancelled]);

  if (!orderId) {
    return <p className="form-error">PayPal did not return an order to capture.</p>;
  }
  if (error) {
    return <p className="form-error" role="alert">{error}</p>;
  }
  if (!payment) {
    return <p className="integration-description">Confirming the PayPal Sandbox payment...</p>;
  }

  return (
    <div className="payment-order-result" role="status">
      <span className={payment.status === "COMPLETED" ? "status" : "status status-disconnected"}>
        {payment.status === "COMPLETED" ? "Payment completed" : `Payment ${payment.status.toLowerCase()}`}
      </span>
      <p className="identity-value">{payment.currency} {payment.amount}</p>
      {payment.capture_id && <p className="integration-description">Capture ID: {payment.capture_id}</p>}
    </div>
  );
}
