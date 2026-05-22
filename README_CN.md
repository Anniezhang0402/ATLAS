<div align="center">

# ATLAS

**A**gentic **T**ools for **L**ayered **A**nnotation of **S**ingle-cells

*面向单细胞 RNA-seq 细胞类型注释的多智能体 LLM 框架——CASSIA 论文的独立复现实现。*

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/原论文-Nat%20Commun%202026-red)](https://doi.org/10.1038/s41467-025-67084-x)
[![Original](https://img.shields.io/badge/基于-CASSIA-orange)](https://github.com/ElliotXie/CASSIA)

[🇬🇧 English README](README.md) ·
[📐 架构文档](docs/ARCHITECTURE.md) ·


</div>

---

## 这是什么？

ATLAS 是一个用多智能体大语言模型（multi-agent LLM）为单细胞 RNA 测序聚类做注释的系统，
输出带可解释推理和质量评分的细胞类型预测。

本项目的目标是**忠实复现**：每个架构决策都能追溯到论文或 CASSIA 开源代码，
并明确标注来源。ATLAS 只用 **OpenRouter** 作为 LLM 提供方（CASSIA 同时支持多家），
以让代码保持精简、可读。

本项目作为以下技能的实践练习：
- 多智能体 LLM 协作编排
- 学术软件的忠实复现
- 与生物学知识库（CellMarker 2.0, Cell Ontology）协作

## ✨ 项目亮点

- **完整复现**：论文里 5 个核心 agent + 2 个可选 agent，全部跑通
- **真实数据验证**：成功复现论文 Fig 6b 的"识别 gold standard 标注错误"案例
  （monocyte 实际是 enteric glial cells）
- **开箱即用**：自带预处理过的 CellMarker 2.0 和 Cell Ontology
- **一个 key、任意模型**：通过 OpenRouter 同时访问 GPT-5、Claude Sonnet 4.5、Gemini、Llama、DeepSeek
- **成本可控**：默认 4-agent pipeline 平均 ~$0.04/cluster
- **HTML 报告**：每次注释都生成发表级别的可视化报告

详细架构见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 🚀 90 秒上手

### 1. 安装

```bash
git clone https://github.com/YOUR_USERNAME/ATLAS.git
cd ATLAS
pip install -r requirements.txt
```

### 2. 配置 OpenRouter API key

在 <https://openrouter.ai> 申请（充值 $5 大约够跑 100 次注释）：

```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

### 3. 注释一个 cluster

```python
import sys
sys.path.insert(0, '.')

from atlas.pipeline import annotate_cluster_full

result = annotate_cluster_full(
    species="Human",
    tissue="PBMC",
    marker_list=["CD8A", "CD8B", "CD3D", "GZMK", "NKG7",
                 "CCL5", "IL7R", "PRF1", "TRAC", "GNLY"],
)

print(result["structured"])
# {'main_cell_type': 'CD8+ T cells',
#  'sub_cell_types': ['CD8+ Effector Memory T cells (TEM)', ...]}

print(f"质量分: {result['score']}/100")
```

### 4. 生成 HTML 报告

```python
from atlas.reports import save_report

save_report(
    result,
    output_path="cd8_t_cell_report.html",
    species="Human",
    tissue="PBMC",
    marker_list=marker_list,
)
# 浏览器双击 HTML 文件即可查看。
```

## 📊 已验证的性能

以下是本仓库测试套件用 CASSIA 论文示例数据跑出来的真实结果：

| 测试用例 | 结果 | 分数 | 备注 |
|---|---|---|---|
| 清晰 CD8+ T cell（marker 明确） | ✅ 正确 | 92/100 | 默认 4-agent pipeline |
| CD8+ T cell + RAG 增强 | ✅ 子类型更精细 | 95/100 | Hierarchical Feature agent 加入了 T 细胞判别轴 |
| Plasma cell（housekeeping markers 主导） | ✅ 正确 | 78/100 | Annotator 看穿了噪声 |
| **Monocyte（论文 Fig 6b 的标注错误案例）** | ✅ **识别出 gold standard 错误** | 68/100 | Boost agent 确认实际是 enteric glial cells |
| 混合 T + B 细胞 | ✅ 正确报告 mixed | — | — |

所有结果都可复现——见 [`docs/REPRODUCTION.md`](docs/REPRODUCTION.md)。

## 💰 成本参考

2026 年 5 月 OpenRouter 实测价格：

| Pipeline | LLM 调用 | 典型成本 | 适用场景 |
|---|---|---|---|
| 3-agent（不含 Scoring） | 3 | ~$0.04 | 快速原型 |
| 4-agent 默认 | 4 | ~$0.04 | 标准注释 |
| 4-agent + Boost | +5–9 | +$0.10 | score < 75 的 cluster |
| 4-agent + RAG | +1 | +$0.05 | 复杂或冷门组织 |
| 完整（4-agent + Boost + RAG） | 多达 14 | ~$0.20 | 最高置信度需求 |

**省钱小贴士**：Scoring 默认用 DeepSeek v3（约 $0.001/次），Formatter 用 Gemini Flash，
只有 Annotator/Validator/Boost 用强模型如 Claude Sonnet 4.5。
任何 agent 都可通过 `*_model=` 参数覆盖默认模型。

## 🧬 7 个 Agent

| # | Agent | 用 LLM? | 做什么 |
|---|---|---|---|
| 1 | **Annotator** | ✅ | 对 marker 列表做 chain-of-thought 推理，给出主类型 + 3 个子类型 |
| 2 | **Validator** | ✅ | 检查 marker-celltype 一致性，必要时要求修订（≤3 轮） |
| 3 | **Formatter** | ✅ | 把自由文本注释转成结构化 JSON |
| 4 | **Scoring** | ✅ | 基于 marker 平衡性和科学准确性打 0-100 分 |
| 5 | **Reporter** | ❌ | 把完整对话历史渲染成漂亮的 HTML 报告 |
| 6 | **Annotation Boost**（可选） | ✅ | ReAct 循环：提假设 → 查 FindAllMarkers 基因统计 → 修正。挽救低置信注释 |
| 7 | **RAG**（可选） | ✅ | 3 个子 agent：查 CellMarker 2.0 + Cell Ontology + LLM 抽取判别轴 |


## ⚖️ License

MIT —— 与 CASSIA 一致。详见 [LICENSE](LICENSE)。
