# leleby

## The Semantic Infrastructure for the Industrial World

**让 AI 理解企业、产品、能力和工业知识。**

---

## 项目简介

leleby 是面向 AI 时代的开放工业语义基础设施。

它不是：

* 企业黄页
* 产品数据库
* 电商搜索平台
* 标准文档管理系统

而是通过 **Ontology（本体）+ Semantic Model（语义模型）+ Knowledge Graph（知识图谱）+ Reasoning（推理）**，建立一个机器可理解的工业世界模型。

leleby 的目标是：

> 让企业、产品、服务、能力、标准、要求和验证结果，都能够以统一语义被 AI 理解、连接和推理。


## 为什么需要 leleby？

现代工业世界拥有大量知识：

* 企业能力
* 产品规格
* 制造工艺
* 技术标准
* 测试数据
* 供应链关系

但是这些知识长期存在于 PDF 文档、Excel 表格、企业网站、CAD 文件、私有数据库和人员经验之中。

这些信息：

* 人无法快速获取全部信息；
* 企业之间无法有效交换；
* AI 无法真正理解。

工业进入 AI 时代，需要的不只是数据，而是：

> **机器能够理解的工业语义。**


## leleby 的核心理念

### 从数据连接到语义理解

传统互联网：

```
网页
  ↓
搜索
  ↓
人工判断
```

leleby：

```
实体
  ↓
语义模型
  ↓
关系理解
  ↓
约束推理
  ↓
AI决策
```


## leleby 总体架构

```
                    leleby Ecosystem


                         llb
              Foundation Vocabulary


                         |
                         |

                         lbo
                 Ontology Layer


                         |
                         |

                         lbs
              Semantic Package Layer


                         |
                         |

                         llc
             Commercial Application Layer
```


## 核心能力

### 1. Industrial Ontology

leleby 建立工业世界的基础语义模型，描述产品、企业、能力、过程、资源、规格、要求、约束、测量、验证等核心概念。

例如：

```
Product
  hasSpecification
  hasCharacteristic
  hasRequirement
  hasVerification
  hasComplianceAssessment
```


### 2. Specification Ontology

Specification Ontology 是 leleby 的核心创新之一。它定义：

> 一个产品应该如何被机器理解。

不仅描述：

```
电机：
  功率 500W
  转速 30000rpm
```

而是描述：

```
功能：
  提供旋转动力

性能：
  转速范围
  扭矩曲线
  效率

条件：
  温度
  湿度
  负载

约束：
  最大值
  最小值
  公差

验证：
  测试方法
  测量结果

符合性：
  是否满足要求
```

使 AI 能够进行产品匹配、技术比较、标准符合性判断和智能采购决策。


### 3. Requirement & Constraint Model

工业世界中的核心不是简单属性，而是：

> 在特定条件下，某个对象必须满足什么要求。

leleby 将要求表达为：

```
Requirement
  +
Target
  +
Characteristic
  +
Condition
  +
Constraint
  +
Verification
```

例如：

```
某户外灯具
  要求：
    工作温度 -40℃~50℃
  条件：
    盐雾环境
  验证：
    测试报告
  结果：
    符合 / 不符合
```


### 4. Semantic Package

现实世界中的标准、法规、企业规范、技术要求，通过 Semantic Package 转换为机器可理解资产。

流程：

```
标准文件 (PDF/HTML)
  ↓
语义提取
  ↓
Normative Semantic Package
  ↓
Ontology 实例
  ↓
AI 推理
```


## leleby 支持的未来应用

### AI 采购

用户：

> 寻找满足北欧低温环境的户外照明供应商。

AI 自动分析产品规格、企业能力、标准要求、测试数据，输出符合要求的供应方案。


### 企业 AI 商业名片

企业可以表达：

* 我是谁
* 我生产什么
* 我有什么制造能力
* 我满足哪些标准
* 我有哪些验证记录

形成机器可理解的企业身份。


### 工业产品智能匹配

AI 可以理解：

不是“关键词相似”，而是“功能、性能、条件和约束是否匹配”。


## leleby 与 PPM

PPM（Perfect Product Manufacture）是 leleby 在工业制造领域的重要验证平台。

leleby：

> 定义工业语义。

PPM：

> 验证语义如何转化为制造标准。

关系：

```
leleby
  Specification Ontology
        ↓
PPM
  功能部件标准
  制造验证
  制造商认证
        ↓
工业数据反馈
        ↓
语义模型进化
```

PPM 重点探索高可靠电机、泵、精密运动模块、工业功能部件标准化，通过真实制造场景验证 leleby 的价值。


## 技术路线

leleby 基于开放语义技术：

* OWL
* RDF
* JSON-LD
* Turtle
* SHACL
* Knowledge Graph

核心原则：

### 语义开放

不绑定单一行业标准。通过 Mapping 连接 schema.org、GS1、eCl@ss、行业 Ontology、企业标准。

### 标准中立

leleby 不替代 ISO、IEC 或国家标准。而是将不同来源的要求转化为统一语义，使 AI 可以理解和推理。


## 开源方向

leleby 将逐步开放：

* **Ontology**：工业世界语义模型
* **Semantic Package Specification**：规范语义表达格式
* **Reference Models**：行业示例模型
* **Developer Tools**：用于 RDF 生成、数据验证、语义转换、AI Agent 调用


## 长期愿景

未来工业世界需要的不只是更多数据，而是更多可理解的数据。

leleby 希望成为：

> 工业世界的语义基础设施，让 AI 真正理解企业、产品和制造能力。


## 项目状态

当前重点：

* 建立核心 Ontology
* 完善 Specification Ontology
* 建立 Requirement / Constraint 模型
* 构建语义验证原型
* 探索 PPM 工业验证体系


## 加入 leleby

我们欢迎：

* 工业领域专家
* 本体工程师
* AI 开发者
* 制造企业
* 标准研究者

共同建设下一代工业语义基础设施。

---

**leleby**

*Semantic Infrastructure for the Industrial World.*