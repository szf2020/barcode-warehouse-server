# System Architecture & Protocol Notes

## 概述

倉管條碼系統後端服務，負責接收 ESP32-S3 掃描器透過 MQTT 發送的條碼查詢/建立請求，
查詢 PostgreSQL 資料庫後回傳品項資訊。同時提供 REST API 供管理介面使用。

## 系統架構

```
┌──────────────────┐                    ┌───────────────┐
│  ESP32-S3        │                    │  Mosquitto    │
│  Barcode Scanner │ ── MQTT Pub ──►   │  MQTT Broker  │
│  (多台設備)       │ ◄── MQTT Sub ──   │  Port: 1883   │
└──────────────────┘                    └───────┬───────┘
                                                │
                                                │ Subscribe/Publish
                                                ▼
                                    ┌───────────────────────┐
                                    │  barcode-warehouse    │
                                    │  -server              │
                                    │  FastAPI + paho-mqtt  │
                                    │  Port: 8000           │
                                    └───────────┬───────────┘
                                                │
                                                │ SQLAlchemy
                                                ▼
                                    ┌───────────────────────┐
                                    │  PostgreSQL           │
                                    │  Host: blog.softsnail │
                                    │  .com:1432            │
                                    │  DB: warehouse        │
                                    └───────────────────────┘
```

## Database Schema

### items 表

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | 自動遞增 ID |
| barcode | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | 條碼（唯一識別） |
| name | VARCHAR(200) | NOT NULL | 品名 |
| spec | VARCHAR(200) | NULLABLE | 規格 |
| quantity | INTEGER | DEFAULT 0 | 數量 |
| location | VARCHAR(100) | NULLABLE | 儲位（如 A-01-03） |
| supplier | VARCHAR(200) | NULLABLE | 供應商 |
| date_in | TIMESTAMP | DEFAULT NOW() | 入庫日期 |
| updated_at | TIMESTAMP | DEFAULT NOW(), ON UPDATE | 最後更新時間 |

### 儲位編碼規則

建議格式：`{區域}-{架號}-{層號}`
- 例：`A-01-03` = A 區 第1架 第3層
- 例：`B-12-01` = B 區 第12架 第1層

## MQTT Protocol 設計

### Broker 設定

- Host: `localhost`（可部署在同一台 Raspberry Pi / Linux 主機）
- Port: `1883`（標準 MQTT port）
- 無認證（內部區域網路使用）

### Topics

| Topic | Publisher | Subscriber | 用途 |
|-------|-----------|------------|------|
| `warehouse/query` | ESP32 | Server | 條碼查詢請求 |
| `warehouse/create` | ESP32 | Server | 新品項建立請求 |
| `warehouse/response/{device_id}` | Server | ESP32 | 回傳結果給特定設備 |

### Payload 格式 (JSON)

#### 查詢請求 → `warehouse/query`
```json
{
  "barcode": "4710088123456",
  "device_id": "esp32-001"
}
```

#### 建立請求 → `warehouse/create`
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

#### 回應 — 查詢成功 → `warehouse/response/{device_id}`
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

#### 回應 — 查詢未找到
```json
{
  "status": "not_found",
  "barcode": "4710088123456",
  "message": "Item not found in database"
}
```

#### 回應 — 建立成功
```json
{
  "status": "created",
  "data": {
    "barcode": "4710088123456",
    "name": "電阻 10kΩ"
  }
}
```

#### 回應 — 錯誤
```json
{
  "status": "error",
  "message": "Barcode 4710088123456 already exists"
}
```

## ESP32-S3 硬體端通訊流程

### 查詢流程
```
1. ESP32 掃描條碼 → 解碼得到 barcode string
2. ESP32 publish JSON 到 "warehouse/query"
3. Server 收到 → 查 PostgreSQL
4. Server publish 結果到 "warehouse/response/esp32-001"
5. ESP32 收到結果 → LVGL 顯示品項詳細資訊
```

### 建立流程
```
1. ESP32 掃描條碼 → 解碼得到 barcode string
2. ESP32 UI 提示輸入品名、規格、數量等（或用預設值）
3. ESP32 publish JSON 到 "warehouse/create"
4. Server 收到 → 檢查是否重複 → 寫入 PostgreSQL
5. Server publish 確認到 "warehouse/response/esp32-001"
6. ESP32 螢幕顯示 "建立成功" 或錯誤訊息
```

## .env 設定說明

| 變數 | 說明 | 預設值 |
|------|------|--------|
| PGHOST | PostgreSQL 主機位址 | blog.softsnail.com |
| PGPORT | PostgreSQL 端口 | 1432 |
| PGUSER | 資料庫使用者 | reef |
| PGPASSWORD | 資料庫密碼 | (見 .env) |
| PGDATABASE | 資料庫名稱 | warehouse |
| MQTT_BROKER | MQTT Broker 位址 | localhost |
| MQTT_PORT | MQTT Broker 端口 | 1883 |
| MQTT_TOPIC_QUERY | 查詢 topic | warehouse/query |
| MQTT_TOPIC_CREATE | 建立 topic | warehouse/create |
| MQTT_TOPIC_RESPONSE | 回應 topic 前綴 | warehouse/response |

## ESP32-S3 GPIO Pin Map (硬體端參考)

詳見 [esp32s3-barcode-scanner](https://github.com/JiangAlex/esp32s3-barcode-scanner) 專案。

### 摘要

| Module | Signal | GPIO | Notes |
|--------|--------|------|-------|
| Camera OV2640 | XCLK | 15 | Camera clock |
| | SIOD/SIOC | 4/5 | SCCB I2C |
| | VSYNC/HREF/PCLK | 6/7/13 | Sync signals |
| | D0-D7 | 11,9,8,10,12,18,17,16 | Data bus |
| TFT SPI | MOSI/SCLK/CS/DC/RST/BL | 35/36/37/38/39/40 | Display |
| SD Card SPI | MISO/MOSI/SCLK/CS | 41/42/2/1 | Storage |
| Misc | BUZZER/LED/BTN | 14/48/0 | UI feedback |

## 專案目錄結構

```
barcode-warehouse-server/
├── src/
│   ├── __init__.py
│   ├── main.py              ← FastAPI app entry, REST endpoints
│   ├── config.py            ← .env 設定載入
│   ├── database.py          ← SQLAlchemy engine/session
│   ├── models.py            ← ORM model + Pydantic schemas
│   ├── mqtt_handler.py      ← MQTT 訂閱/查詢/回傳
│   └── services/
│       ├── __init__.py
│       └── warehouse_service.py  ← CRUD 業務邏輯
├── docs/
│   └── hw_shopping_list.md  ← 硬體採購清單
├── .env                     ← 環境變數（不入版控）
├── .env.example             ← 環境變數範本
├── .gitignore
├── requirements.txt
├── README.md
└── memory.md                ← 本文件
```
