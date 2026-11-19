from __future__ import annotations

from pathlib import Path

from app.core.config import settings

"""知识模块的静态数据：项目路径、课程领域词表、概念噪声词、默认图谱与边。"""

PROJECT_ROOT = Path(__file__).resolve().parents[3]


PROJECT_MATERIALS_DIR = PROJECT_ROOT / "项目资料"


def _material_path(*parts: str) -> Path:
    """Prefer the organized project-materials folder, with old paths as fallback."""
    organized = PROJECT_MATERIALS_DIR.joinpath(*parts)
    if organized.exists():
        return organized
    return PROJECT_ROOT.joinpath(*parts)


COURSE_DIR = _material_path("课程资料")


SAMPLE_DIR = _material_path("生成示例")


PATH_OUTPUT_DIR = _material_path("第三点_学习路径规划与资源推送", "输出结果")


def _textbook_dir() -> Path:
    """Resolve uploads from the active runtime data directory, including roadshow copies."""
    return settings.data_path / "uploads" / "textbooks"


def _chapter_knowledge_dir() -> Path:
    return _textbook_dir() / "chapter_knowledge"


GRAPH_DOMAIN_CONCEPTS = (
    "C语言", "数据类型", "变量", "常量", "运算符", "流程控制", "条件语句", "循环语句",
    "函数", "数组", "指针", "结构体", "文件操作", "预处理", "内存管理", "算法", "程序调试",
    "HTML5", "CSS3", "JavaScript", "DOM", "BOM", "语义化标签", "表单", "Canvas", "SVG",
    "Flexbox", "Grid布局", "响应式设计", "事件处理", "Ajax", "WebSocket", "Web Storage",
    "IndexedDB", "动画", "多媒体",
    "Java虚拟机", "JVM", "类加载机制", "运行时数据区", "堆", "栈", "方法区", "垃圾回收",
    "垃圾收集器", "字节码", "JIT", "HotSpot", "双亲委派", "Java内存模型", "性能调优",
    "常量池", "方法调用", "对象创建", "逃逸分析",
    "PHP", "MySQL", "面向对象", "异常处理", "数据库连接", "SQL", "索引", "事务", "查询优化",
    "缓存", "会话管理", "数据库安全",
    "Python", "NumPy", "pandas", "Matplotlib", "数据获取", "数据清洗", "数据预处理",
    "数据分析", "数据可视化", "缺失值", "异常值", "数据聚合", "时间序列",
    "SQL Server", "性能监控", "查询计划", "锁", "死锁", "等待事件", "性能计数器",
    "动态管理视图", "数据库诊断", "备份恢复",
    "区块链", "哈希函数", "数字签名", "共识机制", "工作量证明", "智能合约", "分布式账本",
    "P2P网络", "Merkle树", "比特币", "以太坊", "隐私保护",
    "操作系统", "进程", "线程", "进程调度", "虚拟内存", "文件系统", "中断", "系统调用",
    "设备管理", "同步互斥", "线程同步", "线程互斥", "定时处理", "系统总线", "设备驱动",
    "图形用户界面", "内核", "启动引导", "MBR", "BIOS",
    "数据通信", "信号", "信道", "编码", "调制", "复用", "差错控制", "流量控制", "OSI",
    "TCP/IP", "物理层", "数据链路层", "网络层", "传输层",
    "嵌入式系统", "实时操作系统", "任务调度", "中断处理", "设备驱动", "启动流程",
    "资源管理", "交叉编译", "BSP",
    "物联网", "感知层", "应用层", "传感器", "RFID", "ZigBee", "MQTT", "边缘计算",
    "云计算", "设备接入", "数据采集",
    "安全需求", "威胁建模", "身份认证", "访问控制", "输入验证", "安全编码", "漏洞分析",
    "代码审计", "渗透测试", "加密", "SQL注入", "跨站脚本",
    "软件工程", "软件过程", "需求工程", "需求分析", "用例建模", "软件设计", "体系结构",
    "详细设计", "软件测试", "软件维护", "配置管理", "项目管理", "质量保证", "UML", "敏捷开发",
    "机器学习", "监督学习", "无监督学习", "回归", "分类", "聚类", "特征工程", "模型训练",
    "模型评估", "过拟合", "交叉验证", "决策树", "支持向量机", "神经网络", "scikit-learn",
)


GRAPH_KEYWORD_NOISE_MARKERS = (
    "isbn", "丛书序", "推荐序", "序言", "前言", "内容简介", "作者简介", "译者简介", "编者",
    "出版社", "出版日期", "版权所有", "版权声明", "开发经验丰富", "技术扎实", "职场点拨",
    "疑难问题解", "同事关系", "考虑跳槽", "配套资源下载", "扫码", "二维码", "微信公众号",
    "官方网站", "电子邮箱", "如图所示", "代码清单", "本书", "本章", "读者",
)


GRAPH_GENERIC_TERMS = {
    "一个", "一种", "进行", "实现", "系统", "功能", "主要", "相关", "概述", "介绍", "介绍了",
    "定义", "认识", "目前", "所示", "如图", "内容", "方法", "技术", "特点", "区别", "使用",
    "生成", "开发", "安装", "过程", "应用", "窗口", "管理", "虚拟", "数据", "环境", "运行",
    "机制", "文件",
    "代码", "清单", "基础", "原理", "实践", "小结", "章介绍", "本章小", "子模", "小菜",
    "china", "hello", "turbo", "flash", "downloads", "export", "home", "return", "function",
    "echo", "array", "empty", "null", "true", "false", "https", "http", "br", "ll", "oo", "is",
}


GRAPH_CONCEPT_SUFFIXES = (
    "语言", "类型", "控制", "语句", "函数", "数组", "指针", "结构", "操作", "处理", "管理",
    "算法", "模型", "机制", "架构", "体系", "设计", "编程", "系统", "开发", "过程", "方法",
    "原则", "需求", "测试", "维护", "配置", "工程", "数据库", "网络", "安全", "协议", "线程",
    "进程", "内存", "文件", "调度", "通信", "编码", "调制", "复用", "控制", "视图", "分析",
    "监控", "诊断", "评估", "训练", "学习", "计算", "验证", "审计", "签名", "合约", "账本",
)


GRAPH_COURSE_CONCEPT_HINTS = (
    (("c语言", "手把手教你学c"), (
        "C语言", "数据类型", "变量", "常量", "运算符", "流程控制", "条件语句", "循环语句",
        "函数", "数组", "指针", "结构体", "文件操作", "预处理", "内存管理", "算法", "程序调试",
    )),
    (("html5", "web前端", "javascript"), (
        "HTML5", "CSS3", "JavaScript", "DOM", "BOM", "语义化标签", "表单", "Canvas", "SVG",
        "Flexbox", "Grid布局", "响应式设计", "事件处理", "Ajax", "WebSocket", "Web Storage",
        "IndexedDB", "动画", "多媒体",
    )),
    (("java虚拟机", "jvm"), (
        "Java虚拟机", "JVM", "类加载机制", "运行时数据区", "堆", "栈", "方法区", "垃圾回收",
        "垃圾收集器", "字节码", "JIT", "HotSpot", "双亲委派", "Java内存模型", "性能调优",
        "常量池", "方法调用", "对象创建", "逃逸分析",
    )),
    (("php", "mysql"), (
        "PHP", "MySQL", "函数", "数组", "面向对象", "异常处理", "数据库连接", "SQL", "索引",
        "事务", "查询优化", "缓存", "会话管理", "数据库安全", "输入验证", "SQL注入",
    )),
    (("python数据分析", "数据获取到可视化"), (
        "Python", "NumPy", "pandas", "Matplotlib", "数据获取", "数据清洗", "数据预处理",
        "数据分析", "数据可视化", "缺失值", "异常值", "数据聚合", "时间序列", "机器学习",
    )),
    (("sqlserver", "sql server", "监控和诊断"), (
        "SQL Server", "SQL", "性能监控", "查询计划", "索引", "锁", "死锁", "事务", "等待事件",
        "性能计数器", "动态管理视图", "数据库诊断", "备份恢复", "查询优化",
    )),
    (("区块链",), (
        "区块链", "哈希函数", "数字签名", "共识机制", "工作量证明", "智能合约", "分布式账本",
        "P2P网络", "Merkle树", "比特币", "以太坊", "隐私保护",
    )),
    (("操作系统",), (
        "操作系统", "进程", "线程", "进程调度", "内存管理", "虚拟内存", "文件系统", "中断",
        "系统调用", "设备管理", "同步互斥", "线程同步", "线程互斥", "定时处理", "系统总线",
        "设备驱动", "图形用户界面", "死锁", "内核", "启动引导", "MBR", "BIOS",
    )),
    (("嵌入式",), (
        "嵌入式系统", "实时操作系统", "任务调度", "中断处理", "设备驱动", "启动流程", "内核",
        "资源管理", "交叉编译", "BSP",
    )),
    (("数据通信",), (
        "数据通信", "信号", "信道", "编码", "调制", "复用", "差错控制", "流量控制", "OSI",
        "TCP/IP", "物理层", "数据链路层", "网络层", "传输层",
    )),
    (("物联网",), (
        "物联网", "感知层", "网络层", "应用层", "传感器", "RFID", "ZigBee", "MQTT",
        "边缘计算", "云计算", "设备接入", "数据采集",
    )),
    (("软件安全",), (
        "安全需求", "威胁建模", "身份认证", "访问控制", "输入验证", "安全编码", "漏洞分析",
        "代码审计", "渗透测试", "加密", "SQL注入", "跨站脚本",
    )),
    (("软件工程",), (
        "软件工程", "软件过程", "需求工程", "需求分析", "用例建模", "软件设计", "体系结构",
        "详细设计", "软件测试", "软件维护", "配置管理", "项目管理", "质量保证", "UML", "敏捷开发",
    )),
    (("python机器学习", "机器学习快速入门"), (
        "Python", "机器学习", "监督学习", "无监督学习", "回归", "分类", "聚类", "特征工程",
        "模型训练", "模型评估", "过拟合", "交叉验证", "决策树", "支持向量机", "神经网络",
        "scikit-learn", "NumPy", "pandas", "Matplotlib",
    )),
)


GRAPH_DOMAIN_CONCEPT_SET = {item.lower() for item in GRAPH_DOMAIN_CONCEPTS}


DEFAULT_GRAPH = [
    {
        "id": "req_context",
        "name": "业务场景与问题域",
        "layer": "需求发现",
        "difficulty": 1,
        "desc": "明确业务目标、用户角色、边界和约束，防止后续建模偏离真实场景。",
        "keywords": ["业务场景", "用户", "边界", "问题域"],
    },
    {
        "id": "req_stakeholder",
        "name": "干系人与访谈",
        "layer": "需求发现",
        "difficulty": 1,
        "desc": "识别干系人并设计访谈问题，把隐性需求转化为可分析材料。",
        "keywords": ["干系人", "访谈", "需求调研"],
    },
    {
        "id": "req_usecase",
        "name": "用例建模",
        "layer": "需求建模",
        "difficulty": 2,
        "desc": "用参与者、用例、主成功场景和扩展场景描述系统行为。",
        "keywords": ["用例", "参与者", "场景", "UML"],
    },
    {
        "id": "req_domain",
        "name": "领域模型",
        "layer": "需求建模",
        "difficulty": 2,
        "desc": "抽取领域对象、属性与关系，为数据库设计和业务规则实现打基础。",
        "keywords": ["领域模型", "类图", "对象", "关系"],
    },
    {
        "id": "req_nonfunctional",
        "name": "非功能需求",
        "layer": "质量约束",
        "difficulty": 2,
        "desc": "从性能、安全、可靠性、可用性和可维护性描述系统质量。",
        "keywords": ["非功能需求", "性能", "安全", "可靠性"],
    },
    {
        "id": "req_priority",
        "name": "需求优先级",
        "layer": "质量约束",
        "difficulty": 2,
        "desc": "用 MoSCoW、价值/成本矩阵等方法确定阶段实现顺序。",
        "keywords": ["优先级", "MoSCoW", "价值", "成本"],
    },
    {
        "id": "req_trace",
        "name": "需求追踪矩阵",
        "layer": "验证闭环",
        "difficulty": 3,
        "desc": "把目标、需求、设计、测试和资源关联起来，支撑评审与变更控制。",
        "keywords": ["追踪矩阵", "测试", "变更", "验证"],
    },
    {
        "id": "req_review",
        "name": "需求评审与验收",
        "layer": "验证闭环",
        "difficulty": 3,
        "desc": "通过评审清单、验收标准和原型验证降低需求歧义和返工风险。",
        "keywords": ["评审", "验收", "原型", "歧义"],
    },
]


DEFAULT_EDGES = [
    {"source": "req_context", "target": "req_usecase", "label": "场景驱动"},
    {"source": "req_stakeholder", "target": "req_usecase", "label": "访谈输入"},
    {"source": "req_usecase", "target": "req_domain", "label": "对象抽取"},
    {"source": "req_domain", "target": "req_trace", "label": "设计映射"},
    {"source": "req_nonfunctional", "target": "req_priority", "label": "约束排序"},
    {"source": "req_priority", "target": "req_trace", "label": "计划落地"},
    {"source": "req_trace", "target": "req_review", "label": "闭环验证"},
]
