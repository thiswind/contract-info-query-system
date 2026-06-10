# 合同信息查询系统

合同信息查询系统是一个面向本地或内网使用的轻量级合同台账查询原型。系统把授权范围内的合同 Excel 台账与本地 PDF 原文目录关联起来，生成 SQLite 索引，并提供命令行工具与 Web 页面用于合同检索、详情查看、PDF 原文访问、历史数据导入和查询账号管理。

本仓库是 public 代码仓库，只包含源码与使用说明，不包含任何真实合同 Excel、PDF、SQLite 数据库、账号密码或派生数据。

## 适用场景

- 将已有合同台账 Excel 和合同 PDF 文件统一索引；
- 在内网服务器上提供合同查询入口；
- 支持管理员导入历史数据、新增合同、上传或引用 PDF；
- 为普通查询人员提供只读查询账号；
- 在不把真实合同资料提交到 Git 的前提下部署和维护系统。

当前版本定位为可部署原型，不是完整的合规审计、审批流、电子签章或 OCR 全文检索平台。

## 主要功能

- 导入合同 Excel 台账并生成本地 SQLite 索引；
- 扫描本地 PDF 目录，按合同编号或序号前缀与台账记录建立关联；
- 支持关键词、年份、供应商、采购方式、金额区间等条件查询；
- 支持合同详情页查看和下载已关联 PDF；
- 支持 Web 页面新增合同记录、上传 PDF 或引用已有 PDF；
- 支持本地 Web 登录、管理员账号、普通查询账号、账号启停和密码重置；
- 支持 CLI 初始化数据库、导入数据、检查文件引用、管理账号；
- 支持通过环境变量配置 workspace、数据目录、数据库路径、监听地址、二级访问路径和会话密钥。

## 技术栈

- Python 3.9+
- FastAPI / Uvicorn
- Jinja2
- SQLite
- openpyxl
- pypdf
- itsdangerous
- python-dotenv
- python-multipart

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

检查命令行入口：

```bash
contract-query --help
```

## 数据目录

默认以当前工作目录作为 workspace，数据目录结构如下：

```text
data/
  raw/
    采购合同细节.xlsx
    合同文件/
      example-001.pdf
      example-002.pdf
  processed/
    contracts.sqlite3
    session_secret.txt
```

说明：

- `data/raw/` 保存授权范围内的 Excel 和 PDF 原始资料；
- `data/processed/contracts.sqlite3` 是本地 SQLite 索引；
- `data/processed/session_secret.txt` 是本地会话签名密钥；
- `data/`、Office 文档、PDF、压缩包和 `.env` 均已被 `.gitignore` 排除，不应提交到仓库。

## 配置

系统会自动读取 `.env`，也可以直接使用环境变量：

```bash
export CONTRACT_QUERY_WORKSPACE=/path/to/workspace
export CONTRACT_QUERY_DATA_DIR=/path/to/workspace/data
export CONTRACT_QUERY_RAW_DIR=/path/to/workspace/data/raw
export CONTRACT_QUERY_PROCESSED_DIR=/path/to/workspace/data/processed
export CONTRACT_QUERY_DB=/path/to/workspace/data/processed/contracts.sqlite3
export CONTRACT_QUERY_SECRET_FILE=/path/to/workspace/data/processed/session_secret.txt
export CONTRACT_QUERY_SESSION_SECRET='replace-with-a-long-random-secret'
export CONTRACT_QUERY_HOST=127.0.0.1
export CONTRACT_QUERY_PORT=8000
export CONTRACT_QUERY_ROOT_PATH=/contract-query
```

如果不设置这些变量，系统会使用当前目录下的 `data/raw`、`data/processed`、`data/processed/contracts.sqlite3`，默认 Web 入口为 `/contract-query/`。

生产或长期内网部署建议显式设置 `CONTRACT_QUERY_SESSION_SECRET`，或妥善保管自动生成的 `session_secret.txt`。更换会话密钥后，已有登录会话会失效。

## 初始化

### 1. 初始化数据库和管理员账号

```bash
contract-query admin init
```

首次执行会创建 `admin` 管理员账号，并在终端输出一次性临时密码。请妥善保存该密码，不要提交到 Git 或聊天记录中。

如需同时创建一个普通查询账号 `query`：

```bash
contract-query admin init --create-viewer
```

如果管理员账号已存在，该命令不会覆盖现有账号。

### 2. 准备历史数据

将合同台账 Excel 和 PDF 文件放入数据目录，例如：

```text
data/raw/采购合同细节.xlsx
data/raw/合同文件/*.pdf
```

### 3. 预检查并导入

```bash
contract-query inventory
contract-query import-excel --dry-run
contract-query import-excel
contract-query check-files
```

`--dry-run` 只生成扫描报告，不写入数据库。

## 启动 Web 服务

```bash
contract-query serve --host 127.0.0.1 --port 8000
```

默认访问地址：

```text
http://127.0.0.1:8000/contract-query/
http://127.0.0.1:8000/health
```

登录后：

- 管理员可以查询合同、新增合同、导入历史数据、管理普通查询账号；
- 普通查询账号可以查询合同、查看详情、查看或下载 PDF；
- 未登录用户会被重定向到登录页。

## CLI 命令

```bash
contract-query inventory              # 盘点原始数据目录
contract-query import-excel --dry-run # 预检查导入结果，不写数据库
contract-query import-excel           # 导入 Excel 并映射 PDF
contract-query build-index            # 初始化空 SQLite 数据库
contract-query search "关键词"         # 查询合同元数据
contract-query check-files            # 检查数据库中的文件引用
contract-query serve                  # 启动 Web 服务

contract-query admin init                         # 创建初始管理员账号
contract-query admin init --create-viewer         # 同时创建 query 查询账号
contract-query admin list-users                   # 列出本地 Web 用户
contract-query admin reset-password --username 用户名 # 重置用户密码
```

## Web 路径

默认业务入口挂载在 `CONTRACT_QUERY_ROOT_PATH` 下：

```text
/contract-query/                          首页
/contract-query/login                     登录
/contract-query/contracts                 合同列表与筛选
/contract-query/contracts/new             新增合同，管理员可用
/contract-query/contracts/{contract_id}   合同详情，支持 ?format=json
/contract-query/files/{file_id}/view      在线查看 PDF
/contract-query/files/{file_id}/download  下载 PDF
/contract-query/import                    历史数据初始化，管理员可用
/contract-query/users                     用户管理，管理员可用
/contract-query/stats                     统计接口
/contract-query/inventory                 原始数据盘点接口，管理员可用
/contract-query/check-files               文件引用检查接口，管理员可用
/contract-query/health                    业务路径健康检查
/health                                   根路径健康检查
```

## 内网部署建议

建议让应用监听本机端口，再通过 Nginx、Caddy 或平台网关反向代理到内网二级路径。真实合同资料、SQLite 数据库、`.env` 和会话密钥应放在服务器授权目录中，不要打包进镜像、发布包或 Git 仓库。

一个常见部署流程：

```bash
git clone https://github.com/thiswind/contract-info-query-system.git
cd contract-info-query-system
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
contract-query admin init --create-viewer
contract-query import-excel --dry-run
contract-query import-excel
contract-query serve --host 127.0.0.1 --port 8000
```

如部署在反向代理二级路径下，请保持代理路径与 `CONTRACT_QUERY_ROOT_PATH` 一致。

## 无真实数据验证

可以使用临时 workspace 验证安装和基础入口：

```bash
export CONTRACT_QUERY_WORKSPACE=/tmp/contract-query-demo
contract-query build-index
contract-query admin init --create-viewer
contract-query search "test"
contract-query serve --host 127.0.0.1 --port 8000
```

上述命令会创建空数据库和本地测试账号，不需要真实合同文件。

## 数据安全边界

- 本仓库不包含真实合同 Excel、PDF、SQLite 索引、账号密码或派生数据；
- 使用者需要自行准备具备合法授权的数据文件；
- README 中只使用示例路径和示例文件名，不应写入真实合同名称、供应商、金额、文件名或合同正文；
- 本系统的本地账号用于轻量级内网访问控制，不替代统一身份认证、堡垒机、审计系统或合规审批流程；
- 对外网开放前，应补充 HTTPS、反向代理安全配置、备份策略、访问日志和更严格的权限控制。

## 范围与限制

- 当前搜索主要基于 Excel 字段、文件名和备注；
- PDF 目前用于原文查看、下载和页数等基础信息，不做 OCR 正文全文检索；
- 账号体系为本地 SQLite 用户表，适合小范围内网原型，不是企业级 IAM；
- 审计事件仅记录在本地数据库中，未接入集中日志平台；
- 批量统计导出、OCR、全文检索、审批流程、统一登录等能力可作为后续扩展。

## 项目结构

```text
src/contract_query/            Python 应用源码
src/contract_query/templates/  Web 页面模板
src/contract_query/static/     Web 静态资源
docs/                          项目补充说明
```

## 许可证

当前仓库未声明开源许可证。如需对外复用、二次分发或商业使用，请先补充明确的 LICENSE 文件或联系维护者确认授权边界。
