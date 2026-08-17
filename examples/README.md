# Examples

This folder contains public-safe example input files.

The sample data uses fake ASINs, fake store-link groups, and fake ERP SKUs. It is only intended to show the expected input shape.

## Input Columns

| Column | Meaning |
| --- | --- |
| ASIN或链接 | Amazon ASIN or product URL. |
| 店铺链接名 | Optional group name used to organize results. |
| ERP SKU | Optional internal SKU used for inventory matching. |
| 预期价 | Optional expected price for price comparison. |

## How To Use

Open `sample-asins.csv` in Excel or another spreadsheet tool, replace the fake rows with your own local data, and save it as `.xlsx` before importing it through the dashboard.

Do not commit real ASIN lists, ERP SKUs, inventory files, accounts, passwords, or exported results.
