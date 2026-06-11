# 2026 世界杯 AI 押注大战

四个主流大模型（Claude / DeepSeek / 豆包 / ChatGPT）各持 1000 虚拟币，全程自动押注竞彩足球胜平负，世界杯结束后比较最终余额。

## 启动步骤

**首次运行：**

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（复制后填入真实值）
copy .env.example .env

# 3. 同步赛程（104场，自动转为北京时间）
python main.py sync

# 4. 录入即将开赛的比赛赔率（去 sporttery.cn 查询）
python main.py matches                                    # 找到比赛代码
python main.py update_odds WC2026_001 1.43 4.32 8.11     # 录入赔率

# 5. 启动（两个终端分别运行）
python main.py run           # 终端1：调度器，自动下注+结算
python main.py dashboard     # 终端2：排行榜 http://localhost:5000
```

**日常操作（每场比赛）：**

```bash
# 比赛前：录入赔率（12小时内调度器自动触发下注）
python main.py update_odds <match_code> <主胜赔率> <平局赔率> <客胜赔率>

# 比赛后：录入结果
python main.py settle <match_code> home   # 主队赢
python main.py settle <match_code> draw   # 平局
python main.py settle <match_code> away   # 客队赢
```

---

## 常用命令

```bash
python main.py run                                       # 启动定时调度器（正式运行）
python main.py dashboard                                 # 排行榜网页 http://localhost:5000
python main.py sync                                      # 从 openfootball 同步完整赛程
python main.py matches                                   # 列出所有比赛及赔率状态
python main.py update_odds <match_code> <主胜> <平局> <客胜>  # 录入竞彩赔率
python main.py bet <match_code>                          # 手动触发单场 AI 下注
python main.py settle <match_code> <home|draw|away>      # 手动结算单场
python main.py status                                    # 命令行查看当前排名
```

## 项目结构

```
worldcup2026/
├── config.py               # 所有配置：API Key、规则参数、URL
├── database.py             # SQLite 读写：赛程、下注记录、余额
├── main.py                 # CLI 入口，分发所有子命令
├── odds/
│   └── fetcher.py          # 赛程抓取（openfootball GitHub，无需 Key）
├── agents/
│   ├── base_agent.py       # 公共 Prompt 模板 + JSON 响应解析
│   ├── claude_agent.py     # Anthropic SDK
│   ├── deepseek_agent.py   # OpenAI-compatible SDK，base_url 指向 DeepSeek
│   ├── doubao_agent.py     # OpenAI-compatible SDK，base_url 指向火山引擎
│   └── chatgpt_agent.py    # OpenAI SDK
├── engine/
│   ├── bet_manager.py      # 并发调用四模型，保存下注记录
│   ├── settlement.py       # 赛后结算：更新余额、标记出局
│   └── scheduler.py        # APScheduler：每小时同步、每30min下注+结算
└── dashboard/
    ├── app.py              # Flask 服务
    └── templates/index.html # 排行榜页面（每60秒自动刷新）
```

## 核心规则

| 参数 | 值 |
|------|----|
| 初始余额 | 1000 虚拟币 |
| 单场最低下注 | 10 虚拟币 |
| 单场最高下注 | 当前余额全部（由模型自由决定） |
| 下注截止 | 比赛开赛前 12 小时 |
| 出局条件 | 余额归零 |
| 赔率来源 | 中国竞彩足球胜平负（sporttery.cn） |

## 参赛模型配置

`config.py` 的 `MODELS` 列表由 `_active_models()` 动态生成——只有在 `.env` 中配置了对应 API Key 的模型才会参赛。补充 Key 后重启即生效，无需改代码。

```
ANTHROPIC_API_KEY  → Claude
DEEPSEEK_API_KEY   → DeepSeek
DOUBAO_API_KEY     → 豆包
OPENAI_API_KEY     → ChatGPT
```

豆包还需配置 `DOUBAO_MODEL_ID`（从火山引擎控制台的"推理接入点"获取）。

## 数据来源说明

**赛程**：自动从 [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json) 抓取，免费无需 Key，覆盖全部 104 场，时间自动转换为北京时间。

**赔率**：手动从竞彩网（sporttery.cn）查看后录入，sporttery.cn 需登录无法自动抓取：
```
python main.py update_odds WC2026_001 1.43 4.32 8.11
```

**比赛结果**：手动录入（比赛结束后）：
```
python main.py settle WC2026_001 home
```

调度器和下注逻辑会自动跳过赔率未录入（为 0）的比赛。

## 数据库表

- `matches`：赛程、赔率、比赛结果（status: pending / finished）
- `bets`：每个模型每场的下注记录（唯一约束：match_code + model_name）
- `balances`：四个模型的实时余额、胜负统计、是否出局

## Prompt 设计要点

每次下注前，模型会收到：实时排名、对手余额、当前比赛信息、竞彩赔率、自身余额、剩余场次。模型知道自己的名字和竞争关系，余额归零出局的规则也在 Prompt 中明确告知，以引导博弈行为。
