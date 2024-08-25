# 系統
AMDB是一個基於Django開發的運維平台
平台的主要功能包括：AMDB、外租設備、虛擬機操作，最終作為包發佈和工具系統的角色
與SaltStack、Zabbix...等系統進行整合

* AMDB：資產信息管理，快速創建Vsphere和Nutanix虛擬機，而且Salt的Agent非常適合採集這些基礎信息最後
* 虛擬機初始化發佈：程序包發佈的功能，主要是調用SaltStack的state.sls進行發佈的動作，

## 目錄
- [AMDB系統](#AMDB系統)
  - [目錄](#目錄)
  - [1. System requirements](#1-system-requirements)
  - [2. 建議配置](#2-建議配置)
  - [3. 端口規劃](#3-端口規劃)
  - [安裝依賴](#安裝依賴)
  - [設定數據庫名稱](#設定數據庫名稱)
  - [本地腳本](#本地腳本)
  - [線上版本](#線上版本)
  - [Unit Test](#unit-test)
  - [Manage Command](#manage-command)

## 1. System requirements

推薦使用 pyenv virtualenv 與 docker 安裝環境

- Python 3.7.4;
- Poetry ^1.1.7;
- Web-server (Nginx) **Prodution and Dev only**;
- Database (MySQL 8);
  - 包含 mysqlclient 套件, 需要環境支持
- Cache (RedisCluster);
- MQ (Redis);

## 2. 建議配置

| 類型     | 配罝    |
| -------- | ------- |
| 系統     | Centos7 |
| CPU      | 4 核    |
| Memory   | 8G      |
| 磁盤空間 | 200G    |

## 3. 端口規劃

| 類型  | 端口 | 説明                    |
| ----- | ---- | ----------------------- |
| Nginx | ---- | 對接 VIP 阜號           |
| uWSGI | 8089 | 預設對接 Nginx 連接阜號 |

## 安裝依賴
```bash
pyenv virtualenv 3.7.4 $(cat .python-version)
pip install --upgrade pip
pip install poetry

pyenv activate $(cat .python-version)

# Prodution Build
# poetry install --no-dev

# Local Build
poetry install
```

## 設定數據庫名稱
```sql
-- For databases other than SQLite
CREATE DATABASE AMDB;
```

## 本地腳本
```bash
python manage.py makemigrations
python manage.py collectstatic --noinput
python manage.py migrate


./uwsgi.sh run
./celery.sh run
```

## 線上版本
```bash
python manage.py collectstatic --noinput
python manage.py migrate

./uwsgi.sh start
./celery.sh start
```

## Unit Test
```bash

python manage.py test

```

## Manage Command
路徑：apps/management/management/commands
```bash
python manage.py init_AMDB --user "<用户名>" --email "<信箱>"

python manage.py upload_AMDB "<appname>"

python manage.py runscript "<file>"
```