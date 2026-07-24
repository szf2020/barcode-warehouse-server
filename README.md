# SoftSnail 倉管系統 (barcode-warehouse-server)

進銷存 ERP 系統後端服務 — 支援條碼掃描入出庫、進銷貨單據、帳務管理、維修工單、點陣列印。

## Features

- **Web UI** — Jinja2 SSR + HTMX + Bootstrap 5，中英文切換
- **進銷貨單據** — 報價單 → 銷貨單 → 應收帳款；進貨單 → 應付帳款
- **庫存管理** — 即時庫存、出入庫連動、盤點作業
- **帳務管理** — 應收/應付帳款、收付款記錄、帳務匯總
- **維修工單** — 狀態追蹤、零件管理、費用計算
- **MQTT 即時通訊** — ESP32 條碼掃描器入出庫 + 盤點
- **點陣列印** — Epson LQ-635C ESC/P 指令，支援所有單據列印
- **多租戶** — 資料隔離、角色權限（super_admin / tenant_admin / user）

## Tech Stack

| 元件 | 技術 |
|------|------|
| Web Framework | FastAPI 0.115.6 + Uvicorn |
| Frontend | Jinja2 + HTMX 2.0 + Bootstrap 5 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| ORM | SQLAlchemy 2.0 |
| Migration | Alembic |
| MQTT | paho-mqtt 2.1.0 (Mosquitto broker) |
| Printing | ESC/P raw commands → /dev/usb/lp0 |
| Language | Python 3.10+ |

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

## Installation

```bash
# Clone
git clone https://github.com/JiangAlex/barcode-warehouse-server.git
cd barcode-warehouse-server

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — 設定 DB_TYPE (sqlite/postgresql) 與 MQTT 連線

# Initialize database + create admin account
python scripts/seed.py

# Install Mosquitto MQTT Broker (Ubuntu/Debian)
sudo apt install mosquitto mosquitto-clients
```

## Run

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8040 --reload
```

開啟瀏覽器：`http://localhost:8040/`

預設帳號：`admin` / `admin123`

## Project Structure

```
src/
├── main.py                 ← FastAPI 入口
├── config.py               ← 環境變數設定
├── database.py             ← SQLAlchemy 引擎
├── mqtt_handler.py         ← MQTT 7 個 topic handler
├── models/                 ← ORM models (20 tables)
│   ├── base.py             ← Tenant, User
│   ├── item.py             ← Item, Category
│   ├── partner.py          ← Customer, Supplier
│   ├── transaction.py      ← PurchaseOrder, Quotation, SalesOrder + lines
│   ├── accounting.py       ← Receivable, Payable, Payment
│   ├── repair.py           ← RepairOrder, RepairPart
│   └── inventory.py        ← InventoryLog, StocktakeSession
├── services/               ← 業務邏輯
├── routes/                 ← Web UI routes
├── printing/               ← ESC/P 列印模組
│   ├── escp.py             ← ESC/P 指令封裝
│   ├── printer.py          ← 印表機連線管理
│   └── templates/          ← 各單據排版
├── templates/              ← Jinja2 HTML
└── static/                 ← CSS/JS
docs/
├── UserGuide.md            ← 使用者操作手冊
├── erp_plan.md             ← ERP 實作計畫 + DB schema
└── hw_shopping_list.md     ← 硬體採購清單
```

## Database (20 tables)

| 類別 | Tables |
|------|--------|
| 基礎 | tenants, users, categories |
| 庫存 | items, inventory_logs, stocktake_sessions, stocktake_items |
| 夥伴 | customers, suppliers |
| 進銷貨 | purchase_orders, purchase_order_lines, quotations, quotation_lines, sales_orders, sales_order_lines |
| 帳務 | receivables, payables, payments |
| 維修 | repair_orders, repair_parts |

### Migration

```bash
alembic current          # 查看目前版本
alembic upgrade head     # 升級到最新
alembic revision --autogenerate -m "描述"  # 產生新 migration
```

## MQTT Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `warehouse/query` | ESP32 → Server | 條碼查詢品項 |
| `warehouse/create` | ESP32 → Server | 建立新品項 |
| `warehouse/stock/in` | ESP32 → Server | 掃碼入庫 |
| `warehouse/stock/out` | ESP32 → Server | 掃碼出庫 |
| `warehouse/stocktake/start` | ESP32 → Server | 開始盤點 |
| `warehouse/stocktake/scan` | ESP32 → Server | 盤點掃描 |
| `warehouse/stocktake/end` | ESP32 → Server | 結束盤點 |
| `warehouse/response/{device_id}` | Server → ESP32 | 回傳結果 |

## REST API

Swagger UI：`http://localhost:8040/docs`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/items` | 列出所有品項（分頁） |
| GET | `/items/{barcode}` | 查詢品項 |
| POST | `/items` | 建立品項 |
| PUT | `/items/{barcode}` | 更新品項 |
| DELETE | `/items/{barcode}` | 刪除品項 |
| POST | `/api/print/{type}/{id}` | 列印單據 |

## Printing

支援 Epson LQ-635C 點陣印表機（USB 接 server，Linux `/dev/usb/lp0`）：

- 進貨單、銷貨單、報價單
- 維修收件單、完工通知單
- 應收/應付對帳單（連續報表紙）

## Environment Variables (.env)

| 變數 | 說明 | 預設值 |
|------|------|--------|
| DB_TYPE | 資料庫類型 | sqlite |
| SQLITE_PATH | SQLite 檔案路徑 | ./warehouse.db |
| PGHOST | PostgreSQL 主機 | localhost |
| PGPORT | PostgreSQL 端口 | 5432 |
| PGUSER | 資料庫使用者 | user |
| PGPASSWORD | 資料庫密碼 | password |
| PGDATABASE | 資料庫名稱 | warehouse |
| MQTT_BROKER | MQTT Broker 位址 | localhost |
| MQTT_PORT | MQTT Broker 端口 | 1883 |
| SECRET_KEY | Session 加密金鑰 | (change me) |
| PRINTER_DEVICE | 印表機裝置路徑 | /dev/usb/lp0 |

## Related Projects

- **[esp32s3-barcode-scanner](https://github.com/JiangAlex/esp32s3-barcode-scanner)** — ESP32-S3 韌體端（PlatformIO + LVGL + OV2640）

## License

MIT
