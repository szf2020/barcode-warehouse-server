"""Print template for Sales Order / Quotation."""

from src.printing.escp import ESCPBuilder
from src.models.transaction import SalesOrder, Quotation


def render_sales_order(so: SalesOrder) -> bytes:
    """Render a sales order for printing (80-column, 2-part copy format)."""
    b = ESCPBuilder()
    b.init_chinese()
    b.set_page_length_lines(66)

    # Header
    b.header("銷 貨 單")
    b.newline()

    # Info
    b.row(
        [f"單號：{so.order_no}", f"日期：{so.order_date.strftime('%Y-%m-%d')}"],
        [40, 40],
    )
    customer_name = so.customer.name if so.customer else ""
    b.row(
        [f"客戶：{customer_name}", ""],
        [40, 40],
    )
    b.line("=")

    # Table
    col_widths = [4, 30, 8, 12, 12, 14]
    col_aligns = ['c', 'l', 'r', 'r', 'r', 'l']
    b.bold_on()
    b.row(["#", "品名", "數量", "單價", "金額", "備註"], col_widths, col_aligns)
    b.bold_off()
    b.line("-")

    for i, line in enumerate(so.lines, 1):
        item_name = line.item.name if line.item else "?"
        b.row(
            [str(i), item_name, str(line.quantity),
             f"{line.unit_price:,.0f}", f"{line.amount:,.0f}",
             line.notes or ""],
            col_widths, col_aligns,
        )

    b.line("-")
    b.row(["", "", "", "合計：", f"${so.total_amount:,.0f}", ""], col_widths, col_aligns)
    b.newline()

    if so.notes:
        b.text(f"備註：{so.notes}").newline()

    b.newline()
    b.row(["客戶簽收：__________", "經辦人：__________", ""], [30, 30, 20])
    b.form_feed()

    return b.data


def render_quotation(qt: Quotation) -> bytes:
    """Render a quotation for printing."""
    b = ESCPBuilder()
    b.init_chinese()
    b.set_page_length_lines(66)

    b.header("報 價 單")
    b.newline()

    b.row(
        [f"單號：{qt.quote_no}", f"日期：{qt.quote_date.strftime('%Y-%m-%d')}"],
        [40, 40],
    )
    customer_name = qt.customer.name if qt.customer else ""
    valid_str = qt.valid_until.strftime('%Y-%m-%d') if qt.valid_until else "無期限"
    b.row(
        [f"客戶：{customer_name}", f"有效期限：{valid_str}"],
        [40, 40],
    )
    b.line("=")

    col_widths = [4, 30, 8, 12, 12, 14]
    col_aligns = ['c', 'l', 'r', 'r', 'r', 'l']
    b.bold_on()
    b.row(["#", "品名", "數量", "單價", "金額", "備註"], col_widths, col_aligns)
    b.bold_off()
    b.line("-")

    for i, line in enumerate(qt.lines, 1):
        item_name = line.item.name if line.item else "?"
        b.row(
            [str(i), item_name, str(line.quantity),
             f"{line.unit_price:,.0f}", f"{line.amount:,.0f}",
             line.notes or ""],
            col_widths, col_aligns,
        )

    b.line("-")
    b.row(["", "", "", "合計：", f"${qt.total_amount:,.0f}", ""], col_widths, col_aligns)
    b.newline()

    if qt.notes:
        b.text(f"備註：{qt.notes}").newline()

    b.newline()
    b.text("以上報價如蒙惠顧，敬請於有效期限內回覆。").newline()
    b.newline()
    b.row(["業務代表：__________", "主管：__________", ""], [30, 30, 20])
    b.form_feed()

    return b.data
