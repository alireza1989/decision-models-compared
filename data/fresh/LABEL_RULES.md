# Label rules for the fresh set

Written on November 18, 2026, before any model saw these messages. Every message gets one label:
one of the 15 skills, `out_of_scope`, or `drop` when a careful reader could defend two labels.

## The policy the labels follow

The agent is a banking support agent. It covers **bank accounts and bills**. Each skill does exactly
what its one-line description says, read literally:

| Skill | Does |
|---|---|
| account_blocked | Explain why the user's bank account is blocked or has a hold on it |
| balance | Tell the user the balance of a bank account |
| bill_balance | Tell the user how much they owe on a bill |
| bill_due | Tell the user when a bill is due |
| freeze_account | Freeze or lock the user's bank account right away |
| interest_rate | Tell the user the interest rate on their account |
| min_payment | Tell the user the minimum payment due on a bill |
| order_checks | Order new checks or checkbooks |
| pay_bill | Pay a bill from the user's account |
| pin_change | Change the PIN of a bank account |
| report_fraud | Report a fraudulent charge on a bank account |
| routing | Give the routing number of a bank account |
| spending_history | Summarize how much the user spent on something |
| transactions | List the user's recent transactions |
| transfer | Move money between the user's accounts |

## Rules

1. **Credit card accounts themselves are out of scope.** Questions about a credit card's APR or
   interest, limit, rewards or points, annual fee, activation, expiry, replacement, a lost or damaged
   card, a declined card, or applying for a card are `out_of_scope`.
2. **Banking actions that happen to involve a card stay in scope.** Listing charges on a card is
   `transactions`, reporting a fraudulent card charge is `report_fraud`, and a card bill's amount owed,
   due date, minimum payment or payment are `bill_balance`, `bill_due`, `min_payment` and `pay_bill`.
   This matches how CLINC150 labels the same requests.
3. **A debit card belongs to its bank account.** Changing a debit card's PIN is `pin_change`, and
   freezing or locking a debit card is `freeze_account`.
4. **Read each skill literally.** `transfer` moves money between the user's own accounts, so sending
   money to another person is `out_of_scope`. `account_blocked` explains a block or hold; asking to
   remove one is `out_of_scope`.
5. **Anything else a bank does but no skill covers** (opening or closing an account, loans and
   mortgages, foreign exchange and international wires, branch and ATM locations, statements and tax
   forms, changing an address, setting up direct deposit, overdraft settings) is `out_of_scope`.
6. **Context counts.** When the state includes account details, the label follows them: "what's my
   interest rate" about a checking account is `interest_rate`, about a credit card it is `out_of_scope`.
7. **One request per message.** Messages that ask for two different things were not written into
   this set, because any single label for them would be arbitrary.
8. **When in doubt, drop.** If a message can honestly be read two ways, label it `drop`. Dropped
   messages are removed before any scoring, and the post reports how many there were.

The labels are the author's, checked against these rules. The proposed label written with each
message is kept separate from the labelling sheet, so the labeller doesn't see it, and the two are
compared afterwards.
