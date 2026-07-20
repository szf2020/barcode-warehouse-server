# barcode-warehouse-server

倉管條碼系統後端服務 — ESP32-S3 掃描條碼後透過 MQTT 查詢/建立倉管資料。

## Features

- **FastAPI REST API** — 品項 CRUD 操作，Swagger UI 文件自動生成
- **MQTT 即時通訊** — 接收 ESP32 條碼掃描請求，即時回傳查詢結果
- **PostgreSQL 資料庫** — 儲存倉管品項資料（品名、規格、數量、儲位、供應商）
- **雙向操作** — 支援掃描查詢既有品項 & 掃描建立新品項

## Tech Stack

| 元件 | 技術 |
|------|------|
| Web Framework | FastAPI 0.115.6 + Uvicorn |
| Database | PostgreSQL (SQLAlchemy ORM) |
| MQTT | paho-mqtt 2.1.0 (Mosquitto broker) |
| Language | Python 3.10+ |

## System Architecture

```
┌─────────────────┐       MQTT        ┌──────────────────────┐       SQL       ┌────────────┐
│  ESP32-S3       │ ◄──────────────► │  barcode-warehouse   │ ◄────────────► │ PostgreSQL │
│  Barcode Scanner│   Mosquitto       │  -server (FastAPI)   │                 │  warehouse │
└─────────────────┘                   └──────────────────────┘                 └────────────┘
                                              │
                                              │ REST API
                                              ▼
                                      ┌──────────────────┐
                                      │  Swagger UI /    │
                                      │  管理介面         │
                                      └──────────────────┘
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
# Edit .env with your PostgreSQL and MQTT settings
```

## Run

```bash
# Start server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Access Swagger UI
# http://localhost:8000/docs
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/items` | 列出所有品項（支援分頁） |
| GET | `/items/{barcode}` | 以條碼查詢品項 |
| POST | `/items` | 建立新品項 |
| PUT | `/items/{barcode}` | 更新品項資料 |
| DELETE | `/items/{barcode}` | 刪除品項 |

### Request/Response Examples

**查詢品項：**
```bash
curl http://localhost:8000/items/4710088123456
```

**建立品項：**
```bash
curl -X POST http://localhost:8000/items \
  -H "Content-Type: application/json" \
  -d '{
    "barcode": "4710088123456",
    "name": "電阻 10kΩ",
    "spec": "0805 1/8W",
    "quantity": 500,
    "location": "A-01-03",
    "supplier": "大毅科技"
  }'
```

## MQTT Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `warehouse/query` | ESP32 → Server | 條碼查詢請求 |
| `warehouse/create` | ESP32 → Server | 建立新品項請求 |
| `warehouse/response/{device_id}` | Server → ESP32 | 回傳查詢/操作結果 |

### MQTT Payload Format

**查詢 (warehouse/query):**
```json
{
  "barcode": "4710088123456",
  "device_id": "esp32-001"
}
```

**建立 (warehouse/create):**
```json
{
  "device_id": "esp32-001",
  "barcode": "4710088123456",
  "name": "電阻 10kΩ",
  "spec": "0805 1/8W",
  "quantity": 500,
  "location": "A-01-03",
  "supplier": "大毅科技"
}
```

**回應 (warehouse/response/{device_id}):**
```json
{
  "status": "found",
  "data": {
    "barcode": "4710088123456",
    "name": "電阻 10kΩ",
    "spec": "0805 1/8W",
    "quantity": 500,
    "location": "A-01-03",
    "supplier": "大毅科技",
    "date_in": "2026-07-20T10:00:00"
  }
}
```

## Database Schema

```sql
CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    barcode VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    spec VARCHAR(200),
    quantity INTEGER DEFAULT 0,
    location VARCHAR(100),
    supplier VARCHAR(200),
    date_in TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Related Projects

- **[esp32s3-barcode-scanner](https://github.com/JiangAlex/esp32s3-barcode-scanner)** — ESP32-S3 韌體端（PlatformIO + LVGL + OV2640）

## License

MIT
