"""Print template for Repair Order."""

from src.printing.escp import ESCPBuilder
from src.models.repair import RepairOrder


def render_repair_receipt(ro: RepairOrder) -> bytes:
    """Render a repair receipt (收件單) for customer."""
    b = ESCPBuilder()
    b.init_chinese()
    b.set_page_length_lines(66)

    b.header("維 修 收 件 單")
    b.newline()

    b.row([f"單號：{ro.repair_no}", f"收件日：{ro.received_date.strftime('%Y-%m-%d')}"], [40, 40])
    customer_name = ro.customer.name if ro.customer else ""
    b.row([f"客戶：{customer_name}", ""], [40, 40])
    b.line("=")

    b.text(f"送修品名：{ro.item_name}").newline()
    b.text(f"品牌/型號：{ro.brand or ''} {ro.model or ''}").newline()
    b.text(f"序號：{ro.serial_no or '無'}").newline()
    b.text(f"保固到期：{ro.warranty_until.strftime('%Y-%m-%d') if ro.warranty_until else '無保固'}").newline()
    b.newline()
    b.bold_on().text("故障描述：").bold_off().newline()
    b.text(f"  {ro.fault_desc}").newline()
    b.newline()
    b.line("-")
    b.text("※ 維修完成後將以電話通知取件").newline()
    b.text("※ 逾三個月未取件視同放棄").newline()
    b.newline()
    b.row(["客戶簽名：__________", "收件人：__________"], [40, 40])
    b.form_feed()

    return b.data


def render_repair_completion(ro: RepairOrder) -> bytes:
    """Render a repair completion notice (完工通知單)."""
    b = ESCPBuilder()
    b.init_chinese()
    b.set_page_length_lines(66)

    b.header("維 修 完 工 單")
    b.newline()

    b.row([f"單號：{ro.repair_no}", f"完工日：{ro.completed_date.strftime('%Y-%m-%d') if ro.completed_date else ''}"], [40, 40])
    customer_name = ro.customer.name if ro.customer else ""
    b.row([f"客戶：{customer_name}", f"送修品：{ro.item_name}"], [40, 40])
    b.line("=")

    b.bold_on().text("維修內容：").bold_off().newline()
    b.text(f"  {ro.repair_desc or '(無)'}").newline()
    b.newline()

    # Parts
    if ro.parts:
        b.bold_on().text("零件明細：").bold_off().newline()
        col_widths = [4, 30, 8, 12, 12]
        col_aligns = ['c', 'l', 'r', 'r', 'r']
        b.row(["#", "零件", "數量", "單價", "金額"], col_widths, col_aligns)
        b.line("-", 66)
        for i, p in enumerate(ro.parts, 1):
            b.row(
                [str(i), p.part_name, str(p.quantity), f"{p.unit_price:,.0f}", f"{p.amount:,.0f}"],
                col_widths, col_aligns,
            )
        b.newline()

    # Fee summary
    b.line("-")
    b.text(f"  工資：${ro.labor_fee:,.0f}").newline()
    b.text(f"  零件費：${ro.parts_fee:,.0f}").newline()
    b.bold_on().text(f"  合計：${ro.total_fee:,.0f}").bold_off().newline()
    b.newline()

    b.row(["客戶簽收：__________", "技師：__________"], [40, 40])
    b.form_feed()

    return b.data
