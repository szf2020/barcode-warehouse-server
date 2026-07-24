# SoftSnail 倉管系統 — 使用說明

## 啟動服務

```bash
# 啟動虛擬環境
source .venv/bin/activate

# 啟動服務（port 8040）
uvicorn src.main:app --host 0.0.0.0 --port 8040 --reload

# 瀏覽器開啟
http://localhost:8040/
```

## 預設帳號

首次啟動需執行 seed 建立管理員帳號：

```bash
python scripts/seed.py
```

| 帳號 | 密碼 | 角色 |
|------|------|------|
| admin | admin123 | super_admin |

> ⚠️ 請登入後立即修改密碼

## 功能模組

| 模組 | 路徑 | 說明 |
|------|------|------|
| 庫存 Inventory | `/web/items` | 品項管理 + 即時庫存數量 |
| 客戶 Customers | `/web/customers` | 客戶建檔（自動編號 C001~） |
| 供應商 Suppliers | `/web/suppliers` | 供應商建檔（自動編號 S001~） |
| 進貨 Purchase | `/web/purchases` | 進貨單（草稿→確認→收貨入庫） |
| 報價 Quote | `/web/quotations` | 報價單（草稿→送出→接受/拒絕） |
| 銷貨 Sales | `/web/sales` | 銷貨單（草稿→確認→出貨扣庫→完成） |
| 帳務 Accounting | `/web/accounting` | 應收/應付帳款 + 收付款記錄 |
| 維修 Repair | `/web/repairs` | 維修工單（狀態追蹤 + 零件費用） |
| 廠商 Tenants | `/web/tenants` | 多租戶管理（super_admin 專用） |
| 員工 Staff | `/web/users` | 員工帳號管理 |
| 列印 Print | `/api/print/...` | ESC/P 點陣列印（LQ-635C） |

## 操作流程

### 進貨流程

```
新增進貨單 → 選供應商 → 加明細（掃碼/選品項）
→ 確認（自動產生應付帳款）→ 收貨入庫（庫存+）
```

### 銷貨流程

```
報價單 → 客戶接受 → 一鍵轉銷貨單
→ 確認（自動產生應收帳款）→ 出貨扣庫（庫存-）→ 完成
```

### 維修流程

```
收件 → 檢測 → 維修中 / 等零件 → 完工 → 客戶取件
```

## MQTT 掃碼操作

ESP32 掃碼器可透過 MQTT 直接操作：

| Topic | 說明 |
|-------|------|
| `warehouse/query` | 掃碼查詢品項 |
| `warehouse/create` | 掃碼建立新品項 |
| `warehouse/stock/in` | 掃碼入庫（+數量） |
| `warehouse/stock/out` | 掃碼出庫（-數量） |
| `warehouse/stocktake/start` | 開始盤點 |
| `warehouse/stocktake/scan` | 盤點掃描 |
| `warehouse/stocktake/end` | 結束盤點 |

### 入庫掃碼範例

```json
{"device_id": "esp32-001", "barcode": "4710088123456", "quantity": 10}
```

### 出庫掃碼範例

```json
{"device_id": "esp32-001", "barcode": "4710088123456", "quantity": 2}
```

## 語言切換

Navbar 右上角有 🌐 按鈕，支援中文/英文切換。

## 列印功能

支援 Epson LQ-635C 點陣印表機（USB 接 server）：

- 進貨單列印：`POST /api/print/purchase/{id}`
- 銷貨單列印：`POST /api/print/sales/{id}`
- 報價單列印：`POST /api/print/quotation/{id}`
- 維修收件單：`POST /api/print/repair/{id}/receipt`
- 維修完工單：`POST /api/print/repair/{id}/completion`

> 如果印表機不可用，會自動儲存到 `/tmp/print_output.prn`

## 資料庫

- 開發環境：SQLite（`warehouse.db`）
- 生產環境：PostgreSQL

切換方式：修改 `.env` 中的 `DB_TYPE=postgresql` 並設定 PG 連線資訊。

### Migration

```bash
# 查看目前版本
alembic current

# 升級到最新
alembic upgrade head

# 產生新 migration
alembic revision --autogenerate -m "描述"
```

## 目錄結構

```
src/
├── main.py                 ← FastAPI 入口
├── config.py               ← 環境變數設定
├── database.py             ← SQLAlchemy 引擎
├── mqtt_handler.py         ← MQTT 訂閱/處理
├── models/                 ← ORM models + Pydantic schemas
├── services/               ← 業務邏輯
├── routes/                 ← Web UI routes
├── printing/               ← ESC/P 列印模組
├── templates/              ← Jinja2 HTML 模板
└── static/                 ← CSS/JS 靜態檔案
```

## API 文件

Swagger UI：`http://localhost:8040/docs`
