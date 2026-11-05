# NOTICE — ark fork 分叉说明

本仓库是 [caru-ini/stack-diagram](https://github.com/caru-ini/stack-diagram) 的私有改造分支（fork 基线钉在
**v0.4.0 / commit `1ed53e3e9525364ae5d82e0430f2bb3f7ef4c838`，2026-11-03**）。上游代码与文档为 MIT
（见 LICENSE），字体 SIL OFL 1.1。本分支的改动同样以 MIT 提供。

## 相对上游的改动（ark 分支）

1. **推理后端换成火山方舟 Seed 2.1**：新增 `ark/` 包——`spec.py` 把「一句话 → nodes/groups/edges
   JSON 规格层」变成一次 OpenAI 兼容接口调用（校验 + 带反馈重试），上游原版由 agent 读 SKILL.md
   手写 HTML、手排坐标。
2. **确定性排版引擎**：`ark/layout.py` 按 `references/geometry.md` 的常量实现分层布局、分组包围盒、
   正交走线（含无碰撞走廊搜索、行距自适应、标签避线），替代上游「agent 手排坐标 + 看图自查」。
   `ark/check.py` 用 Playwright 在真实 DOM 上断言「无压线 / 图标加载 / 不越界」，双主题各查一遍。
3. **火山生态 + 中文常用栈官方图标包**：`skills/stack-diagram/assets/volc/`（火山引擎/豆包/扣子/
   TRAE/飞书/微信/抖音/小红书 + cron 概念图标），`fetch_icons.py` 新增 `volc/` 本地源与中文别名
   （`ark:volc/ark`、`公众号:volc/wechat`…）。图标为各品牌官方图形，仅作指示性使用，不重着色、
   不改形、不代表官方背书；来源清单见 `assets/volc/CREDITS.md`。
4. **中文化**：template 字体栈加入 PingFang SC / Noto Sans SC / Microsoft YaHei；节点宽度按
   CJK 字宽自适应；`<html lang>` 按标签语言置 zh-CN。
5. **网页版**：`ark/server.py`（FastAPI）+ `ark/web/index.html`——粘贴一句话，出双主题 PNG /
   自包含 HTML，附示例句按钮与自查徽标。`bash ark/start.sh` 本地运行，API Key 不出本机。
6. **安全加固**：`fetch_icons.py` 的取图请求改为显式 scheme/host 校验（禁内网地址、禁非 http[s]），
   `ark/ark_client.py` 仅连接方舟官方域（常量表，无用户输入可达 URL）；`build.py`/`render_png.py`
   重构出可 import 的 `run()`/`render()` 供进程内调用（CLI 行为不变）。
7. **删除**：`site/`（上游 stacks.caru.moe 画廊的 Cloudflare 工程与配置）、`share.py`（画廊投稿）、
   `.github/workflows/site.yml`——本分支不做画廊，纯本地生成。

## 商标与品牌

图中出现的所有品牌名与 logo 为其各自所有者的商标。本工具按「指示性使用」原则在架构图中指代该
产品本身，不暗示任何背书或关联。若品牌方提出异议，将移除对应图标。
