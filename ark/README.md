# 一句话架构图 · Ark Seed 2.1（ark fork）

> 用一句大白话描述你的技术栈，得到一张带官方品牌 logo 的工程风架构图（浅色/深色双主题 PNG + 自包含 HTML）。
> 基于 [caru-ini/stack-diagram](https://github.com/caru-ini/stack-diagram)（MIT）改造：推理换火山方舟 Seed 2.1，新增火山/中文官方图标包与确定性排版引擎。分叉说明见 [NOTICE.md](../NOTICE.md)。

## 快速开始

```bash
# 1. 装依赖（Python 3.9+；首次会装 playwright chromium，约一分钟）
cd ark
cp .env.example .env        # 填入你的方舟 ARK_API_KEY
bash start.sh               # → http://127.0.0.1:8000
```

页面里点一个示例句（或自己写一句），等几秒，下载 PNG。

## 它是怎么工作的

```
一句话 ──方舟 Seed 2.1（OpenAI 兼容端点）──▶ {nodes, groups, edges} JSON
        │                                    （pydantic 校验 + 带反馈重试 1 次）
        ▼
确定性排版引擎（分层/分组框/正交走线/走廊避让，常量来自 references/geometry.md）
        ▼
template.html（中文自适应）─▶ fetch_icons.py（volc 本地包 + svgl/devicon 链）
        ▼
build.py 内联 ─▶ render_png.py 双主题 PNG ─▶ check.py DOM 级自查（无压线/图标/越界）
```

- 模型只负责「听懂」（内容抽取），每个像素的坐标都由代码按规则计算。
- 每次生成会自动自查并在结果里给出徽标；生成失败给中文原因（账户欠费/Key 无效/超时）。
- 模型档位：`lite`（默认，约 ¥0.005/次）与 `pro`（约 ¥0.05/次）。

## 文件

| 路径 | 作用 |
|---|---|
| `ark/server.py` + `ark/web/index.html` | 网页版（FastAPI，本地运行） |
| `ark/pipeline.py` | 端到端流水线（图标/排版/渲染/自查） |
| `ark/spec.py` / `ark/prompts.py` | 规格层 schema、校验修复、系统提示词 |
| `ark/layout.py` | 确定性排版引擎 |
| `ark/check.py` | Playwright DOM 级视觉自查 |
| `ark/test_stub.py` | 离线端到端测试（不调 API，手写 spec 全流程出图） |
| `skills/stack-diagram/` | 上游技能本体（含 volc 图标包与中文适配） |

## 许可

代码 MIT（承上游）；字体 SIL OFL 1.1；品牌 logo 为各自所有者的商标，仅作指示性使用（见
`skills/stack-diagram/assets/volc/CREDITS.md`）。
