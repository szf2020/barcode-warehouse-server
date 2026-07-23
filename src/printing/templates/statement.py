"""Print template for Account Statement (對帳單)."""

from datetime import date
from decimal import Decimal
from typing import List

from src.printing.escp import ESCPBuilder
from src.models.accounting import Receivable, Payable


def render_receivable_statement(
    customer_name: str, items: List[Receivable], as_of: date = None
) -> bytes:
    """Render a receivable statement for a customer (continuous form)."""
    if as_of is None:
        as_of = date.today()

    b = ESCPBuilder()
    b.init_chinese()
    b.condensed_on()  # 132-col mode for more data

    b.header("應 收 帳 款 對 帳 單")
    b.condensed_on()
    b.newline()
    b.text(f"客戶：{customer_name}").newline()
    b.text(f"列印日期：{as_of.strftime('%Y-%m-%d')}").newline()
    b.line("=", 100)

    col_widths = [18, 14, 14, 14, 14, 14, 12]
    col_aligns = ['l', 'l', 'r', 'r', 'r', 'l', 'l']
    b.bold_on()
    b.row(["銷貨單號", "日期", "應收金額", "已收金額", "餘額", "狀態", "到期日"], col_widths, col_aligns)
    b.bold_off()
    b.line("-", 100)

    total_amount = Decimal("0")
    total_paid = Decimal("0")

    for r in items:
        order_no = r.sales_order.order_no if r.sales_order else "-"
        order_date = r.sales_order.order_date.strftime('%Y-%m-%d') if r.sales_order else "-"
        balance = r.amount - r.paid_amount
        total_amount += r.amount
        total_paid += r.paid_amount

        b.row(
            [order_no, order_date, f"{r.amount:,.0f}", f"{r.paid_amount:,.0f}",
             f"{balance:,.0f}", r.status, r.due_date.strftime('%Y-%m-%d') if r.due_date else "-"],
            col_widths, col_aligns,
        )

    b.line("-", 100)
    total_balance = total_amount - total_paid
    b.row(
        ["", "合計", f"{total_amount:,.0f}", f"{total_paid:,.0f}",
         f"{total_balance:,.0f}", "", ""],
        col_widths, col_aligns,
    )
    b.newline()
    b.condensed_off()
    b.form_feed()

    return b.data


def render_payable_statement(
    supplier_name: str, items: List[Payable], as_of: date = None
) -> bytes:
    """Render a payable statement for a supplier."""
    if as_of is None:
        as_of = date.today()

    b = ESCPBuilder()
    b.init_chinese()
    b.condensed_on()

    b.header("應 付 帳 款 對 帳 單")
    b.condensed_on()
    b.newline()
    b.text(f"供應商：{supplier_name}").newline()
    b.text(f"列印日期：{as_of.strftime('%Y-%m-%d')}").newline()
    b.line("=", 100)

    col_widths = [18, 14, 14, 14, 14, 14, 12]
    col_aligns = ['l', 'l', 'r', 'r', 'r', 'l', 'l']
    b.bold_on()
    b.row(["進貨單號", "日期", "應付金額", "已付金額", "餘額", "狀態", "到期日"], col_widths, col_aligns)
    b.bold_off()
    b.line("-", 100)

    total_amount = Decimal("0")
    total_paid = Decimal("0")

    for p in items:
        order_no = p.purchase_order.order_no if p.purchase_order else "-"
        order_date = p.purchase_order.order_date.strftime('%Y-%m-%d') if p.purchase_order else "-"
        balance = p.amount - p.paid_amount
        total_amount += p.amount
        total_paid += p.paid_amount

        b.row(
            [order_no, order_date, f"{p.amount:,.0f}", f"{p.paid_amount:,.0f}",
             f"{balance:,.0f}", p.status, p.due_date.strftime('%Y-%m-%d') if p.due_date else "-"],
            col_widths, col_aligns,
        )

    b.line("-", 100)
    total_balance = total_amount - total_paid
    b.row(
        ["", "合計", f"{total_amount:,.0f}", f"{total_paid:,.0f}",
         f"{total_balance:,.0f}", "", ""],
        col_widths, col_aligns,
    )
    b.newline()
    b.condensed_off()
    b.form_feed()

    return b.data
