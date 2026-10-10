# DeepDoc 解析模型 · 来源与版本台账（开源合规留痕）

> 用途：混沌海文档解析管线（PPT/扫描 PDF/图片 OCR/表格识别）所依赖的第三方模型权重登记。
> 下载日期：2026-10-10 ｜ 下载人：开发环境自动留痕 ｜ 权重文件本身不入 git（.gitignore models/），本台账入库。

## 来源

- **上游仓库**：HuggingFace `InfiniFlow/deepdoc`（RAGFlow/DeepDoc 官方权重）
- **仓库快照 commit**：`9c7aa2c730d7`（2026-10-10 查询时 main HEAD）
- **许可**：Apache-2.0（随上游仓库声明）
- **下载 URL 模式**：`https://huggingface.co/InfiniFlow/deepdoc/resolve/main/<file>`
- **备选镜像**：`https://hf-mirror.com/InfiniFlow/deepdoc/resolve/main/<file>`

## 已登记文件（本地目录 models/deepdoc/）

| 文件 | 用途 | 大小 | SHA256 |
|---|---|---|---|
| det.onnx | 文本行检测（文字在哪） | 4.7 MB | `30a86f5731181461d08021402766601e4302a9b9b9666be8aff402696339cdff` |
| layout.onnx | 版面分析（10 类：标题/正文/图/表/公式…） | 75.7 MB | `de401c03ee30b1c120416dc06f0705237f0c36d3cdb692c9bfefe8a8f98a4b70` |
| rec.onnx | OCR 文字识别 | 10.8 MB | `1c7cf60de2afd728d512f4190cf37455092b45f06175365c6fc58d8cd7e2a68b` |
| ocr.res | OCR 字典资源 | 26 KB | `28b2362ad4ab2dc38769aa72feb535e3a9ddb3fd2a7585a05920e6393b1dc7f7` |

## 未下载（按需再取，同仓库同许可）

- `layout.laws.onnx` / `layout.manual.onnx` / `layout.paper.onnx`：法务/手册/论文领域版面模型——**中医典籍（M2 领域适配）如需可再取并补记本台账**
- 对应 `.ort` 变体：Go 运行时格式，Python onnxruntime 管线不使用

## 复验方法

```bash
cd models/deepdoc && shasum -a 256 det.onnx layout.onnx rec.onnx ocr.res
# 与上表 SHA256 比对，不一致 = 权重被篡改或版本漂移，禁止上线
```
