"""Print template for Purchase Order."""

from src.printing.escp import ESCPBuilder
from src.models.transaction import PurchaseOrder


def render_purchase_order(po: PurchaseOrder) -> bytes:
    """Render a purchase order for printing on LQ-635C (80-column)."""
    b = ESCPBuilder()
    b.init_chinese()
    b.set_page_length_lines(66)

    # Header
    b.header("進 貨 單")
    b.newline()

    # Order info
    b.row(
        [f"單號：{po.order_no}", f"日期：{po.order_date.strftime('%Y-%m-%d')}"],
        [40, 40],
    )
    supplier_name = po.supplier.name if po.supplier else ""
    b.row(
        [f"供應商：{supplier_name}", f"建立者：{po.creator.display_name if po.creator else ''}"],
        [40, 40],
    )
    b.line("=")

    # Table header
    col_widths = [4, 30, 8, 12, 12, 14]
    col_aligns = ['c', 'l', 'r', 'r', 'r', 'l']
    b.bold_on()
    b.row(["#", "品名", "數量", "單價", "金額", "備註"], col_widths, col_aligns)
    b.bold_off()
    b.line("-")

    # Lines
    for i, line in enumerate(po.lines, 1):
        item_name = line.item.name if line.item else "?"
        b.row(
            [str(i), item_name, str(line.quantity),
             f"{line.unit_price:,.0f}", f"{line.amount:,.0f}",
             line.notes or ""],
            col_widths, col_aligns,
        )

    # Footer
    b.line("-")
    b.row(["", "", "", "合計：", f"${po.total_amount:,.0f}", ""], col_widths, col_aligns)
    b.newline()

    if po.notes:
        b.text(f"備註：{po.notes}").newline()

    b.newline()
    b.row(["驗收人：__________", "主管：__________", ""], [30, 30, 20])
    b.form_feed()

    return b.data
