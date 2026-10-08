# Worked example: your own invoice

`my_001.png` is a fictional sample invoice made for testing. `my_001.json` is its answer key: the correct values, written independently of any model.

Keys: `invoice_number`, `vendor`, `invoice_date` (YYYY-MM-DD), `currency`, `line_items` (`description`, `quantity`, `unit_price`, `amount`), `subtotal`, `tax`, `total`.

To use it, copy both files into `data/my_invoices/mine/` and run the commands in [Test your own invoices](../../README.md#test-your-own-invoices).
