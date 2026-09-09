# Feature / hazard result 74

Status: **RESEARCH ONLY — no alpha, no strategy or runtime change.**

## Frozen causal construction

Inputs are the completed universe71 normalized identity database and
`universe.json`: fact frontier **2,194,123**, cutoff
`2026-09-09T04:55:14.116134Z`.  Sep7 is the exploration day and Sep8 is the
unchanged holdout.  This work did not read later facts for either date and did
not write to the production database.

For each universe71 original `(token, exact_pool)` anchor, the feature time is
the first three causal normalized frames: first anchor; first same-pool frame
whose `observed_at` is after the prior frame's `recorded_at`; then the same rule
again for frame three.  All three already passed exact identity, positive price,
liquidity >=1000, and `observed <= ingested <= recorded` validation.  Provider
must be unchanged across the three frames.  The actual record-to-record gaps
are retained in the acceleration calculation; no spacing threshold was mined.

Every 60-minute label begins strictly **after frame three's recorded
availability**.  It is a same-pool sampled proxy, costed by 4% on the
hypothetical buy and 4% on the hypothetical sell.  `tail100` means a future
sampled maximum reached +100%; `loss50` means a future sample reached -50%.
No universe71 anchor/second-frame outcome was reused.  No post-third future
frame is `UNKNOWN`, rather than a loss, writeoff, or zero.

The fixed Sep7 medians, applied unchanged on Sep8, split these descriptive
features one at a time: displacement per mean reported 5m volume; reported
activity efficiency (displacement divided by volume/liquidity); volume/liquidity;
third-frame buy-count imbalance; frame-one-to-three liquidity growth; minimum
second/third liquidity retention; path efficiency
`abs(p3-p1)/(abs(p2-p1)+abs(p3-p2))`; and second-to-third price-rate
acceleration less first-to-second price-rate acceleration.  Reported 5m volume
is an overlapping provider aggregate, so it is a **reported-notional proxy**,
never swap-level notional or price impact.  A zero denominator makes only that
ratio diagnostic unavailable; it does not turn a raw zero into missing data.

## Coverage and full-denominator result

| Three-frame-complete date | Episodes | Future observed | Future UNKNOWN | 60m endpoint observed | +100% tail / all | >=50% loss / all |
|---|---:|---:|---:|---:|---:|---:|
| Sep7 exploration | 2,468 | 1,281 (51.9%) | 1,187 (48.1%) | 45 (1.8%) | 53 (2.15%) | 111 (4.50%) |
| Sep8 holdout | 2,885 | 1,622 (56.2%) | 1,263 (43.8%) | 75 (2.6%) | 43 (1.49%) | 114 (3.95%) |

The future-observed-only rates are descriptive and are not used as the decision
denominator: tail/loss are 4.14%/8.67% on Sep7 and 2.65%/7.03% on Sep8.  Low
endpoint coverage and source-dependent missing paths prevent interpreting a
sampled maximum as executable profitability.

Not every mathematically derived diagnostic is defined on every otherwise
complete three-frame episode: all eight diagnostics are available for 1,230
Sep7 and 1,068 Sep8 episodes; path efficiency is defined for 1,285/1,245; and
buy-count imbalance for 1,985/2,136.  Each feature-bin row below uses its own
available full denominator and retains its own future `UNKNOWN` count.

## Fixed-median checks

The most apparent recurring split is also adverse: the high
volume/liquidity half has more right-tail paths **and** substantially more
>=50% loss hazard.

| Date | Volume/liquidity bin | n | Future coverage | +100% tail / all | >=50% loss / all |
|---|---|---:|---:|---:|---:|
| Sep7 | low | 1,234 | 49.4% | 0.08% | 0.32% |
| Sep7 | high/equal | 1,234 | 54.5% | 4.21% | 8.67% |
| Sep8 | low | 1,838 | 55.2% | 0.33% | 0.60% |
| Sep8 | high/equal | 1,047 | 58.1% | 3.53% | 9.84% |

Other broad bins do not repair this tradeoff.  In both days, low displacement/
reported-notional, low liquidity growth or retention, and low acceleration
show higher tail and higher loss rates; the corresponding high/equal bins show
lower rates for both outcomes.  The new path-efficiency split also lowers both
tail/loss from 4.68%/9.36% to 3.71%/7.52% on Sep7 and from 4.41%/11.89% to
2.75%/7.96% on Sep8; it is not a useful tail discriminator.  High third-frame
buy-count imbalance lowers both tail and loss versus its low bin (Sep7
1.42%/2.74% versus 3.99%/8.74%; Sep8 1.23%/2.15% versus 3.01%/9.99%).  These
are hazard/coverage descriptions, not a safe gate or a return estimate.  No
threshold grid, multifeature conjunction, model, or account registration was
run.

## Chain and provider separation

Mixing providers would conceal major coverage differences.  For example,
geckoterminal BSC has 55.4%/52.8% future coverage on Sep7/Sep8, while
dexscreener Robinhood has 97.8% on both dates; geckoterminal Solana coverage is
26.5% on Sep7 and 0 of 49 feature-complete Sep8 paths.  Tail and loss rates are
therefore retained separately by `(date, chain, provider)` in the research
artifact and are not pooled into a chain or launchpad conclusion.

## Raw missing-versus-zero audit

The script audited **every** three-frame-complete episode: 5,353 episodes and
16,059 distinct frame IDs.  It fetched exactly those production
`token_snapshots` raw JSON records in 33 read-only ID chunks of at most 500,
each bounded by the frozen frontier.  It did not scan the production table.

Across this complete diagnostic denominator, `pair.volume.m5` was 13,528
nonzero and 2,531 zero; `pair.txns.m5.buys` was 13,109 nonzero and 2,950 zero;
and `pair.txns.m5.sells` was 6,773 nonzero and 9,286 zero.  There were no
missing or invalid values for these three raw paths among the audited IDs.
Thus a raw zero is an observed zero here, rather than missing data.  If any
future frozen rerun finds a missing/invalid raw field, it removes that frame's
raw-dependent diagnostics (notional, efficiency, volume/liquidity, and
buy-count imbalance) from their diagnostic denominator; it never normalizes
the absence to zero.  This audit does not authenticate aggregate counts as
individual trades or dollar flow.

Native launchpad state and quote-asset semantics remain `UNKNOWN` or ambiguous
for much of universe71.  They were not inferred from a provider/dex label, so
this result supplies no launchpad-specific, native-state, actual-notional, or
executable-liquidity claim.

## Disposition

There is no stable, adequately covered feature pattern that raises rare-tail
incidence without at least comparable or worse observed loss hazard.  Keep the
result as a bounded failure-learning/hazard artifact.  Do not promote any
feature to Paper, change a score, or call the sampled tail proxy alpha.

Artifacts: `scripts/research_features74.py` and
`data/research/features74/result.json`.
