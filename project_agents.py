# 项目Agent阵容
#
# 每个项目Agent有自己的Brain和认知域。
# 在语义场中通过ISA Chat互动。
#
# 启动:  python3 start_project_agents.py
# 单个:  python3 start_project_agents.py isa

AGENTS = {
    "老搭档": {
        "role": "常驻协作·监督方向·把关质量",
        "keywords": {"协作":0.9, "方向":0.8, "把关":0.7, "质量":0.6},
    },
    "isa": {
        "role": "ISA认知架构 — WaveEngine/Brain/Gateway/Chat",
        "keywords": {"isa":0.9, "波扩散":0.8, "gateway":0.7, "brain":0.6},
    },
    "ios": {
        "role": "IO-S治理系统 — cap_policy/审计/进程管理",
        "keywords": {"ios":0.9, "cap":0.8, "审计":0.7, "治理":0.6},
    },
    "ita": {
        "role": "ITA意图Token架构 — LLM原生语言探针",
        "keywords": {"ita":0.9, "意图":0.8, "token":0.7, "原生语言":0.6},
    },
    "iat": {
        "role": "IAT语言压缩理论 — D₀守恒律/相变实验",
        "keywords": {"iat":0.9, "压缩":0.8, "守恒律":0.7, "d0":0.6},
    },
    "iah": {
        "role": "IAH注意力解剖 — D₀测量/attention head分类",
        "keywords": {"iah":0.9, "注意力":0.8, "解剖":0.7, "d0":0.6},
    },
    "idc": {
        "role": "IDC三系统 — 记忆/技能/治理理论框架",
        "keywords": {"idc":0.9, "三系统":0.8, "理论":0.7, "框架":0.6},
    },
    "iko": {
        "role": "IKO交付管线 — 资产→发布→传播",
        "keywords": {"iko":0.9, "交付":0.8, "发布":0.7, "管线":0.6},
    },
    "搜神": {
        "role": "情报搜索 — 随时待命·查文献·搜资料",
        "keywords": {"搜神":0.9, "搜索":0.8, "情报":0.7, "文献":0.6},
    },
}
