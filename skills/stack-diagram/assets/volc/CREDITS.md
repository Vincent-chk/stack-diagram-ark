# volc icon pack — 火山生态 + 中文常用栈官方图标

8 枚官方品牌图形，供 `fetch_icons.py` 的 `volc/` 本地源使用。**指示性使用（nominative
use）：仅用于在架构图中指代该产品本身；不重着色、不裁切改形、不代表任何官方背书。**
商标归各品牌方所有。若有品牌方提出异议，将立即移除对应文件。

| slug | 指代 | 文件 | 来源（2026-11-05 抓取） |
|---|---|---|---|
| volcengine | 火山引擎（方舟/HiAgent/AgentKit 等子产品共用厂商标） | volcengine.png 192×192 | https://portal.volccdn.com/obj/volcfe/misc/favicon.png （官网 favicon） |
| doubao | 豆包（含 Seed 系模型） | doubao.png 192×192 | https://lf-flow-web-cdn.doubao.com/obj/flow-doubao/favicon/new-doubao/192x192.png （官网 favicon） |
| coze | 扣子 Coze | coze.jpg 512×512 | App Store「扣子 - 开启全新 Agent 体验」官方应用图标 |
| trae | TRAE | trae.png 48×48 | https://lf16-web-neutral.traecdn.ai/obj/trae-ai-static/trae_website/favicon.png （官网 favicon；**官方最大尺寸即 48×48**——2026-11-05 实测海外站/中国站 CDN、App Store 均无更高清版本，34px 磁贴显示 1.4 倍余量够用，仅 2x retina 屏略软） |
| feishu | 飞书 | feishu.png 512×512 | https://www.feishu.cn/ og:image（飞书官方 CDN，黑底彩标） |
| wechat | 微信 / 公众号 | wechat.jpg 512×512 | App Store「微信」官方应用图标 |
| douyin | 抖音 | douyin.jpg 512×512 | App Store「抖音」官方应用图标 |
| xiaohongshu | 小红书 | xiaohongshu.jpg 512×512 | App Store「小红书 - 你的生活兴趣社区」官方应用图标 |

别名（`fetch_icons.py` 内 VOLC_ALIASES，同一图形的多称呼）：
- `ark` `hiagent` `agentkit` `volc` `火山` `火山引擎` `方舟` → volcengine（子产品无独立
  logo 时按上游惯例复用厂商标，节点名携带产品区分）
- `seed` `豆包` → doubao
- `扣子` `coze` → coze；`飞书` `lark` → feishu；`微信` `公众号` `weixin` → wechat；
  `抖音` → douyin；`小红书` `rednote` → xiaohongshu

取图时 svgl/devicon/gilbarbara 对上述所有品牌均无收录（实测 2026-11-05），这正是本图标包
存在的原因。
