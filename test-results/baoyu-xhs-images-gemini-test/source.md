根据您提供的来源资料，以下是整理好的 **香港虚拟资产交易反洗钱风控配置指南** 的 Markdown 文档：

***

# 香港虚拟资产交易反洗钱风控配置指南

这是一份为受香港证监会（SFC）监管的持牌虚拟资产交易平台（VATP）及 OTC 交易商定制的 TrustIn KYA Pro 配置策略白皮书。
本策略严格遵循香港**《打击洗钱及恐怖分子资金筹集条例》(AMLO, Cap. 615)** 及证监会发布的**《打击洗钱及恐怖分子资金筹集指引》(SFC AML Guideline)**。

### 1. 监管背景与核心合规义务

*   **适用主体** ：持有 SFC 第 1/7 类牌照的交易所、根据 AMLO 申领 VASP 牌照的平台，以及从事 OTC 业务的持牌法团。
*   **核心法规** ：
    *   **SFC AML Guideline (2023)** ：适用于持牌法团及获发牌的虚拟资产服务提供者。
    *   **AMLO (Cap. 615)** ：打击洗钱及恐怖分子资金筹集条例。
*   **关键合规痛点** ：资金来源审查 (Source of Funds)、转账规则 (Travel Rule)、制裁筛查 (Sanctions Screening) 及持续监控 (Ongoing Monitoring)。

---

### 2. TrustIn KYA Pro 规则引擎配置 (Rule Engine Configuration)

针对 OTC 及机构业务大额、高频的特点，建议在 TrustIn KYA Pro 中配置以下策略。

#### 2.1 入金审查 (Inflow Rules) - 识别“脏币”与资金来源

**监管依据** ：SFC AML Guideline 第 4.1.9 及 12.7 段要求对客户进行尽职调查，并采取合理措施确立资金来源 (Source of Funds)，特别是识别由于匿名性高、混币器或欺诈相关的风险。

| 参数项 (Parameter) | 建议设定 (Recommended Setting) | 逻辑说明与合规依据 (Rationale & Source) |
| :--- | :--- | :--- |
| **Trace Direction** | **Inflow** (资金来源) | 追溯资金上游，识别入金是否存在风险。 |
| **Trace Depth** | **5 Hops (5层)** | **穿透剥离链 (Peel Chains)** ：洗钱者常利用多层转账清洗资金。SFC 强调需识别与非法活动相关的钱包地址。5层深度为行业高标准，能有效穿透复杂的洗钱路径。 |
| **Risk Category: Severe** | **Sanctions, Terrorist Financing** | **Risk Score > 0 (零容忍)** ：根据 UNATMO 及 UNSO，严禁处理受制裁资金。一旦发现任何关联，立即冻结。 |
| **Risk Category: High** | **Mixers, Darknet, Ransomware, Hacks** | **Risk Score > 0 (零容忍)** ：SFC 特别指出混币器 (Mixers) 和暗网市场属于高风险指标。建议直接拒绝此类资金入金。 |
| **Risk Category: Medium** | **Gambling, High Risk Exchange** | **Risk Score > 30% AND Amount > $1,000** ：对于博彩或高风险交易所来源，若占比过高，需执行 EDD（增强尽职调查），要求客户解释资金来源。 |
| **Whitelist** | **Enable (开启)** | 将 Binance, Kraken 等持牌/合规交易所的热钱包加入白名单。系统遇到白名单地址将停止穿透，避免因交易所热钱包关联复杂产生的误报。 |

#### 2.2 出金/转账监控 (Outflow Rules) - Travel Rule 与制裁筛查

**监管依据** ：
*   **Travel Rule** ：SFC AML Guideline 第 12.11 段规定，转账金额 ≥ HKD 8,000 时，必须传递发起人和接收人信息。
*   **制裁合规** ：防止资金流向受制裁实体或恐怖组织。

| 参数项 (Parameter) | 建议设定 (Recommended Setting) | 逻辑说明与合规依据 (Rationale & Source) |
| :--- | :--- | :--- |
| **Trace Direction** | **Outflow** (资金去向) | 监控提币目标地址及其下游。 |
| **Trace Depth** | **2-3 Hops** | 重点监控直接接收方及次级接收方，防止资金经由跳板流向制裁实体。 |
| **Travel Rule Threshold** | **> USD 1,000 (约 HKD 7,800)** | **系统预警线** ：虽然法规为 HKD 8,000，建议设为 USD 1,000 以缓冲汇率波动。触发此阈值时，系统强制要求填写 Travel Rule 信息 (IVMS101 标准)。 |
| **Unhosted Wallet** | **Risk Level: High (需额外核实)** | **非托管钱包风险** ：SFC AML Guideline 第 12.14 段要求，对于与非托管钱包 (Unhosted Wallet) 的转账，必须评估风险并采取额外措施（如所有权验证/Satoshi Test）。 |
| **Sanctions Screening** | **Global Lists + HK Lists** | 必须筛查 UN 及香港宪报刊登的制裁名单。 |

#### 2.3 交互行为检测 (Interaction Rules) - 识别异常交易模式

**监管依据** ：SFC AML Guideline 第 5.10 段及附录 B，要求识别复杂、异常大额或无明显经济目的的交易。

| 规则名称 (Rule Name) | 阈值设置 (Threshold) | 触发等级 | 应对措施 |
| :--- | :--- | :--- | :--- |
| **Structuring (拆分交易)** | 单日累计 > USD 10,000 但单笔 < USD 1,000 | 🟠 High | **防范 Smurfing** ：识别试图规避 Travel Rule 或 CDD 门槛的“蚂蚁搬家”行为。需提交 STR（可疑交易报告）。 |
| **Rapid Movement (快进快出)** | 资金入账后 1 小时内全额转出 | 🟡 Medium | SFC 附录 B 指出“资金存入后立即转出”为可疑指标。需人工复核交易目的。 |
| **New/Inactive Wallet** | 目标地址为新创建或长期休眠 | 🟡 Medium | 防止勒索软件攻击或诈骗资金转移。 |

---

### 3. 事后监控配置 (Ongoing Monitoring Configuration)

**监管依据** ：SFC AML Guideline 第 5 章及 12.7 段要求对业务关系进行持续监控，包括定期审查客户资料和持续监控交易。

#### 3.1 钱包地址持续回溯 (Wallet Screening)
在 TrustIn 中开启 **"Ongoing Monitoring"** 功能，针对已建立业务关系的白名单地址进行 7x24 小时监控。
*   **监控对象** ：所有通过 KYC 的 OTC 客户白名单地址。
*   **触发机制 (Trigger Events)** ：
    *   **Sanctions Hit** ：当地址被新列入 UN/OFAC 制裁名单时，系统需在 24 小时内报警。
    *   **Risk Profile Change** ：当某个客户地址的风险评分从 Low 变为 High/Severe（例如该地址卷入新的黑客事件）。
    *   **Unexpected Interaction** ：当客户地址突然与暗网或混币器产生交互。

#### 3.2 监控频率与报告
*   **高风险客户 (High Risk/PEP)** ：每日扫描 (Daily)。
*   **标准客户** ：每周扫描或交易发生时实时扫描。
*   **报告留存** ：系统生成的风险警报和处理记录必须保存至少 **5 年**。

---

### 4. 监控阈值配置汇总表 (Configuration Summary)

| 模块 (Module) | 参数 (Key Parameter) | 设定值 (Value) | 对应 SFC 合规要求 (Source) |
| :--- | :--- | :--- | :--- |
| **Inflow** | 穿透深度 (Trace Depth) | **5 Hops** | 识别 Peel Chains / Layering |
| **Inflow** | 混币器容忍度 (Mixer Tolerance) | **0% (Reject)** | 针对匿名性风险 (SFC 12.15.2) |
| **Outflow** | Travel Rule 触发金额 | **> USD 1,000** | 对应 HKD 8,000 门槛 (SFC 12.11) |
| **Outflow** | 非托管钱包 (Unhosted Wallet) | **Enable "Proof of Ownership"** | 针对非托管钱包的额外措施 (SFC 12.14) |
| **Identity** | 制裁名单 (Sanctions List) | **UN + HK Gazette** | 满足 UNATMO/UNSO 要求 |
| **Interaction** | 大额交易 (Large Transaction) | **> HKD 120,000 (约 $15k)** | 对应偶然交易 CDD 门槛 (SFC 4.1.9) |

---

### 5. 操作流程 (SOP) 建议

1.  **Pre-Trade (交易前)** ：
    *   OTC 交易员收到客户地址后，输入 TrustIn KYA Pro 进行扫描。
    *   若 Risk Level 为 **Severe** -> **拒绝交易** ，并上报合规部（考虑提交 STR）。
    *   若 Risk Level 为 **High** -> 检查是否涉及混币器。若涉及，要求客户提供有力解释（资金来源证明）；否则拒绝。
2.  **During-Trade (交易中)** ：
    *   若提币金额 > USD 1,000，系统自动检查是否收集了 Beneficiary VASP 信息。
    *   若目标为 Unhosted Wallet，启动所有权验证流程（如 Satoshi Test）。
3.  **Post-Trade (交易后)** ：
    *   将客户地址加入 TrustIn 的 **Ongoing Monitoring** 列表。
    *   定期（如每月）导出监控报告，作为合规审计底稿。

通过以上配置，贵司可确保满足香港 SFC 对虚拟资产交易的严格反洗钱要求，有效规避合规风险。