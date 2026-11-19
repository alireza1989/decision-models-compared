"""Builds the fresh set: 296 messages written for this post on November 18, 2026.

Labels follow data/fresh/LABEL_RULES.md. Run once; the output order is shuffled with a fixed seed
so categories are mixed when someone labels them.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
OOS = "out_of_scope"

IN_MESSY = {
    "account_blocked": [
        "hey so I tried to log in this morning and it says my account is restricted?? what happened",
        "Why is there a hold on my checking account? I deposited a check on Monday and now I can't touch any of it.",
        "my savings account got blocked out of nowhere, can someone tell me why",
        "I'm traveling for work and suddenly my account shows as frozen. I didn't do that. What's going on with it?",
        "got a notice that my account is on hold pending review. what does that mean and why",
        "why cant i use my bank account, it keeps saying blocked when i try to pay rent",
    ],
    "balance": [
        "how much money is in my checking right now",
        "Before I go grocery shopping can you tell me what I've got in my savings account?",
        "balance on acct ending 2281 pls",
        "i need to know if i have enough for rent, whats the current balance in my main account",
        "Can you check how much is sitting in my joint account with my wife?",
        "what's left in my account after yesterday's paycheck cleared",
    ],
    "bill_balance": [
        "how much do i still owe on my gas bill this month",
        "What's the total I owe on my internet bill? Want to double check before I pay it.",
        "remind me what the water bill came to",
        "can you tell me the amount owed on my phone bill",
        "how big is my electricity bill this time, the heat was on all month",
        "what do I owe for the cable bill",
    ],
    "bill_due": [
        "when's my phone bill due",
        "I always forget, what day is the electric bill due this month?",
        "is my water bill due before or after the 15th",
        "need the due date for my car insurance bill",
        "When do I have to pay the internet bill by?",
        "what's the deadline on my gas bill, don't want a late fee again",
    ],
    "freeze_account": [
        "I think someone has my login details. lock my checking account immediately please",
        "Please freeze my savings account right now, I left my debit card at a restaurant.",
        "freeze my account asap",
        "Can you put a lock on my bank account until I get back from vacation?",
        "my phone got stolen with my banking app on it, can you block access to my account now",
        "stop all activity on my checking account right away, something is wrong",
    ],
    "interest_rate": [
        "what interest am I earning on my savings",
        "What's the current rate on my high yield savings account?",
        "is the interest rate on my checking still 0.5 percent",
        "how much interest does my money market account pay",
        "tell me the APY on my savings",
        "did the rate on my CD account change this month",
    ],
    "min_payment": [
        "whats the minimum i have to pay on my electric bill",
        "What's the smallest payment I can make on my phone bill this month without a penalty?",
        "minimum due on my water bill?",
        "how little can I pay on the cable bill and still be ok",
        "Can you tell me the minimum payment for my internet bill",
        "i'm short this month, what's the lowest amount i can pay on the gas bill",
    ],
    "order_checks": [
        "I need a new checkbook, can you send one",
        "Please order me more checks, I'm down to my last two.",
        "can i get a box of checks mailed to my house",
        "order checks for my business checking account",
        "How do I get new checks? I just want the same design as before.",
        "running out of checks, send more",
    ],
    "pay_bill": [
        "pay my electric bill from checking",
        "Can you pay the water bill today so it's not late?",
        "use my savings to pay off the phone bill",
        "I'd like to pay my internet bill now, the full amount",
        "please take care of the gas bill payment",
        "send the payment for my cable bill this afternoon",
    ],
    "pin_change": [
        "i want to change the pin on my account",
        "Can I set a new PIN for my checking account? I think someone saw me type it.",
        "reset my pin please",
        "need a different pin for my debit card",
        "How do I update my PIN, I keep forgetting the old one",
        "change pin to something new",
    ],
    "report_fraud": [
        "there's a charge on my checking account I definitely didn't make",
        "I want to report a fraudulent transaction of $214 from a store I've never been to.",
        "someone took money out of my account without asking",
        "theres a weird charge from an online shop on my bank statement, i didnt buy anything",
        "Please flag the $39.99 charge from yesterday as fraud",
        "my debit card got used in another country while I was home",
    ],
    "routing": [
        "what's my routing number",
        "My employer needs the routing number for direct deposit, what is it?",
        "routing # for my checking",
        "can you give me the ABA number for my account",
        "What routing number should I give the IRS for my refund?",
        "need my bank's routing number for a form",
    ],
    "spending_history": [
        "how much did I spend on restaurants last month",
        "Can you add up what I've spent at Amazon since January?",
        "what did i spend on gas this year",
        "I'm trying to budget. How much have I spent on groceries in the past three months?",
        "total spent on coffee shops in october?",
        "how much money went to uber this month",
    ],
    "transactions": [
        "show me my last few transactions",
        "Can you list everything that came out of my checking this week?",
        "what are my most recent charges",
        "I'd like to see the last 10 transactions on my savings account.",
        "list recent activity on my account please",
        "what went in and out of my account yesterday",
    ],
    "transfer": [
        "move $200 from checking to savings",
        "Can you transfer five hundred dollars from my savings into my checking account tonight?",
        "put 50 bucks into my savings",
        "I want to shift some money between my two accounts, $1,000 from savings to checking",
        "transfer my paycheck amount over to the joint account",
        "send $75 from my checking to my savings please",
    ],
}

IN_CARD = {
    "transactions": [
        "what were the last five charges on my visa",
        "Can you list the recent purchases on my credit card?",
        "show me everything I charged to my mastercard this week",
        "what are the latest transactions on my amex",
        "list my credit card activity from the past few days",
        "I need to see recent charges on my card ending 4417",
        "what did i put on my credit card yesterday",
        "Show the most recent transactions on my discover card.",
        "can you pull up the newest charges on my rewards card",
    ],
    "report_fraud": [
        "there's a charge on my credit card I didn't make",
        "I need to report fraud on my visa, someone bought a TV with it",
        "someone used my mastercard number online without permission",
        "Please report the $89 charge on my credit card as fraud, I've never heard of that merchant.",
        "my amex has a charge from a hotel I never stayed at",
        "fraudulent purchases on my credit card, need to report them",
        "I see three charges on my card from a gas station two states away",
        "report a fake charge on my capital one card",
        "Someone is making charges on my credit card. I still have the card with me.",
    ],
    "bill_balance": [
        "how much do i owe on my credit card",
        "What's my credit card bill this month?",
        "how much is my visa bill",
        "what's the statement balance I owe on my amex",
        "total due on my mastercard bill?",
        "Can you tell me how much I owe on my store credit card?",
        "what does my credit card bill come to",
    ],
    "bill_due": [
        "when is my credit card payment due",
        "What's the due date on my visa bill?",
        "when do i have to pay my amex by",
        "is my mastercard payment due this week",
        "when's the next payment due on my credit card",
        "I need the due date for my discover bill",
        "What day is my credit card bill due this month?",
    ],
    "min_payment": [
        "what's the minimum payment on my credit card",
        "How much is the minimum due on my visa this month?",
        "smallest amount i can pay on my amex",
        "min payment for my mastercard?",
        "what's the lowest I can pay on my credit card bill without a late fee",
        "Tell me the minimum payment on my store card.",
        "how much is the minimum on my discover bill",
    ],
    "pay_bill": [
        "pay my credit card bill from checking",
        "Please pay off my visa balance in full today.",
        "make a payment on my amex",
        "use my savings to pay the mastercard bill",
        "I want to pay $300 toward my credit card bill",
        "can you pay the minimum on my credit card",
    ],
}

NEAR_CARD = {
    "apr": [
        "what's the APR on my credit card",
        "is my visa interest rate going up next month",
        "What interest rate am I paying on my credit card balance?",
        "how much interest does my amex charge",
        "whats the purchase apr on my mastercard",
        "Can you tell me the cash advance rate on my card?",
        "did my credit card apr change",
        "what's the interest rate on my store credit card",
    ],
    "limit": [
        "what's my credit limit",
        "How much credit do I have available on my visa?",
        "whats the spending limit on my amex",
        "how high is the limit on my mastercard",
        "Can you tell me my total credit line on my card?",
        "how much more can i charge before i hit my limit",
        "what's the max I can put on my credit card",
        "is my credit limit still $5,000",
    ],
    "limit_increase": [
        "can you raise my credit limit",
        "I'd like a higher limit on my visa please.",
        "request a credit line increase",
        "how do I get my amex limit bumped up",
        "increase the limit on my credit card to 10k",
        "Am I eligible for a credit limit increase?",
        "please up my mastercard limit before my trip",
    ],
    "rewards": [
        "how many reward points do I have",
        "What can I redeem my credit card points for?",
        "check my cash back balance on my visa",
        "how many miles have i earned on my travel card",
        "Do my amex points expire?",
        "transfer my credit card points to an airline",
        "how much cash back did i earn this month",
        "can i use my rewards to pay for a hotel",
    ],
    "replacement": [
        "I lost my credit card, can I get a new one",
        "My visa is cracked and won't swipe. Can you send a replacement?",
        "send me a new credit card, mine expired",
        "my credit card snapped in half",
        "I need a replacement amex, I left mine in a taxi",
        "my mastercard chip stopped working",
        "how long does it take to get a replacement credit card",
        "I think I lost my credit card at the airport",
    ],
    "declined": [
        "why did my credit card get declined at the gas station",
        "My visa keeps getting declined online. What's wrong with it?",
        "card declined at dinner, embarrassing, why",
        "my amex was rejected at the store even though I paid it off",
        "why won't my credit card work",
        "my mastercard got denied twice today",
        "Is there a problem with my credit card? It was declined at the pharmacy.",
        "why is my credit card being declined when I have plenty of credit left",
    ],
    "application": [
        "I want to apply for a credit card",
        "Can I get a second credit card with you guys?",
        "what credit cards do you offer",
        "how do i sign up for your travel rewards card",
        "check the status of my credit card application",
        "I'd like to upgrade to a premium credit card.",
        "can my daughter get her own credit card on my account",
        "Am I approved for the cash back card yet?",
    ],
    "activation_expiry_fee": [
        "activate my new credit card",
        "How do I activate the visa that came in the mail?",
        "my credit card needs activating",
        "when does my credit card expire",
        "What's the expiration date on my amex?",
        "is my mastercard about to expire",
        "what's the annual fee on my credit card",
        "Can you waive the annual fee on my visa this year?",
        "do i pay a yearly fee for my amex",
        "why was I charged an annual fee on my credit card",
        "how much is the annual fee for the travel card",
        "will the annual fee on my card go up",
    ],
    "other_card": [
        "can I do a balance transfer to my credit card",
        "what's the balance transfer fee on my visa",
        "can I add my credit card to apple pay",
        "close my credit card account",
        "change the due date on my credit card",
        "is there a foreign transaction fee on my visa",
        "can you lower the interest on my credit card",
        "my credit card has a hold on it, why?",
    ],
}

NEAR_BANK = {
    "open_account": [
        "I want to open a savings account",
        "How do I open a checking account for my son?",
        "can i open a joint account online",
        "what do i need to open a business account",
        "Can I open a CD with you?",
        "sign me up for a new checking account",
    ],
    "close_account": [
        "close my savings account",
        "I'd like to close my checking account and move everything elsewhere.",
        "how do i shut down my account",
        "cancel my bank account please",
        "What happens to my money if I close my account?",
        "close the joint account, we're separating",
    ],
    "loans": [
        "what's the rate on a car loan",
        "Can I apply for a personal loan?",
        "how much is left on my mortgage",
        "do you offer home equity loans",
        "I want to refinance my house",
        "how do I apply for a student loan",
        "can I get pre-approved for a mortgage",
        "what credit score do I need for a loan",
    ],
    "international": [
        "what's the exchange rate for euros today",
        "I need to send money to my mom in India",
        "can I order foreign currency before my trip",
        "how much does an international wire cost",
        "wire $2,000 to an account in Mexico",
        "Do you charge fees for using my debit card abroad?",
    ],
    "branch_atm": [
        "where's the closest ATM",
        "What time does the branch on Main Street close?",
        "is there a branch near the airport",
        "are you open on saturdays",
        "find me an atm that doesn't charge fees",
        "can I deposit cash at any ATM",
    ],
    "contact_details": [
        "I moved, can you update my address",
        "change the phone number on my account",
        "How do I update my email for account alerts?",
        "need to change my mailing address before my statements go out",
        "add my new last name to my account, I just got married",
        "update my contact info please",
    ],
    "direct_deposit": [
        "how do I set up direct deposit",
        "Can you send me a direct deposit form for my new job?",
        "I want my paycheck deposited straight into savings, how do I set that up",
        "switch my direct deposit to my other account",
        "how long does it take to set up direct deposit",
        "can i split my direct deposit between two accounts",
    ],
    "overdraft": [
        "turn off overdraft protection",
        "What's your overdraft fee?",
        "can you link my savings for overdraft protection",
        "how does overdraft coverage work",
        "opt me out of overdraft",
    ],
    "statements_tax": [
        "can you mail me a paper statement",
        "where do I find my 1099 for interest",
        "I need a copy of last month's statement",
        "send me my tax forms",
        "How do I go paperless for statements?",
    ],
    "pay_another_person": [
        "send $50 to my friend Jake",
        "Can you transfer $300 to my sister's account?",
        "zelle my roommate $40",
        "move money to my brother's checking account",
        "pay back my coworker $20 from my account",
        "send money to someone at another bank",
    ],
}

CHECKING = {"type": "checking", "name": "Everyday Checking ending 2281", "card": "debit card"}
SAVINGS = {"type": "savings", "name": "High Yield Savings ending 9034"}
CARD = {"type": "credit card", "name": "Visa Platinum credit card ending 4417"}
# (message, first account, label with first account, label with the credit card)
CONTEXT_PAIRS = [
    ("What's my interest rate?", CHECKING, "interest_rate", OOS),
    ("Please lock it right now, I think someone has my details.", SAVINGS, "freeze_account", OOS),
    ("I want to change the PIN.", CHECKING, "pin_change", OOS),
    ("Why is there a hold on it?", CHECKING, "account_blocked", OOS),
    ("What's the rate on this account?", SAVINGS, "interest_rate", OOS),
    ("Freeze it please.", SAVINGS, "freeze_account", OOS),
    ("Is this account blocked? Nothing is going through.", CHECKING, "account_blocked", OOS),
    ("List my last five purchases.", CHECKING, "transactions", "transactions"),
    ("How much do I owe?", {"type": "bill", "name": "Electricity bill, City Power"}, "bill_balance", "bill_balance"),
    ("Someone made a charge on this I didn't authorize.", CHECKING, "report_fraud", "report_fraud"),
    ("When is the payment due?", {"type": "bill", "name": "Phone bill, Northwind Mobile"}, "bill_due", "bill_due"),
    ("What's the minimum I need to pay?", {"type": "bill", "name": "Water bill, City Utilities"}, "min_payment", "min_payment"),
    ("Pay it in full today.", {"type": "bill", "name": "Internet bill, Fibrelink"}, "pay_bill", "pay_bill"),
]


def main() -> None:
    items = []
    for label, texts in IN_MESSY.items():
        items += [{"category": "in_messy", "subcategory": label, "state": t, "proposed_label": label} for t in texts]
    for label, texts in IN_CARD.items():
        items += [{"category": "in_card", "subcategory": label, "state": t, "proposed_label": label} for t in texts]
    for sub, texts in NEAR_CARD.items():
        items += [{"category": "near_card", "subcategory": sub, "state": t, "proposed_label": OOS} for t in texts]
    for sub, texts in NEAR_BANK.items():
        items += [{"category": "near_bank", "subcategory": sub, "state": t, "proposed_label": OOS} for t in texts]
    for n, (msg, acct, lab_acct, lab_card) in enumerate(CONTEXT_PAIRS):
        kind = "flip" if lab_acct != lab_card else "control"
        items.append({"category": "context", "subcategory": f"pair{n:02d}_{kind}", "pair": n,
                      "state": {"customer_message": msg, "account": acct}, "proposed_label": lab_acct})
        items.append({"category": "context", "subcategory": f"pair{n:02d}_{kind}", "pair": n,
                      "state": {"customer_message": msg, "account": CARD}, "proposed_label": lab_card})
    texts = [json.dumps(i["state"], sort_keys=True) for i in items]
    assert len(texts) == len(set(texts)), "duplicate message"
    random.Random(1118).shuffle(items)
    for n, item in enumerate(items, 1):
        item["id"] = f"fresh-{n:03d}"
        item["kind"] = "in" if item["proposed_label"] != OOS else "near"
    with open(HERE / "fresh_set.jsonl", "w") as f:
        for item in items:
            f.write(json.dumps({"id": item.pop("id"), **item}) + "\n")
    from collections import Counter
    print(len(items), "messages")
    print(Counter(i["category"] for i in items))
    print(Counter(i["kind"] for i in items))


if __name__ == "__main__":
    main()
