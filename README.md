<h3 align="center">混沌海 ChaosSea</h3>
<h4 align="center">多产品统一知识库 · 产品 × 用户矩阵租户 · 证据可溯的检索与问答</h4>

<p align="center">
  <a href="https://github.com/1Panel-dev/MaxKB"><img src="https://img.shields.io/badge/based%20on-MaxKB%20v2-blue" alt="based on MaxKB v2"></a>
  <img src="https://img.shields.io/badge/license-GPL--3.0-green" alt="License: GPL v3">
</p>

## 什么是混沌海

**混沌海（ChaosSea）** 是数据中台（Chaos）之上、面向多产品的统一知识库：

- **多产品 × 多用户矩阵租户**：个人工作台、Superman、OpenSkoob 等产品按 Product ID × User ID 隔离接入，同一用户跨产品可授权共享资料；
- **证据可溯**：回答附带条文级出处引用，原文哈希校验；检索支持向量 / 关键词 / 混合三种模式；
- **全格式解析**：Markdown / Word / PDF / PPT / Excel / HTML / 图片 OCR，可扩展高精度解析后端；
- **图谱检索（规划中）**：实体关系图谱支撑关系型问题，RAG 算法基于 LightRAG 移植；
- **问答应用**：知识库问答、工作流编排、OpenAI 兼容接口、嵌入第三方网站。

[中文说明](README_CN.md)

## 开发与部署

```bash
# 本地开发（依赖 uv）
uv sync
cp .env.example .env   # 配置数据库/Redis/租户密钥
python main.py upgrade_db
python main.py dev web        # Web + API (8080)
python main.py dev celery     # 异步任务 worker
```

## 致谢与许可

本项目基于 [1Panel-dev/MaxKB](https://github.com/1Panel-dev/MaxKB)（v2 分支）深度定制，遵循 **GPL-3.0** 许可，感谢上游社区。
产品规划与架构决策见仓内 `docs/`。
