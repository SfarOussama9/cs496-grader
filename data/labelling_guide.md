# Labelling Guide - Corvina Airways Policy QA (v1)

## What you are labelling

Each item shows **policy section(s)** from the Corvina Airways handbook, a **customer question**, and an **answer**. You decide whether the answer is good enough to send to the customer, **using only the policy text shown**. Do not use your own knowledge of real airlines: Corvina is fictional and its rules deliberately differ from real ones.

You answer three yes/no questions. The final verdict is computed automatically:

> **PASS** only if all three are **yes**. Any **no** means **FAIL**.

## The three criteria

### 1. Correct - does everything the answer states agree with the policy?

- **No** if any number, time limit, fee, percentage, age or weight is wrong, or if a calculation is wrong.
- **No** if the answer applies the wrong rule or reaches the wrong conclusion (for example says "yes" when the policy says "no").
- **No** if the question contains a false assumption and the answer goes along with it (for example: "Since Light includes a checked bag, how heavy can it be?" answered with a weight). A correct answer points out the false assumption.
- Rule of thumb: if the policy says something **different** from the answer, that is a **Correct = no**.

### 2. Complete - does the answer give the customer everything they need to act?

- **No** if it leaves out a condition that changes the outcome (a deadline, an exception, a "only if..."). Example: "Can I change my Flex ticket for free?" -> "Yes." is incomplete, because changes are free only up to 2 hours before departure, and any fare difference still applies.
- **No** if it answers only part of a multi-part question.
- **Yes** if the missing detail would not change what the customer does. Don't fail an answer for leaving out trivia.

### 3. Grounded - is every claim supported by the policy?

- **No** if the answer states a rule, fee, service or number that the policy **does not mention at all** (invented content), even if it sounds plausible or is true for real airlines.
- **No** if the policy does not cover the question and the answer guesses instead of saying so.
- Rule of thumb: if the policy says **nothing** about it and the answer asserts it, that is **Grounded = no**.

## Special cases

| Situation | How to label |
|---|---|
| The policy does not cover the question, and the answer says so clearly | All three **yes** (PASS). |
| The answer suggests contacting Corvina, the airport or an embassy | Allowed. Generic advice like this is **not** an invented claim. |
| Friendly padding ("Great question!", "Have a nice trip!") | **Ignore it.** Judge only the content. Padding is neither good nor bad. |
| Extra correct information from the policy that wasn't asked for | Fine, as long as it is correct. |
| Wrong number AND invented rule in the same answer | Mark **both** criteria no. Label each criterion independently. |
| Question details are incomplete (for example the distance isn't stated) | Judge whether the answer is right for the situation described. If you genuinely cannot decide, **drop** the item. |

## When to drop an item

Drop (key `d`) and write a short reason if:

- the policy itself is ambiguous, so two careful people could reasonably disagree about the right answer;
- the question makes no sense or cannot be judged from the sections shown;
- the item is broken (for example the wrong section is attached).

Don't drop an item just because it is hard. Dropped items are reported, so the reason matters.

## Worked examples (not in the golden set)

**Q:** When does the boarding gate close for a long-haul flight? (S09)

- "40 minutes before departure." -> Correct **yes**, Complete **yes**, Grounded **yes** -> **PASS**
- "30 minutes before departure." -> Correct **no** -> **FAIL**

**Q:** What is the checked baggage allowance on a Classic fare? (S02, S04)

- "One checked bag of up to 27 kg, and you also get free priority boarding." -> Grounded **no** (priority boarding is not a Classic benefit) -> **FAIL**

**Q:** Can I bring my e-scooter? (S03, S04)

- "The policy doesn't cover e-scooters, so I can't confirm. Please check with Corvina." -> **PASS**
- "No, e-scooters are banned on all flights." -> Grounded **no** (a guess) -> **FAIL**

**Q:** Since Classic includes two checked bags, can I bring two 27 kg bags? (S02)

- "Classic includes one checked bag of 27 kg, not two. A second bag costs EUR 35 per flight online or EUR 70 at the airport." -> **PASS**
- "Yes, two bags of 27 kg each." -> Correct **no** (accepts the false assumption) -> **FAIL**

## Process rules

1. **Label independently.** Do not discuss items with the other labellers, and do not look at anyone else's labels, until everyone has finished.
2. **Do not open `data/golden/generation_meta.jsonl`** before labelling is finished. It contains notes on how each answer was built, and seeing it would contaminate your labels.
3. Read the policy section in full for every item. The trap is often one clause.
4. Label in the labelling page (`labelling/label_app.html`, also published as a link). Pick your labeller number (each person a different one), label with `y`/`n` and `Enter`, then click **Send my labels** and **Copy my labels**, and paste the result to the project owner, who imports it with `python -m scripts.import_labels`.
5. Every item is labelled by exactly two people. Agreement is measured with `python -m scripts.agreement <name1> <name2> <name3> <name4>`.
