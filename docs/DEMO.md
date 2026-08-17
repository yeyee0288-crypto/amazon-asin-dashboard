# Demo Workflow

This demo uses fake ASINs and fake SKUs. It shows the kind of workflow ASIN Watchtower is designed to support.

## Scenario

You manage a small Amazon catalog and want to check whether today's listings still match your expected price and sellability status.

Before opening Amazon pages one by one, you prepare a simple batch:

| ASIN or URL | Store-link name | ERP SKU | Expected price |
| --- | --- | --- | --- |
| `B000000001` | `Demo-Store-A` | `T-DEMO-001-BK` | `99.99` |
| `https://www.amazon.com/dp/B000000002` | `Demo-Store-A` | `T-DEMO-002-WH` | `89.99` |
| `B000000003` | `Demo-Store-B` | `T-DEMO-003-GY` | `129.99` |

You can start from [`examples/sample-asins.csv`](../examples/sample-asins.csv), replace the fake rows with your own local data, save it as `.xlsx`, and import it from the dashboard.

## What The Dashboard Helps Review

After a batch check, the dashboard can help separate rows into operational buckets:

| Result type | Example meaning | Operator action |
| --- | --- | --- |
| Success | The listing has a usable current price. | No urgent action unless price changed. |
| Price different | Current price differs from expected price or previous run. | Review pricing rule or listing setup. |
| Out of stock | Target ASIN is unavailable or redirects to another ASIN. | Check listing variation, replenishment, or offer status. |
| Missing offer | Amazon has no usable featured offer or price. | Check offer health and seller availability. |
| ERP risk | Optional ERP stock context shows shortage or mismatch. | Coordinate replenishment or listing suppression. |

## Example Review Flow

1. Import the batch input file.
2. Click start check.
3. Use status filters to review unavailable or price-different ASINs first.
4. Open changed rows to inspect current price, previous result, seller, and title context.
5. Export Excel for follow-up or team handoff.

## Example Output Interpretation

| ASIN | Expected price | Current price | Status | Change |
| --- | --- | --- | --- | --- |
| `B000000001` | `99.99` | `94.99` | Success | Price decreased |
| `B000000002` | `89.99` | `-` | Out of stock | Needs listing review |
| `B000000003` | `129.99` | `139.99` | Price different | Price increased |

## Privacy Reminder

Do not commit real ASIN batches, ERP SKUs, inventory exports, credentials, cookies, debug HTML, or screenshots containing private business data.

When sharing a bug report, reduce it to fake data or a minimal public-safe example.
