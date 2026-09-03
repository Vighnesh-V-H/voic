# Voic Domain

Voic connects a merchant's payment systems to a trusted foundation for payment recovery.

## Language

**User**:
A person who can sign in to Voic. In Phase 1, each user is associated with one merchant.
_Avoid_: Customer, merchant

**Merchant**:
A business using Voic. A merchant owns its provider connections, payment events, and future recovery activity.
_Avoid_: Account, user, workspace

**Provider connection**:
An authorization relationship in which a merchant has granted Voic access to an external payment provider.
_Avoid_: Integration, provider account

**Payment event**:
A provider-originated record that tells Voic a payment-related event occurred.
_Avoid_: Transaction, recovery case

**Connected Stripe account**:
An existing Stripe account that a merchant authorizes Voic to access through Stripe Standard OAuth. It is identified by Stripe's account ID and is not itself a Voic merchant.
_Avoid_: Stripe merchant, provider connection

**Stripe product**:
A catalog item owned and managed in the merchant's Stripe account. Voic reads products and their prices for selection but does not own the catalog.

**Stripe price**:
A Stripe-defined amount and currency associated with a Stripe product. A price is the catalog reference used when Voic creates a payment or Payment Link.

**Payment**:
A Voic-owned attempt to collect money for a merchant, associated with a Stripe PaymentIntent or Payment Link and tracked using Voic's payment status.
_Avoid_: Payment event

**Payment Link**:
A Stripe-hosted checkout URL created by Voic from an existing Stripe price. Voic stores its provider ID and URL but does not construct the URL itself.

**Payment status**:
The Voic-owned lifecycle state of a payment: CREATED, PENDING, COMPLETED, FAILED, or CANCELLED. Verified Stripe webhook events are authoritative for final success and failure states.
