"use client";

import { FormEvent, useState } from "react";
import { apiRequest } from "@/lib/api";

type PaymentOrder = {
  order_id: string;
  status: string;
  approval_url: string | null;
  amount: string;
  currency: string;
};

export function PayPalPaymentForm() {
  const [amount, setAmount] = useState("10.00");
  const [order, setOrder] = useState<PaymentOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  async function createOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setOrder(null);
    setIsCreating(true);
    try {
      const createdOrder = await apiRequest<PaymentOrder>("/api/v1/payments/paypal/orders", {
        method: "POST",
        body: JSON.stringify({ amount, currency: "USD" }),
      });
      setOrder(createdOrder);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The payment could not be created.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="payment-test-panel">
      <div>
        <p className="eyebrow">Sandbox payment</p>
        <h2>Create a test payment</h2>
        <p className="integration-description">
          Create an order in USD, approve it in the PayPal Sandbox, and return here to capture it.
        </p>
      </div>
      <form className="form payment-form" onSubmit={createOrder}>
        <div className="field">
          <label htmlFor="payment-amount">Amount (USD)</label>
          <input
            id="payment-amount"
            name="amount"
            inputMode="decimal"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            required
          />
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-primary" type="submit" disabled={isCreating}>
          {isCreating ? "Creating order..." : "Create PayPal order"}
        </button>
      </form>
      {order && (
        <div className="payment-order-result" role="status">
          <span className="status">Order created</span>
          <p className="identity-value">{order.currency} {order.amount}</p>
          {order.approval_url ? (
            <a className="button button-secondary" href={order.approval_url}>
              Approve in PayPal Sandbox
            </a>
          ) : (
            <p className="form-error">PayPal did not return an approval link.</p>
          )}
        </div>
      )}
    </div>
  );
}
