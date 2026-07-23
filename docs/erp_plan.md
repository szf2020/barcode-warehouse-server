# 進銷存 ERP 系統實作計畫

## Problem Statement

將現有的倉管條碼系統（barcode-warehouse-server）擴展為完整的進銷存 ERP 系統（家電行場景），涵蓋：客戶/廠商建檔、標準進銷貨單據流程、帳務管理、維修追蹤、條碼掃描出入庫/盤點，並支援 Epson LQ-635C 點陣印表機列印所有單據。

## Requirements

1. 漸進式單體架構，模組化目錄
2. Jinja2 SSR + HTMX 前端
3. 標準單據流程：報價單 → 銷貨單 → 應收帳款；進貨單 → 應付帳款
4. 維修工單管理（送修追蹤、狀態、零件、收費、保固）
5. 條碼掃描擴展：出入庫 + 盤點
6. 客戶/廠商簡單管理（名稱、聯絡人、電話、地址）
7. 所有單據支援 Epson LQ-635C 點陣列印（USB 接 server，ESC/P 指令）
8. 紙張：連續報表紙（複寫）+ A4 單張
9. 多租戶隔離維持
10. 先 SQLite 開發，PostgreSQL 生產

## Background

- 現有架構：FastAPI + SQLAlchemy + paho-mqtt + Jinja2/Bootstrap 5/HTMX
- 已有：items, tenants, users 表 + 認證 + 多租戶隔離 + MQTT
- LQ-635C 使用 ESC/P 指令集（非 ESC/POS），80 欄 10CPI 標準，可壓縮至 132 欄
- USB 接在 server 主機，Linux 下透過 `/dev/usb/lp0` 寫入 raw bytes
- Python 可直接用 `open('/dev/usb/lp0', 'wb')` 送出 ESC/P 指令

## System Architecture

```
┌─────────────┐     HTTP      ┌──────────────┐     SQL        ┌────────────┐
│  Browser    │ ─────────────► │  FastAPI     │ ◄────────────► │ PostgreSQL │
│  (Web UI)   │ ◄───────────── │  Server      │                │ /SQLite    │
└─────────────┘               └──────┬───────┘                └────────────┘
                                     │
                              ┌──────┼───────────────┐
                              │      │               │
                              ▼      ▼               ▼
                        ┌─────────┐ ┌──────┐  ┌───────────┐
                        │ LQ-635C │ │ MQTT │  │ ESP32-S3  │
                        │ Printer │ │Broker│◄─│ Scanner   │
                        └─────────┘ └──────┘  └───────────┘
```

### Printing Architecture

```
Browser 點擊列印 → POST /api/print/{type}/{id}
                         │
                         ▼
              ┌─────────────────────┐
              │ print_service.py    │
              │ (組合資料+排版)      │
              └─────────┬───────────┘
                        │
              ┌─────────▼───────────┐
              │ printing/escp.py    │ ← ESC/P 指令封裝
              │ printing/templates/ │ ← 各單據排版
              └─────────┬───────────┘
                        │
              ┌─────────▼───────────┐
              │ printing/printer.py │ → /dev/usb/lp0
              └─────────────────────┘
```

## Directory Structure

```
src/
├── main.py
├── config.py
├── database.py
├── models/
│   ├── __init__.py
│   ├── base.py               ← Tenant, User
│   ├── item.py               ← Item, Category
│   ├── partner.py            ← Customer, Supplier
│   ├── transaction.py        ← PurchaseOrder, SalesOrder, Quotation + line items
│   ├── accounting.py         ← Receivable, Payable, Payment
│   ├── repair.py             ← RepairOrder, RepairPart
│   └── inventory.py          ← InventoryLog, StocktakeSession
├── services/
│   ├── warehouse_service.py
│   ├── auth_service.py
│   ├── partner_service.py
│   ├── purchase_service.py
│   ├── sales_service.py
│   ├── accounting_service.py
│   ├── repair_service.py
│   ├── inventory_service.py
│   └── print_service.py
├── printing/
│   ├── __init__.py
│   ├── escp.py               ← ESC/P 指令封裝
│   ├── printer.py            ← 印表機連線管理
│   └── templates/
│       ├── sales_order.py
│       ├── purchase_order.py
│       ├── quotation.py
│       ├── repair_order.py
│       └── statement.py
├── routes/
│   ├── web.py
│   ├── partners.py
│   ├── purchases.py
│   ├── sales.py
│   ├── accounting.py
│   ├── repairs.py
│   ├── inventory.py
│   └── printing.py
├── mqtt_handler.py
├── templates/
└── static/
```

## Database Schema Design

> 所有表皆帶 `tenant_id` 欄位做多租戶隔離（除 `tenants` 本身）。  
> 時間欄位統一使用 `TIMESTAMP`；金額使用 `NUMERIC(12,2)` 避免浮點誤差。

### 現有表（保留擴展）

```sql
-- 租戶
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 使用者
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',   -- super_admin / tenant_admin / user
    tenant_id INTEGER REFERENCES tenants(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 品項（擴展 cost/price）
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    barcode VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    spec VARCHAR(200),
    quantity INTEGER DEFAULT 0,
    location VARCHAR(100),
    cost NUMERIC(12,2) DEFAULT 0,        -- ← 新增：進貨成本
    price NUMERIC(12,2) DEFAULT 0,       -- ← 新增：建議售價
    category_id INTEGER REFERENCES categories(id),  -- ← 新增
    supplier_id INTEGER REFERENCES suppliers(id),   -- ← 新增：取代 supplier 文字欄位
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    date_in TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 品項分類
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(name, tenant_id)
);
```

### 客戶 / 廠商

```sql
-- 客戶
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL,              -- 客戶編號 e.g. C001
    name VARCHAR(200) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(50),
    address VARCHAR(500),
    tax_id VARCHAR(20),                     -- 統一編號
    notes TEXT,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(code, tenant_id)
);

-- 供應商
CREATE TABLE suppliers (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL,              -- 廠商編號 e.g. S001
    name VARCHAR(200) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(50),
    address VARCHAR(500),
    tax_id VARCHAR(20),
    bank_account VARCHAR(100),              -- 匯款帳號
    notes TEXT,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(code, tenant_id)
);
```

### 進貨單

```sql
-- 進貨單（主表）
CREATE TABLE purchase_orders (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(50) NOT NULL,          -- 單號 e.g. PO-20260723-001
    supplier_id INTEGER REFERENCES suppliers(id) NOT NULL,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(20) DEFAULT 'draft',     -- draft / confirmed / received / cancelled
    total_amount NUMERIC(12,2) DEFAULT 0,
    tax_amount NUMERIC(12,2) DEFAULT 0,
    notes TEXT,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(order_no, tenant_id)
);

-- 進貨單明細
CREATE TABLE purchase_order_lines (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE NOT NULL,
    item_id INTEGER REFERENCES items(id) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0,    -- quantity × unit_price
    received_qty INTEGER DEFAULT 0,              -- 實際收貨數量
    notes VARCHAR(200)
);
```

### 報價單

```sql
-- 報價單（主表）
CREATE TABLE quotations (
    id SERIAL PRIMARY KEY,
    quote_no VARCHAR(50) NOT NULL,           -- 單號 e.g. QT-20260723-001
    customer_id INTEGER REFERENCES customers(id) NOT NULL,
    quote_date DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_until DATE,                        -- 報價有效期限
    status VARCHAR(20) DEFAULT 'draft',      -- draft / sent / accepted / rejected / expired
    total_amount NUMERIC(12,2) DEFAULT 0,
    tax_amount NUMERIC(12,2) DEFAULT 0,
    notes TEXT,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(quote_no, tenant_id)
);

-- 報價單明細
CREATE TABLE quotation_lines (
    id SERIAL PRIMARY KEY,
    quotation_id INTEGER REFERENCES quotations(id) ON DELETE CASCADE NOT NULL,
    item_id INTEGER REFERENCES items(id) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    notes VARCHAR(200)
);
```

### 銷貨單

```sql
-- 銷貨單（主表）
CREATE TABLE sales_orders (
    id SERIAL PRIMARY KEY,
    order_no VARCHAR(50) NOT NULL,           -- 單號 e.g. SO-20260723-001
    customer_id INTEGER REFERENCES customers(id) NOT NULL,
    quotation_id INTEGER REFERENCES quotations(id),  -- 可由報價單轉入
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(20) DEFAULT 'draft',      -- draft / confirmed / shipped / completed / cancelled
    total_amount NUMERIC(12,2) DEFAULT 0,
    tax_amount NUMERIC(12,2) DEFAULT 0,
    notes TEXT,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(order_no, tenant_id)
);

-- 銷貨單明細
CREATE TABLE sales_order_lines (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES sales_orders(id) ON DELETE CASCADE NOT NULL,
    item_id INTEGER REFERENCES items(id) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    notes VARCHAR(200)
);
```

### 應收 / 應付帳款

```sql
-- 應收帳款（銷貨產生）
CREATE TABLE receivables (
    id SERIAL PRIMARY KEY,
    sales_order_id INTEGER REFERENCES sales_orders(id) NOT NULL,
    customer_id INTEGER REFERENCES customers(id) NOT NULL,
    amount NUMERIC(12,2) NOT NULL,           -- 應收金額
    paid_amount NUMERIC(12,2) DEFAULT 0,     -- 已收金額
    status VARCHAR(20) DEFAULT 'unpaid',     -- unpaid / partial / paid / overdue
    due_date DATE,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 應付帳款（進貨產生）
CREATE TABLE payables (
    id SERIAL PRIMARY KEY,
    purchase_order_id INTEGER REFERENCES purchase_orders(id) NOT NULL,
    supplier_id INTEGER REFERENCES suppliers(id) NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    paid_amount NUMERIC(12,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'unpaid',     -- unpaid / partial / paid / overdue
    due_date DATE,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 收付款記錄
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    payment_type VARCHAR(10) NOT NULL,       -- receive（收款）/ pay（付款）
    reference_type VARCHAR(20) NOT NULL,     -- receivable / payable
    reference_id INTEGER NOT NULL,           -- 對應 receivables.id 或 payables.id
    amount NUMERIC(12,2) NOT NULL,
    payment_method VARCHAR(20) DEFAULT 'cash',  -- cash / transfer / check
    payment_date DATE NOT NULL DEFAULT CURRENT_DATE,
    notes TEXT,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 維修工單

```sql
-- 維修工單
CREATE TABLE repair_orders (
    id SERIAL PRIMARY KEY,
    repair_no VARCHAR(50) NOT NULL,          -- 單號 e.g. RO-20260723-001
    customer_id INTEGER REFERENCES customers(id) NOT NULL,
    item_name VARCHAR(200) NOT NULL,         -- 送修品名（不一定在 items 中）
    brand VARCHAR(100),                      -- 品牌
    model VARCHAR(100),                      -- 型號
    serial_no VARCHAR(100),                  -- 產品序號
    fault_desc TEXT NOT NULL,                -- 故障描述
    status VARCHAR(20) DEFAULT 'received',   -- received / diagnosing / repairing / waiting_parts / done / returned
    repair_desc TEXT,                        -- 維修內容
    labor_fee NUMERIC(12,2) DEFAULT 0,       -- 工資
    parts_fee NUMERIC(12,2) DEFAULT 0,       -- 零件費
    total_fee NUMERIC(12,2) DEFAULT 0,       -- 總費用
    warranty_until DATE,                     -- 保固到期日
    received_date DATE DEFAULT CURRENT_DATE,
    completed_date DATE,
    returned_date DATE,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(repair_no, tenant_id)
);

-- 維修零件明細
CREATE TABLE repair_parts (
    id SERIAL PRIMARY KEY,
    repair_order_id INTEGER REFERENCES repair_orders(id) ON DELETE CASCADE NOT NULL,
    item_id INTEGER REFERENCES items(id),    -- 可連結庫存品項
    part_name VARCHAR(200) NOT NULL,         -- 零件名稱
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) DEFAULT 0,
    amount NUMERIC(12,2) DEFAULT 0,
    notes VARCHAR(200)
);
```

### 庫存異動

```sql
-- 庫存異動記錄（所有出入庫動作皆寫入）
CREATE TABLE inventory_logs (
    id SERIAL PRIMARY KEY,
    item_id INTEGER REFERENCES items(id) NOT NULL,
    action VARCHAR(20) NOT NULL,             -- in / out / adjust / stocktake
    quantity INTEGER NOT NULL,               -- 正數入庫，負數出庫
    before_qty INTEGER NOT NULL,             -- 異動前數量
    after_qty INTEGER NOT NULL,              -- 異動後數量
    reference_type VARCHAR(30),              -- purchase_order / sales_order / repair / manual
    reference_id INTEGER,                    -- 關聯單據 ID
    notes VARCHAR(200),
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 盤點作業
CREATE TABLE stocktake_sessions (
    id SERIAL PRIMARY KEY,
    session_no VARCHAR(50) NOT NULL,         -- 盤點單號
    status VARCHAR(20) DEFAULT 'open',       -- open / counting / closed
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP,
    notes TEXT,
    tenant_id INTEGER REFERENCES tenants(id) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(session_no, tenant_id)
);

-- 盤點明細
CREATE TABLE stocktake_items (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES stocktake_sessions(id) ON DELETE CASCADE NOT NULL,
    item_id INTEGER REFERENCES items(id) NOT NULL,
    system_qty INTEGER NOT NULL,             -- 系統庫存
    actual_qty INTEGER,                      -- 實盤數量
    difference INTEGER,                      -- actual - system
    scanned_at TIMESTAMP DEFAULT NOW(),
    notes VARCHAR(200)
);
```

## MQTT Topics（擴展）

> 保留原有 warehouse/query、warehouse/create，新增出入庫與盤點 topics。

| Topic | Direction | Description |
|-------|-----------|-------------|
| `warehouse/query` | ESP32 → Server | 條碼查詢品項 |
| `warehouse/create` | ESP32 → Server | 掃描建立新品項 |
| `warehouse/stock/in` | ESP32 → Server | 掃描入庫（進貨驗收） |
| `warehouse/stock/out` | ESP32 → Server | 掃描出庫（銷貨出貨） |
| `warehouse/stocktake/scan` | ESP32 → Server | 盤點掃描 |
| `warehouse/stocktake/start` | ESP32 → Server | 開始盤點作業 |
| `warehouse/stocktake/end` | ESP32 → Server | 結束盤點作業 |
| `warehouse/response/{device_id}` | Server → ESP32 | 回傳結果 |

### 新增 Payload 範例

**入庫掃描 → `warehouse/stock/in`**
```json
{
  "device_id": "esp32-001",
  "barcode": "4710088123456",
  "quantity": 10,
  "purchase_order_id": 5
}
```

**出庫掃描 → `warehouse/stock/out`**
```json
{
  "device_id": "esp32-001",
  "barcode": "4710088123456",
  "quantity": 2,
  "sales_order_id": 12
}
```

**盤點掃描 → `warehouse/stocktake/scan`**
```json
{
  "device_id": "esp32-001",
  "session_id": 3,
  "barcode": "4710088123456",
  "actual_qty": 48
}
```

---

## Task Breakdown（實作階段分解）

### Phase 1 — 基礎建設（Foundation）

| # | Task | Description |
|---|------|-------------|
| 1-1 | 重構 models.py → models/ package | 拆分為 base.py, item.py, partner.py, transaction.py, accounting.py, repair.py, inventory.py |
| 1-2 | Alembic migration 設置 | 初始化 Alembic，建立 initial migration（現有結構）|
| 1-3 | 新增 categories, customers, suppliers 表 | Migration + ORM models + 基本 CRUD |
| 1-4 | 擴展 items 表 | 加入 cost, price, category_id, supplier_id 欄位 |
| 1-5 | Partner 管理 Web UI | 客戶/廠商的 HTMX 列表 + 新增/編輯表單 |

### Phase 2 — 進銷貨單據

| # | Task | Description |
|---|------|-------------|
| 2-1 | 進貨單 (Purchase Order) | Model + Service + Routes + Web UI（主表+明細）|
| 2-2 | 報價單 (Quotation) | Model + Service + Routes + Web UI |
| 2-3 | 銷貨單 (Sales Order) | Model + Service + Routes + UI + 報價單轉銷貨單功能 |
| 2-4 | 單據編號產生器 | 自動產生 PO/QT/SO-{date}-{seq} 格式單號 |
| 2-5 | 庫存連動 | 進貨確認→入庫；銷貨確認→出庫（寫入 inventory_logs）|

### Phase 3 — 帳務管理

| # | Task | Description |
|---|------|-------------|
| 3-1 | 應收帳款 | 銷貨確認自動產生 receivable；列表+收款操作 |
| 3-2 | 應付帳款 | 進貨確認自動產生 payable；列表+付款操作 |
| 3-3 | 收付款記錄 | Payment 記錄 + 自動更新 receivable/payable 狀態 |
| 3-4 | 帳務報表 | 應收/應付匯總頁面，逾期提醒 |

### Phase 4 — 維修工單

| # | Task | Description |
|---|------|-------------|
| 4-1 | 維修工單 CRUD | Model + Service + Routes + 完整 Web UI |
| 4-2 | 維修零件管理 | repair_parts 明細，可從庫存品項帶入 |
| 4-3 | 狀態流程 | 狀態機轉換 + 歷程記錄 |
| 4-4 | 保固查詢 | 依客戶/序號查詢保固狀態 |

### Phase 5 — 條碼掃描擴展 + 盤點

| # | Task | Description |
|---|------|-------------|
| 5-1 | MQTT 入庫/出庫 handler | 新增 stock/in、stock/out topic 處理 + inventory_logs 寫入 |
| 5-2 | 盤點作業 | stocktake session 管理 + 掃描盤點 MQTT handler |
| 5-3 | 盤點差異報表 | 盤點完成後比對系統與實盤差異 |
| 5-4 | ESP32 韌體更新 | 新增模式選單：查詢 / 入庫 / 出庫 / 盤點 |

### Phase 6 — 列印模組

| # | Task | Description |
|---|------|-------------|
| 6-1 | ESC/P 指令封裝 | printing/escp.py — 初始化、中文列印、表格、換頁 |
| 6-2 | 印表機連線管理 | printing/printer.py — 偵測 /dev/usb/lp0 + 錯誤處理 |
| 6-3 | 進貨單列印 | 排版 template + API endpoint |
| 6-4 | 銷貨單 / 報價單列印 | 複寫聯格式（客戶聯 + 存根聯）|
| 6-5 | 維修單列印 | 收件單 + 完工通知單 |
| 6-6 | 對帳單列印 | 月結帳務明細（連續報表紙）|
