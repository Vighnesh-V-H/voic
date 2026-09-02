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
