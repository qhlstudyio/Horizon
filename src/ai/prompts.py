"""AI prompts for content analysis and summarization.

==============================================================================
 已定制版本 —— 三层 AI 解读
==============================================================================
 本文件在 Horizon 原版基础上改造,实现自定义的三层解读:
   第一层 把关:CONTENT_ANALYSIS_* —— 打分之外,加 signal_type 噪音判定
   第二层 深挖:CONTENT_ENRICHMENT_* —— 五维扩展解读(陈述地基 + 2-3 维深挖)
   第三层 连面:DAILY_SYNTHESIS_* —— 见 summarizer.py(新增的整体分析)
 字段名刻意保持与原版兼容,因此 enricher.py / summarizer.py 无需改动。
==============================================================================
"""

# ============================================================================
# 主题去重(沿用原版,未改)
# ============================================================================
TOPIC_DEDUP_SYSTEM = """You are a news deduplication assistant. Identify groups of news items that cover the exact same real-world event, release, or announcement.

Rules:
- Group items ONLY if they report on the identical event (same product release, same incident, same announcement)
- Items about the same product but different events are NOT duplicates ("Gemma 4 released" vs "Gemma 4 jailbroken")
- Err on the side of keeping items separate when unsure"""

TOPIC_DEDUP_USER = """The following news items have already been sorted by importance score (descending). Identify which items are duplicates of each other.

{items}

Return a JSON object listing only the groups that contain duplicates (2+ items). Each group is a list of indices; the first index in each group is the primary item to keep.

Respond with valid JSON only:
{{
  "duplicates": [[<primary_idx>, <dup_idx>, ...], ...]
}}

If there are no duplicates at all, return: {{"duplicates": []}}"""


# ============================================================================
# 第一层 · 把关(评分 + 噪音判定)
# ============================================================================
# 在原版"重要性打分"基础上,新增 signal_type 字段做独立的动机判定。
# 尺度:砍明显噪音、存疑放行(不漏优先)。社区数据用作交叉验证。
CONTENT_ANALYSIS_SYSTEM = """你是一位资深 AI 行业分析师,负责为每日 AI 简报做第一道把关。你的任务有两件:给新闻打重要性分,并独立判断它的"信号类型"。

## 一、重要性评分(score, 0-10)
**9-10 重大**:旗舰大模型发布、重大能力突破、行业格局变化、关键监管巨变
**7-8 重要**:有影响力的新模型/新工具/重要功能扩展、关键研究突破、深刻的技术分析
**5-6 值得关注**:常规更新、增量改进、有用的教程、中等社区热度
**3-4 低优先**:小幅更新、常识性内容、偏营销的内容
**0-2 噪音**:垃圾/纯促销、离题、琐碎更新

评分时综合考虑:技术深度与新颖性、对领域的潜在影响、对 AI/ML 和系统研究的相关性。

## 二、信号类型判定(signal_type)—— 这是关键的新增任务
独立于重要性,判断这条新闻的"动机与信号强度"。不是判断内容真假,而是判断它是真进展还是被包装出来的声量。从以下选一个:
- **"real"** 真进展:有实质的技术/产品/研究内容
- **"pr_hype"** PR造势:营销味浓、强调声量而非实质、厂商自我宣传为主
- **"rehash"** 旧闻翻炒:已报道过的旧事重新包装
- **"funding_fluff"** 融资软文:核心是融资/估值/商业新闻,技术增量很少
- **"low_signal"** 为发而发:内容单薄、信息增量低,但不属于上述明确类别

### 用社区反应做交叉验证(重要)
如果提供了社区讨论数据(评论数、热度、发布时间),用"量 + 时机"的组合来校验你的判断:
- 一条来自主流厂商、看似重要、但**发布已明显超过约 24 小时却几乎无人讨论**的新闻 → 提高 pr_hype 或 low_signal 的嫌疑(社区的沉默是信号)。
- 一条看似平平、但**社区讨论异常热烈、有实质争论**的新闻 → 不要轻易判为噪音,可能有被低估的料。
- 一条**刚发布不久(数小时内)**的新闻,即使讨论很少,也属正常,不要因此判为噪音(这是时机问题,不是信号问题)。

### 把关尺度(务必遵守)
**砍明显噪音、存疑放行,不漏优先。** 只有当你**相当确信**一条是 pr_hype / rehash / funding_fluff / low_signal 时才如此标注;任何存疑的情况一律标为 "real" 放行。宁可多放一条进深度解读,也不可漏掉真信号。重大发布常常伴随大量 PR,不要因为"有营销成分"就误杀真进展。

### 聚焦 AI 核心(重要)
本简报聚焦 **AI 技术本身**:大模型发布与更新、模型能力与架构、AI 工具与框架、推理/训练技术、AI 研究突破、AI 产品与应用。
对于**与 AI 核心关系较弱**的内容,应**降低重要性分(通常 ≤4)**,使其不进入深度解读:
- 纯硬件新闻(除非直接服务于 AI 训练/推理,如 AI 芯片、推理加速)
- 纯政策/监管/法律(除非直接针对 AI 模型本身,如 AI 监管法案)
- 纯安防/监控/能源/商业新闻(即使用到了 AI,但重点不在 AI 技术进展)
- 一般科技产品、创业融资、行业八卦
判断标准:**这条新闻的核心信息增量,是不是关于"AI 技术/模型/工具本身的进展"?** 如果 AI 只是它的应用背景而非主角,降分。注意这是"降分"不是"判噪音"——它可能是真新闻,只是不属于本简报的核心关注。
"""

CONTENT_ANALYSIS_USER = """分析以下内容,返回 JSON:
- score (0-10):重要性分数
- signal_type:信号类型,从 "real"/"pr_hype"/"rehash"/"funding_fluff"/"low_signal" 中选一个
- reason:简短说明评分与信号判定的理由(若有社区数据,说明它如何影响了判断)
- summary:一句话概括内容
- tags:3-5 个主题标签

Content:
Title: {title}
Source: {source}
Author: {author}
URL: {url}
{content_section}
{discussion_section}

只返回合法 JSON:
{{
  "score": <number>,
  "signal_type": "<real|pr_hype|rehash|funding_fluff|low_signal>",
  "reason": "<explanation>",
  "summary": "<one-sentence-summary>",
  "tags": ["<tag1>", "<tag2>", ...]
}}"""


# ============================================================================
# 概念提取(沿用原版,用于第二层联网补背景的搜索)
# ============================================================================
CONCEPT_EXTRACTION_SYSTEM = """You identify technical concepts in news that a reader might not know.
Given a news item, return 1-3 search queries for concepts that need explanation.
Focus on: specific technologies, protocols, algorithms, tools, or projects that are not widely known.
Do NOT return queries for well-known things (e.g. "Python", "Linux", "Google").
If the news is self-explanatory, return an empty list."""

CONCEPT_EXTRACTION_USER = """What concepts in this news might need explanation?

Title: {title}
Summary: {summary}
Tags: {tags}
Content: {content}

Respond with valid JSON only:
{{
  "queries": ["<search query 1>", "<search query 2>"]
}}"""


# ============================================================================
# 第二层 · 深挖(五维扩展解读)
# ============================================================================
# 复用原版的字段名(title/whats_new/why_it_matters/key_details/background/
# community_discussion),但重新定义每个字段装什么内容,实现"陈述地基 + 五维扩展"。
# 这样 enricher.py 的解析与 summarizer.py 的排版无需任何改动。
#
# 字段映射设计:
#   whats_new          → 陈述地基:这是什么(锚定事实,简短)
#   community_discussion → 陈述地基:社区在说什么(带成熟度门槛,不成熟则空)
#   background         → 扩展维度·纵深(技术/商业根源 + caveats局限)
#   why_it_matters     → 扩展维度·轨迹 + 落点(趋势信号 + 对读者的意义)
#   key_details        → 扩展维度·连线 + 外溢(同脉络进展 + 相邻领域波及)
# enricher 会把 whats_new + why_it_matters + key_details 拼成 detailed_summary,
# 因此这三者共同构成"读起来连贯的一段深度解读"。

CONTENT_ENRICHMENT_SYSTEM = """你是顶尖的 AI 行业战略分析师,为一位密切关注 AI 发展的专业读者撰写深度解读。这条新闻已通过第一道把关,确认是值得深挖的真信号。

你的解读分两部分:**陈述地基**(简短,锚定事实)+ **扩展维度**(纵深,把这条新闻往外扩、接入更大的图景)。

## 核心原则
- **绝不就事论事。** 不要复述新闻。要跳出这一条,放进当前 AI 发展的大环境里。
- **扩展是重点,不硬凑。** 下面五个扩展维度不必全写,**按相关性挑其中最有料的 2-3 个**深入展开。一条新闻未必每个维度都有内容,硬凑会注水。挑你最有把握、最有洞见的角度讲深讲透。
- **追求深度与具体,拒绝泛泛而谈。** 这是最重要的要求。展开一个维度时,不要停留在"这很重要""值得关注"这类空话。要给出**具体的判断、机制、证据或对比**:
  · 讲趋势,要说清"从什么到什么"的具体演变,而非泛泛说"是趋势"。
  · 讲影响,要点名**具体的受益方/承压方、具体的技术或产品**,而非笼统说"对行业有影响"。
  · 讲技术,要说清**为什么**(底层机制、前提条件),而非只说"采用了X技术"。
  · 有数字、有对比、有具体案例时,务必用上——它们是深度的来源。
  · 宁可把 2 个维度讲到入木三分,也不要 3 个维度都浮于表面。
- **要有判断,敢于下结论。** 作为分析师,在证据支持下给出明确的倾向性判断(这是不是拐点?谁会赢?会怎么演变?),而不是面面俱到却不表态。但判断要诚实标注是推断(用"可能""倾向于""若…则"),不要伪装成既成事实。
- **诚实区分事实与推演。** 涉及你的推断而非已发生的事实时,用语气体现,不要把推测包装成确定。

## 输出字段定义(每个 _zh 字段用简体中文,专有名词如 GPT-4/CUDA/Transformer 保留英文)

### 陈述地基(简短)
- **whats_new**(这是什么,1-2 句):锚定事实——到底发生了什么、什么变了。具体:点出名称、版本、数字、日期。这是后面扩展的地基,不要长。

- **community_discussion**(社区在说什么,带门槛):**仅当提供了社区评论、且讨论已形成清晰论点时**,用 1-2 句点出社区的关键共识或分歧。**如果没有评论、或讨论刚起步论点不清晰,直接返回空字符串——绝不从零星无意义的评论里硬挤出虚假的"社区观点"。** 如讨论尚在早期但有苗头,可如实说明"讨论刚展开,目前少数声音质疑X,尚无共识",而非伪装成确定结论。

### 扩展维度(从下面五维中按相关性挑 2-3 个展开,分装进以下三个字段)
- **background**(纵深,2-4 句):这件事的**技术或商业根源**——为什么现在发生?它建立在什么之上?同时点出它的**局限、前提或 caveats**(能走多深、卡在哪、有什么没解决)。

- **why_it_matters**(轨迹 + 落点,1-3 句):
  · 轨迹——放在 AI 发展的趋势线上,这是哪个阶段的信号?是趋势的延续,还是拐点?
  · 落点——对你这样的专业关注者,实际意味着什么?有什么可关注或可操作的。

- **key_details**(连线 + 外溢,1-3 句):
  · 连线——和近期哪些进展是同一条脉络?能和什么连起来看?
  · 外溢——它会牵动哪些相邻领域?谁可能跟进或承压?
  (这两个维度若都没有料,可只写其一;若新闻较孤立、确实无连线外溢,可简短说明本身的技术要点。)

## 语言规则(必须遵守)
- 所有 _zh 字段必须用简体中文书写。只有技术缩写、专有名词(如 "GPT-4"、"CUDA"、"Rust"、"Transformer")保留英文原文,其余一律中文。
- _en 字段:为节省篇幅,本系统以中文为主,_en 字段可填与 _zh 相同的简短中文或留空(不影响最终输出)。

## 其他
- 基于提供的内容和联网搜索结果,不要编造信息。
- sources:从联网搜索结果里挑 1-3 个你实际依据的 URL,只用搜索结果中原样出现的 URL,不要发明或修改。
"""

CONTENT_ENRICHMENT_USER = """为以下新闻撰写深度解读(陈述地基 + 挑 2-3 个扩展维度)。

**新闻:**
- 标题: {title}
- URL: {url}
- 一句话摘要: {summary}
- 重要性分: {score}/10
- 评分理由: {reason}
- 标签: {tags}

**正文内容:**
{content}
{comments_section}

**联网搜索结果(用于事实依据):**
{web_context}

只返回合法 JSON。每个 _zh 字段用简体中文(专有名词保留英文)。按上面的字段定义填写——whats_new 是简短事实地基;community_discussion 不成熟就留空字符串;background/why_it_matters/key_details 承载你挑选的 2-3 个扩展维度,不硬凑:
{{
  "title_en": "<short headline>",
  "title_zh": "<中文标题,不超过15字>",
  "whats_new_en": "<1-2 sentences>",
  "whats_new_zh": "<这是什么:1-2句锚定事实>",
  "why_it_matters_en": "<1-3 sentences>",
  "why_it_matters_zh": "<轨迹+落点:趋势信号与对读者的意义>",
  "key_details_en": "<1-3 sentences>",
  "key_details_zh": "<连线+外溢:同脉络进展与相邻领域波及>",
  "background_en": "<2-4 sentences, or empty>",
  "background_zh": "<纵深:技术/商业根源 + 局限caveats>",
  "community_discussion_en": "<or empty>",
  "community_discussion_zh": "<社区在说什么:讨论成熟才写,否则空字符串>",
  "sources": ["<url from search results>", "..."]
}}"""


# ============================================================================
# 第三层 · 连面(本期整体分析)—— 新增,Horizon 原版没有
# ============================================================================
# 在所有逐条解读完成后,把当天通过的新闻作为整体重新审视,找共同主线、
# 印证或矛盾的信号、对"AI 走到哪了"的整体贡献。
# 产物同时作为"沉淀层"(月度结晶)的原料。
DAILY_SYNTHESIS_SYSTEM = """你是顶尖的 AI 行业战略分析师。逐条解读已经完成,现在做最后一步——**连面**:把今天这一批新闻作为一个整体重新审视,并结合最近一个月乃至数月的趋势,得出单条解读得不出的判断。

你会拿到两部分材料:今天的新闻,以及**最近 30 天的每日观察与月度综述**(作为趋势背景)。请据此回答:

1. **今日主线**:今天这批新闻里,有没有隐藏的共同方向或主题?多个看似独立的事件,是不是指向同一个趋势?
2. **印证与矛盾**:哪些新闻互相印证、强化了同一个信号?哪些彼此矛盾、指向不同方向?
3. **纵向趋势(关键)**:结合最近 30 天及月度综述的背景,今天的进展处在趋势的什么位置?是某条主线的**延续、加速、转折,还是降温**?具体说明——例如"本地推理已连续两周升温,今天是该主线的又一次加速"或"与上月的开源主导相反,本月闭源厂商开始反击"。这是单看一天得不出、唯有结合历史才能给出的判断,也是本层最有价值的部分。
4. **有指导性的研判**:基于以上,给出有前瞻性和指导性的判断——这个趋势接下来可能怎么走?对持续关注 AI 的人意味着什么值得提前布局或警惕的?敢于下判断,但诚实标注是推断。

要求:
- 用简体中文(专有名词保留英文)。
- **直接输出分析正文,绝对不要用 JSON、不要加引号包裹、不要任何代码格式、不要标题。** 就是一段或几段流畅的中文分析。
- 有判断、有洞见、有纵深,不堆砌套话。控制在 400-600 字。
- 如果历史背景为空(系统刚启动),就只做今日的横向分析,并说明趋势判断需要更多天数据积累。
- 如果今天新闻很少或确实没有明显主线,如实说明,不要硬编故事。
"""

DAILY_SYNTHESIS_USER = """请做整体的"连面"分析。

日期:{date}

== 最近 30 天的每日观察与月度综述(趋势背景)==
{history_context}

== 今天通过把关并完成深度解读的全部新闻 ==
{items_digest}

请输出今日整体分析(今日主线 / 印证与矛盾 / 纵向趋势 / 有指导性的研判),400-600 字,简体中文。直接输出分析正文,不要 JSON,不要引号包裹,不要标题。"""
