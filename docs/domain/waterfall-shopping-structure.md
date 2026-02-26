# DOMAIN KNOWLEDGE: Google Ads Waterfall Shopping Structure & Optimization Logic

## 1. Core Purpose of this Document

This document defines the underlying logic of the "Waterfall" (or Priority-Tiered) Google Shopping structure. As the AI engine powering the Revenue Leakage and Tier Routing dashboard, you must understand how traffic flows through this structure to make accurate recommendations for `custom_label_0` (product group) search terms.

**CRITICAL PARADOX (READ CAREFULLY):** You must understand the inverse relationship between the **Target ROAS Setting** (the constraint placed on the algorithm) and the **Actual ROAS Metric** (the resulting performance).

* To bid *aggressively* on high-intent terms, the Target ROAS setting must be **Low**. (Removing the ceiling).
* To bid *conservatively* on low-intent terms, the Target ROAS setting must be **High**. (Choking the algorithm).

## 2. The Funnel Mechanics (How it Works)

The Waterfall structure uses Google's Campaign Priority settings (High, Medium, Low) combined with Negative Keyword sculpting to filter traffic by user intent.

### Tier 1: HIGH Priority (Top of Funnel / Generic)

* **What it catches:** Broad, generic, low-intent searches (e.g., "shoes", "bathroom accessories").
* **Financial Setup (Settings):** Strictly constrained. Uses Manual CPC caps (e.g., $10 max) OR the **Highest Target ROAS** setting in the account. This forces the algorithm to bid very conservatively and not waste money on generic clicks.
* **Performance Expectation (Results):** Lowest Conversion Rate (CVR), **Lowest Actual ROAS**.

### Tier 2: MEDIUM Priority (Middle of Funnel / Brand or Category)

* **What it catches:** Semi-specific searches (e.g., "Nike shoes", "brass toilet paper holder").
* **How it gets here:** These terms are added as *Negative Keywords* in the HIGH campaign.
* **Financial Setup (Settings):** Moderate Target ROAS setting.
* **Performance Expectation (Results):** Moderate CVR, Moderate Actual ROAS.

### Tier 3: LOW Priority (Bottom of Funnel / SKU or High-Intent)

* **What it catches:** Highly specific, bottom-of-funnel searches with immediate purchase intent (e.g., "Avondale Reserve Roll TP Holder Model 123").
* **How it gets here:** These terms are added as *Negative Keywords* in both the HIGH and MEDIUM campaigns.
* **Financial Setup (Settings):** **Lowest Target ROAS** setting. Because the intent is so high, we want the algorithm to bid as aggressively as possible to win the auction. Lowering the target removes the algorithmic bidding ceiling.
* **Performance Expectation (Results):** Highest Conversion Rate (CVR), **Highest Actual ROAS**.

---

## 3. The AI's Job: Recommendation Logic & Categorization

Your objective is to analyze the actual performance metrics (Actual ROAS, CVR, Cost) of search terms and recommend whether they belong in their current tier or need to be moved.

You must classify terms into the following actionable categories:

### A. Misplaced Terms (Intent Mismatch)

**The Problem:** A term's actual performance data does not match the historical expectation of its current tier.

* **Action: "Promote" (Push Down the Funnel):** A term in the HIGH or MEDIUM tier is converting exceptionally well (High Actual ROAS, High CVR).
* *Recommendation:* Add as a negative keyword to its current tier. This forces it into a lower-priority tier (e.g., LOW), where the *Target ROAS setting is lower*, allowing the algorithm to bid much more aggressively and capture maximum volume.


* **Action: "Demote" (Pull Up the Funnel):** A term previously thought to be high-intent in the LOW or MEDIUM tier is suffering from poor Actual ROAS and low CVR, eating up bottom-of-funnel budget.
* *Recommendation:* Remove the negative keyword from the upper tiers to push it back up to HIGH or MEDIUM. There, the *high Target ROAS setting* (or strict CPC cap) will choke the algorithm, forcing it to bid lower and stop wasting money.



### B. Wasted Spend (Revenue Leakage)

**The Problem:** A term is aggressively spending budget but yielding near-zero return, effectively dragging down the performance of the entire `custom_label_0` group.

* **Trigger Metrics:** High Impressions, High Cost, Zero/Negligible Conversions, Extremely Low Actual ROAS.
* **Action: Global Block:** The term is pure garbage and has no relevance to the product.
* *Recommendation:* Add as an account-level negative keyword to completely stop bidding on it.


* **Action: Demote to HIGH:** The term is relevant but low-converting.
* *Recommendation:* Push it to the HIGH tier so it is trapped by the restrictive settings (High tROAS / CPC caps).



### C. Under-Invested (Volume Starvation)

**The Problem:** A highly relevant, high-converting term is stuck in a tier that is artificially restricting its volume.

* **Trigger Metrics:** Exceptionally High Actual ROAS, Low Search Impression Share, Low Cost. (Usually found in HIGH or MEDIUM tiers).
* **The Logic:** The term is converting so well that it is leaving money on the table because the current tier's Target ROAS is too high, preventing aggressive bidding.
* **Action: Route to LOW:** *Recommendation:* Route the term to the LOW tier (Bottom of Funnel). The LOW tier's aggressive (lowest) Target ROAS setting will allow Google to bid whatever it takes to win that highly profitable volume.

---

## 4. Key Directives for Evaluating Metrics

When analyzing the data to generate the UI's `tierFitScores`, `LeakageTermList`, and `RoasBoxPlot`, adhere to these rules:

1. **Evaluate against Tier Medians, not Global Medians:** A ROAS of 2.5 might be considered "Excellent" in the HIGH tier, but "Poor" in the LOW tier. Score terms based on the statistical distribution of the tier they currently reside in.
2. **Watch for Algorithm "Giving Up" (Low Volume + Low CVR):** If a term in a bottom-of-funnel tier suddenly loses volume, look at the recent CVR. If CVR dropped, Smart Bidding is purposely losing the auction to protect ROAS. Do not recommend raising bids; recommend demoting the term to a broader tier.
3. **Prioritize Wasted Spend:** The UI has a "Revenue Leakage" tab. Your highest priority recommendations must identify terms in the MEDIUM and LOW tiers that are spending heavily with low Actual ROAS. Because these tiers have the most aggressive (lowest) Target ROAS settings, bad terms here will rapidly drain the budget.
