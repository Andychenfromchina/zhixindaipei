"""
智信贷配 · 贷款匹配引擎 v5.0
======================================================
v4 → v5 核心改进：解决"优质用户所有产品分数相同"问题

【根本原因诊断】
v4 问题：同类型机构 × 同贷款类型 → 五维原始分100%相同
  例：陈永俊（满分画像）对所有国有大行经营贷都是92.7分+bonus=100
  原因：五维分只衡量"人"，没有衡量"产品"的差异

【v5 三大核心改进】

① 产品级难度系数 (Product Difficulty Score, PDS)
   基于真实市场数据研究：
   - 口子哥(kouzige.cn) 2026年银行产品真实申请难易度数据
   - 证券时报经营贷市场调研报告 2026.01
   - 各银行官方征信要求文件
   每个产品：准入门槛 / 真实通过率 / 分数天花板

② 申请人-产品匹配度拆解 (Person-Product Fit Decomposition)
   - 身份契合度 (Identity Fit)：你是否这个产品的目标客群？
   - 征信契合度 (Credit Fit)：你的征信是否超出/低于要求？
   - 生态契合度 (Ecosystem Fit)：你是否是该平台的活跃用户？
   - 地域契合度 (Geo Fit)：城商行/农商行的地域匹配

③ 分数天花板差异化 (Score Ceiling Differentiation)
   - 高门槛产品（国有大行经营贷）天花板 90-95
   - 中等门槛（股份制消费贷）天花板 87-90
   - 低门槛产品（互联网/消费金融）天花板 78-83
   - 绿色贷/政策性（需特殊资质）天花板 80-88 但通过率极低
   这样即使完美用户，各产品分数也会有10-20分差异
======================================================
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import Counter


# ══════════════════════════════════════════════════════
#  数据模型
# ══════════════════════════════════════════════════════

@dataclass
class CreditProfile:
    name: str = ""
    age: int = 0
    marriage: str = ""
    province: str = ""
    city_tier: int = 3
    credit_cards: list = field(default_factory=list)
    cny_total_limit: float = 0
    cny_used_amount: float = 0
    cny_utilization: float = 0
    active_card_count: int = 0
    total_card_count: int = 0
    has_usd_card: bool = False
    oldest_card_years: float = 0
    multi_bank_cards: int = 0
    loans: list = field(default_factory=list)
    active_loan_count: int = 0
    active_loan_balance: float = 0
    mortgage_balance: float = 0
    business_loan_balance: float = 0
    consumer_loan_balance: float = 0
    est_monthly_payment: float = 0
    settled_loan_count: int = 0
    has_settled_mortgage: bool = False
    has_settled_large_bizloan: bool = False
    max_settled_amount: float = 0
    overdue_accounts: int = 0
    severe_overdue_accounts: int = 0
    current_overdue: bool = False
    is_blacklisted: bool = False
    has_lawsuit: bool = False
    public_records_count: int = 0
    hard_inquiry_1m: int = 0
    hard_inquiry_3m: int = 0
    hard_inquiry_6m: int = 0
    hard_inquiry_12m: int = 0
    hard_inquiry_24m: int = 0
    post_loan_mgmt_count: int = 0
    is_company_legal_person: bool = False
    has_guarantee_query: bool = False
    monthly_income: float = 0
    has_provident_fund: bool = False
    provident_fund_months: int = 0
    has_property: bool = False
    property_value: float = 0
    job_type: str = ""
    income_stability: str = ""
    sesame_score: int = 0
    alipay_active: bool = False
    wechat_pay_active: bool = False
    ecommerce_seller: bool = False
    ecommerce_gmv: float = 0
    bank_assets: float = 0
    debt_ratio: float = 0.0
    _base_score: float = 0


# ══════════════════════════════════════════════════════
#  ★ 核心新增：产品难度系数数据库
#
#  数据来源（2026年实际调研）：
#  - 口子哥kouzige.cn 2026年2月消费贷真实申请难易度汇总表
#  - 证券时报《经营贷利率贴地飞行》现场采访数据
#  - 各银行官方产品准入条件文件
#
#  字段说明：
#  d: 申请难度 0.0=极易 ~ 1.0=极难
#  apr: 真实市场审批通过率估计
#  ceiling: 任何用户能拿到的最高匹配分上限（差异化关键）
#  must: 必须满足的条件（缺失则扣25分/条）
#  nice: 加分项（满足+8分/条）
# ══════════════════════════════════════════════════════

PRODUCT_DIFFICULTY_DB = {
    # ─── 国有大行 消费贷 ───────────────────────────────────────────
    # 来源：口子哥"代发+公积金白名单客户最稳，普通人30万以内比较稳"
    "中银E贷":         dict(d=0.72, apr=0.45, ceiling=86, must=["stable_income","provident_fund"], nice=["公积金","代发工资"]),
    "中银消费贷信用卡": dict(d=0.60, apr=0.55, ceiling=87, must=["active_card"], nice=["中国银行信用卡"]),
    "中银惠农贷":      dict(d=0.45, apr=0.65, ceiling=84, must=[], nice=["农村","县域","新市民"]),
    "融e借":           dict(d=0.75, apr=0.42, ceiling=85, must=["payroll_bank"], nice=["代发工资","工行客户"]),
    "工银薪金贷":      dict(d=0.80, apr=0.38, ceiling=84, must=["payroll_bank","icbc_payroll"], nice=["工行代发"]),
    "快贷":            dict(d=0.68, apr=0.50, ceiling=86, must=["provident_fund"], nice=["公积金","建行客户"]),
    "建易贷":          dict(d=0.72, apr=0.45, ceiling=86, must=["provident_fund","payroll_bank"], nice=["公积金+代发"]),
    "网捷贷":          dict(d=0.78, apr=0.40, ceiling=85, must=["tax_a_grade"], nice=["纳税A级","农行代发"]),
    "农行E贷":         dict(d=0.50, apr=0.60, ceiling=84, must=[], nice=["新市民","县域"]),
    "惠民贷":          dict(d=0.62, apr=0.52, ceiling=85, must=["active_card"], nice=["交通银行信用卡"]),
    "邮享贷":          dict(d=0.45, apr=0.65, ceiling=83, must=[], nice=["邮储客户","农村"]),
    "极速贷":          dict(d=0.65, apr=0.50, ceiling=85, must=["provident_fund"], nice=["公积金","在职"]),

    # ─── 国有大行 经营贷 ───────────────────────────────────────────
    # 来源：证券时报"企业征信良好是基本要求，还需现场尽调"，通过率30-50%
    "惠懂你":          dict(d=0.70, apr=0.48, ceiling=92, must=["biz_owner","tax_data"], nice=["建行生态","纳税记录"]),
    "农银惠农贷":      dict(d=0.55, apr=0.58, ceiling=89, must=["biz_owner","agriculture"], nice=["农业","农村经营"]),
    "邮储经营贷":      dict(d=0.55, apr=0.58, ceiling=89, must=["biz_owner"], nice=["农村小微","邮储客户"]),
    "随心智贷":        dict(d=0.72, apr=0.45, ceiling=91, must=["biz_owner"], nice=["中行客户","小微业主"]),
    "经营e贷":         dict(d=0.68, apr=0.48, ceiling=91, must=["biz_owner","tax_data"], nice=["个体工商户"]),
    "裕农快贷":        dict(d=0.52, apr=0.60, ceiling=88, must=["biz_owner","agriculture"], nice=["农村经营"]),

    # ─── 国有大行 抵押贷 ───────────────────────────────────────────
    "工银房抵贷":      dict(d=0.55, apr=0.62, ceiling=90, must=["has_property"], nice=["工行客户","有房"]),
    "交银房抵贷":      dict(d=0.55, apr=0.62, ceiling=90, must=["has_property"], nice=["交行客户","有房"]),
    "中银E抵贷":       dict(d=0.55, apr=0.62, ceiling=90, must=["has_property"], nice=["中行客户","有房"]),

    # ─── 股份制 消费贷 ─────────────────────────────────────────────
    # 来源：口子哥"招商额度给得最慷慨，审批最快10分钟出结果；征信要求：3月查询≤6次，负债率≤70%"
    "闪电贷":          dict(d=0.60, apr=0.60, ceiling=89, must=[], nice=["白领","代发工资","招行客户"]),
    "拼命贷公积金":    dict(d=0.62, apr=0.58, ceiling=87, must=["provident_fund"], nice=["公积金","招行"]),
    "兴闪贷":          dict(d=0.58, apr=0.62, ceiling=88, must=[], nice=["兴业客户","在职"]),
    "浦银点贷":        dict(d=0.62, apr=0.55, ceiling=86, must=["pufa_customer"], nice=["浦发客户"]),
    "浦发闪贷":        dict(d=0.65, apr=0.52, ceiling=87, must=["pufa_platinum"], nice=["浦发白金卡"]),
    "E秒贷":           dict(d=0.55, apr=0.62, ceiling=87, must=[], nice=["灵活就业","广发客户"]),
    "信秒贷":          dict(d=0.62, apr=0.56, ceiling=86, must=[], nice=["中信信用卡","理财"]),
    "中信e贷":         dict(d=0.60, apr=0.58, ceiling=86, must=[], nice=["中信储蓄"]),
    "白领新一贷":      dict(d=0.65, apr=0.52, ceiling=86, must=["white_collar"], nice=["白领","有房产"]),
    "平安新一贷":      dict(d=0.58, apr=0.60, ceiling=87, must=[], nice=["平安综合","保单"]),
    "光速贷":          dict(d=0.58, apr=0.60, ceiling=86, must=[], nice=["光大客户"]),
    "光大阳光贷":      dict(d=0.55, apr=0.62, ceiling=85, must=[], nice=["在职","光大"]),
    "民易贷":          dict(d=0.58, apr=0.60, ceiling=86, must=[], nice=["理财","代发","小微企业主"]),
    "华夏闪贷":        dict(d=0.60, apr=0.58, ceiling=85, must=["active_card"], nice=["华夏信用卡"]),
    "浙银e贷":         dict(d=0.62, apr=0.55, ceiling=84, must=["zhejiang_resident"], nice=["浙江","浙商客户"]),
    "渤海快贷":        dict(d=0.58, apr=0.58, ceiling=84, must=[], nice=["渤海存量"]),
    "恒e贷":           dict(d=0.55, apr=0.60, ceiling=83, must=[], nice=["恒丰储蓄"]),

    # ─── 股份制 经营贷 ─────────────────────────────────────────────
    "经营贷个人版":    dict(d=0.68, apr=0.48, ceiling=90, must=["biz_owner"], nice=["招行客户","流水"]),
    "兴业经营贷":      dict(d=0.65, apr=0.50, ceiling=90, must=["biz_owner"], nice=["兴业关系","税务"]),
    "平安经营贷":      dict(d=0.65, apr=0.52, ceiling=90, must=["biz_owner"], nice=["平安保单","综合"]),

    # ─── 股份制 抵押/绿色 ──────────────────────────────────────────
    "招行绿色贷":      dict(d=0.85, apr=0.25, ceiling=82, must=["green_cert","biz_owner"], nice=["绿色认证"]),
    "招行e招贷房抵":   dict(d=0.55, apr=0.62, ceiling=89, must=["has_property"], nice=["招行客户","有房"]),
    "平安房抵贷":      dict(d=0.52, apr=0.65, ceiling=89, must=["has_property"], nice=["平安客户","有房"]),
    "浦发房抵贷":      dict(d=0.52, apr=0.65, ceiling=89, must=["has_property"], nice=["浦发客户","有房"]),

    # ─── 城商行 ────────────────────────────────────────────────────
    # 来源：城商行"有些不能满足大行条件的企业，城商行可以放贷"，本地居民通过率55-70%
    "京e贷":           dict(d=0.52, apr=0.65, ceiling=87, must=["beijing_resident"], nice=["北京本地","活动期"]),
    "京e经营贷":       dict(d=0.58, apr=0.60, ceiling=89, must=["biz_owner","beijing_resident"], nice=["北京小微"]),
    "沪e贷":           dict(d=0.52, apr=0.65, ceiling=86, must=["shanghai_resident"], nice=["上海本地"]),
    "宁e贷":           dict(d=0.50, apr=0.66, ceiling=85, must=["jiangsu_resident"], nice=["南京","江苏"]),
    "杭e贷":           dict(d=0.55, apr=0.63, ceiling=85, must=["provident_fund","hangzhou_resident"], nice=["杭州公积金"]),
    "甬e贷":           dict(d=0.50, apr=0.66, ceiling=85, must=["ningbo_resident"], nice=["宁波本地"]),
    "苏e贷":           dict(d=0.48, apr=0.68, ceiling=84, must=["jiangsu_resident"], nice=["江苏省"]),
    "穗e贷":           dict(d=0.48, apr=0.68, ceiling=85, must=["guangzhou_resident"], nice=["广州本地"]),
    "蓉e贷":           dict(d=0.48, apr=0.68, ceiling=84, must=["chengdu_resident"], nice=["成都本地"]),
    "渝e贷":           dict(d=0.46, apr=0.70, ceiling=84, must=["chongqing_resident"], nice=["重庆本地"]),
    "长安贷":          dict(d=0.46, apr=0.70, ceiling=83, must=["shaanxi_resident"], nice=["陕西"]),
    "中原e贷":         dict(d=0.45, apr=0.70, ceiling=83, must=["henan_resident"], nice=["河南"]),
    "星沙贷":          dict(d=0.45, apr=0.70, ceiling=82, must=["hunan_resident"], nice=["湖南"]),
    "贵e贷":           dict(d=0.42, apr=0.72, ceiling=81, must=["guizhou_resident"], nice=["贵州"]),
    "龙e贷":           dict(d=0.42, apr=0.72, ceiling=81, must=["heilongjiang_resident"], nice=["黑龙江"]),
    "京抵贷":          dict(d=0.50, apr=0.66, ceiling=88, must=["has_property","beijing_resident"], nice=["北京有房"]),

    # ─── 农商行 ────────────────────────────────────────────────────
    "渝快贷":          dict(d=0.40, apr=0.73, ceiling=82, must=["chongqing_resident"], nice=["重庆"]),
    "个人综合消费贷":  dict(d=0.38, apr=0.75, ceiling=81, must=["yunnan_resident"], nice=["云南"]),
    "惠农贷":          dict(d=0.42, apr=0.70, ceiling=82, must=["guangzhou_resident"], nice=["广州农村"]),
    "沪农快贷":        dict(d=0.42, apr=0.70, ceiling=83, must=["shanghai_resident"], nice=["上海"]),
    "京农快贷":        dict(d=0.42, apr=0.70, ceiling=82, must=["beijing_resident"], nice=["北京农村"]),

    # ─── 互联网银行 ─────────────────────────────────────────────────
    # 来源：微粒贷邀请制白名单；网商贷基于商家数据，电商卖家通过率70%+
    "微粒贷":          dict(d=0.30, apr=0.80, ceiling=81, must=["wechat_whitelist"], nice=["微信活跃","QQ"]),
    "微业贷":          dict(d=0.55, apr=0.62, ceiling=87, must=["biz_owner","wechat_biz"], nice=["微信企业认证","小微"]),
    "网商贷":          dict(d=0.45, apr=0.70, ceiling=87, must=["ecommerce_seller"], nice=["淘宝","1688","GMV"]),
    "花呗分期":        dict(d=0.25, apr=0.85, ceiling=79, must=["alipay_active"], nice=["支付宝活跃"]),
    "备用金":          dict(d=0.28, apr=0.82, ceiling=79, must=["alipay_active"], nice=["支付宝活跃"]),
    "好人贷":          dict(d=0.38, apr=0.74, ceiling=83, must=[], nice=["在职","白名单"]),
    "亿联快贷":        dict(d=0.38, apr=0.74, ceiling=81, must=["northeast_resident"], nice=["东北地区"]),
    "苏宁任性贷":      dict(d=0.32, apr=0.78, ceiling=81, must=[], nice=["苏宁生态"]),
    "众e贷":           dict(d=0.35, apr=0.76, ceiling=81, must=[], nice=["在职"]),
    "振兴快贷":        dict(d=0.36, apr=0.75, ceiling=80, must=["liaoning_resident"], nice=["辽宁"]),

    # ─── 消费金融 ───────────────────────────────────────────────────
    # 来源：口子哥"招联通过率60-75%，借呗基于芝麻分自动审批"
    "借呗":            dict(d=0.22, apr=0.82, ceiling=79, must=["sesame_600"], nice=["芝麻分","支付宝"]),
    "好期贷":          dict(d=0.30, apr=0.78, ceiling=81, must=[], nice=["一般用户"]),
    "安逸花":          dict(d=0.32, apr=0.76, ceiling=80, must=["age_18_55"], nice=["在职"]),
    "中银消费贷":      dict(d=0.35, apr=0.74, ceiling=81, must=[], nice=["中行用户"]),
    "兴业好贷":        dict(d=0.32, apr=0.76, ceiling=80, must=[], nice=["一般用户"]),
    "邮你贷":          dict(d=0.35, apr=0.74, ceiling=81, must=[], nice=["邮储客户"]),
    "海尔贷":          dict(d=0.28, apr=0.80, ceiling=79, must=[], nice=["海尔生态"]),
    "苏宁易贷":        dict(d=0.28, apr=0.80, ceiling=79, must=[], nice=["苏宁购物"]),
    "楚天贷":          dict(d=0.35, apr=0.75, ceiling=79, must=["hubei_resident"], nice=["湖北"]),
    "北银快贷":        dict(d=0.35, apr=0.74, ceiling=80, must=["beijing_resident"], nice=["北京"]),

    # ─── 互联网平台 ─────────────────────────────────────────────────
    # 来源：口子哥"京东金条重度用户下款快，通过率65-75%"
    "京东金条":        dict(d=0.28, apr=0.78, ceiling=79, must=[], nice=["京东活跃"]),
    "白条分期":        dict(d=0.22, apr=0.85, ceiling=77, must=[], nice=["京东购物"]),
    "有钱花":          dict(d=0.30, apr=0.78, ceiling=79, must=[], nice=["百度系"]),
    "360借条":         dict(d=0.30, apr=0.77, ceiling=78, must=[], nice=["360生态"]),
    "分期乐":          dict(d=0.32, apr=0.75, ceiling=78, must=[], nice=["年轻用户"]),
    "卡卡贷":          dict(d=0.38, apr=0.70, ceiling=79, must=["active_card"], nice=["信用卡用户"]),
    "小米贷款":        dict(d=0.28, apr=0.80, ceiling=78, must=[], nice=["小米生态"]),
    "美团生活费":      dict(d=0.25, apr=0.82, ceiling=77, must=[], nice=["美团活跃"]),
    "滴水贷":          dict(d=0.28, apr=0.80, ceiling=77, must=[], nice=["滴滴用户"]),
    "拿去花":          dict(d=0.25, apr=0.82, ceiling=76, must=[], nice=["携程用户"]),

    # ─── 政策性银行 ─────────────────────────────────────────────────
    # 极难：需国家项目认定，真实通过率25-35%
    "开发贷普惠版":    dict(d=0.85, apr=0.30, ceiling=89, must=["national_project","biz_owner"], nice=["国家重点","小微"]),
    "农发惠农贷":      dict(d=0.78, apr=0.35, ceiling=87, must=["agriculture","biz_owner"], nice=["农业","合作社"]),

    # ─── 绿色贷（最难）──────────────────────────────────────────────
    "中银绿色贷":      dict(d=0.90, apr=0.18, ceiling=80, must=["green_cert","biz_owner"], nice=["绿色认证"]),
    "工银绿贷":        dict(d=0.90, apr=0.18, ceiling=80, must=["green_cert","biz_owner","carbon"], nice=["碳中和","新能源"]),
}

INSTITUTION_TYPE_DEFAULTS = {
    "国有大行":   dict(d=0.70, apr=0.45, ceiling=87),
    "股份制":     dict(d=0.62, apr=0.55, ceiling=88),
    "城商行":     dict(d=0.50, apr=0.65, ceiling=85),
    "农商行":     dict(d=0.42, apr=0.70, ceiling=83),
    "互联网银行": dict(d=0.35, apr=0.75, ceiling=84),
    "消费金融":   dict(d=0.30, apr=0.78, ceiling=81),
    "互联网平台": dict(d=0.28, apr=0.80, ceiling=79),
    "政策性银行": dict(d=0.82, apr=0.32, ceiling=87),
}


def _get_product_difficulty(product: dict) -> dict:
    prod_name = str(product.get("产品名称", ""))
    inst_type = str(product.get("机构类型", "消费金融"))
    loan_type = str(product.get("贷款类型", ""))

    for key, cfg in PRODUCT_DIFFICULTY_DB.items():
        if key in prod_name or prod_name in key:
            return cfg

    # 关键词模糊
    if "绿色" in prod_name or "绿贷" in prod_name:
        return dict(d=0.90, apr=0.18, ceiling=80, must=["green_cert"], nice=[])
    if "抵押" in prod_name or "房抵" in prod_name or loan_type == "抵押贷":
        return dict(d=0.52, apr=0.65, ceiling=89, must=["has_property"], nice=[])
    if loan_type == "经营贷":
        base = INSTITUTION_TYPE_DEFAULTS.get(inst_type, INSTITUTION_TYPE_DEFAULTS["消费金融"])
        return dict(d=base["d"]+0.05, apr=base["apr"]-0.08, ceiling=base["ceiling"]+2, must=["biz_owner"], nice=[])

    return INSTITUTION_TYPE_DEFAULTS.get(inst_type, dict(d=0.35, apr=0.75, ceiling=82, must=[], nice=[]))


# ══════════════════════════════════════════════════════
#  机构风控参数
# ══════════════════════════════════════════════════════

INSTITUTION_PROFILE = {
    "国有大行":   dict(min_score=72, max_overdue=1, max_hi_1m=2, max_hi_3m=4,  max_hi_6m=6,  max_dr_c=0.55, max_dr_b=0.70, max_loans=5, max_util=0.75),
    "股份制":     dict(min_score=65, max_overdue=2, max_hi_1m=3, max_hi_3m=6,  max_hi_6m=8,  max_dr_c=0.60, max_dr_b=0.75, max_loans=6, max_util=0.80),
    "城商行":     dict(min_score=60, max_overdue=3, max_hi_1m=4, max_hi_3m=8,  max_hi_6m=12, max_dr_c=0.65, max_dr_b=0.78, max_loans=7, max_util=0.85),
    "农商行":     dict(min_score=58, max_overdue=3, max_hi_1m=4, max_hi_3m=8,  max_hi_6m=12, max_dr_c=0.65, max_dr_b=0.78, max_loans=7, max_util=0.85),
    "互联网银行": dict(min_score=45, max_overdue=4, max_hi_1m=5, max_hi_3m=10, max_hi_6m=15, max_dr_c=0.75, max_dr_b=0.82, max_loans=8, max_util=0.90),
    "消费金融":   dict(min_score=40, max_overdue=5, max_hi_1m=6, max_hi_3m=12, max_hi_6m=18, max_dr_c=0.80, max_dr_b=0.85, max_loans=9, max_util=0.92),
    "互联网平台": dict(min_score=35, max_overdue=6, max_hi_1m=8, max_hi_3m=15, max_hi_6m=20, max_dr_c=0.85, max_dr_b=0.88, max_loans=10,max_util=0.95),
    "政策性银行": dict(min_score=72, max_overdue=0, max_hi_1m=2, max_hi_3m=3,  max_hi_6m=5,  max_dr_c=0.50, max_dr_b=0.60, max_loans=4, max_util=0.70),
}


# ══════════════════════════════════════════════════════
#  ★ 产品-用户 身份契合度评分
# ══════════════════════════════════════════════════════

def _check_condition(p: CreditProfile, condition: str, product: dict) -> bool:
    c = condition.lower()
    if c == "provident_fund":       return p.has_provident_fund
    if c == "has_property":         return p.has_property
    if c == "biz_owner":            return p.is_company_legal_person or p.business_loan_balance > 0 or p.job_type in ("个体/企业主",)
    if c == "stable_income":        return p.has_provident_fund or p.monthly_income > 0
    if c == "ecommerce_seller":     return p.ecommerce_seller
    if c == "alipay_active":        return p.alipay_active
    if c == "wechat_biz":           return p.is_company_legal_person
    if c == "sesame_600":           return p.sesame_score >= 600 or p.alipay_active
    if c == "age_18_55":            return 18 <= p.age <= 55
    if c == "green_cert":           return False
    if c == "carbon":               return False
    if c == "national_project":     return False
    if c == "agriculture":          return p.job_type in ("农民", "农业经营", "个体/企业主")
    if c == "tax_data":             return p.is_company_legal_person or p.business_loan_balance > 0
    if c == "active_card":          return p.active_card_count >= 1
    if c == "payroll_bank":         return p.has_provident_fund
    if c == "icbc_payroll":         return p.has_provident_fund
    if c == "white_collar":         return p.job_type in ("白领", "公务员", "事业单位")
    if c == "tax_a_grade":          return p.is_company_legal_person
    # 地域条件
    geo_map = {
        "beijing_resident": "北京", "shanghai_resident": "上海",
        "guangzhou_resident": "广东", "jiangsu_resident": "江苏",
        "hangzhou_resident": "浙江", "ningbo_resident": "浙江",
        "chongqing_resident": "重庆", "chengdu_resident": "四川",
        "shaanxi_resident": "陕西", "henan_resident": "河南",
        "yunnan_resident": "云南", "hubei_resident": "湖北",
        "heilongjiang_resident": "黑龙江", "hunan_resident": "湖南",
        "guizhou_resident": "贵州", "northeast_resident": "辽宁",
        "liaoning_resident": "辽宁", "zhejiang_resident": "浙江",
    }
    if c in geo_map:
        return p.province == geo_map[c] or (c == "guangzhou_resident" and p.province in ("广东",))
    # 其他生态条件默认不满足
    return False


def _check_nice(p: CreditProfile, nice: str, inst_name: str) -> bool:
    n = nice
    if "公积金" in n:    return p.has_provident_fund
    if "代发" in n:      return p.has_provident_fund
    if "白领" in n:      return p.job_type in ("白领", "公务员", "事业单位")
    if "有房" in n:      return p.has_property
    if "支付宝" in n or "芝麻" in n: return p.alipay_active
    if "微信" in n:      return p.wechat_pay_active
    if "电商" in n or "淘宝" in n or "GMV" in n: return p.ecommerce_seller
    if "在职" in n:      return p.monthly_income > 0 or p.has_provident_fund
    if "税务" in n or "纳税" in n: return p.is_company_legal_person or p.business_loan_balance > 0
    if "农业" in n or "农村" in n: return p.job_type in ("农民", "农业经营")
    if "活动期" in n:    return True
    if "绿色认证" in n:  return False
    if "碳中和" in n or "新能源" in n: return False
    for bank_kw in ["工行","建行","中行","农行","交行","邮储","招行","招商","兴业","浦发","中信","光大","广发","民生","平安","华夏"]:
        if bank_kw in n:
            return bank_kw in inst_name and p.multi_bank_cards >= 4
    return False


def _calc_geo_fit(p: CreditProfile, inst_name: str) -> float:
    """城商行/农商行地域契合度 -25 ~ +40"""
    geo_map = {
        "北京": ["北京","京"], "上海": ["上海","沪"], "广东": ["广州","广东","穗"],
        "浙江": ["杭州","宁波","浙"], "江苏": ["南京","苏","江苏"], "重庆": ["重庆","渝"],
        "四川": ["成都","蓉","川"], "陕西": ["西安","长安","陕"], "河南": ["郑州","中原","豫"],
        "湖南": ["长沙","星沙","湘"], "贵州": ["贵阳","贵","黔"], "云南": ["昆明","云"],
        "黑龙江": ["哈尔滨","龙","黑龙江"], "辽宁": ["沈阳","辽","振兴"], "湖北": ["武汉","楚"],
    }
    for province, kws in geo_map.items():
        if any(kw in inst_name for kw in kws):
            if p.province == province: return 40
            elif p.city_tier == 1:     return 5
            else:                      return -25
    return 0  # 全国性


def _calc_identity_fit(p: CreditProfile, product: dict, dcfg: dict) -> float:
    """身份契合度 0~100"""
    inst_name = str(product.get("机构名称", ""))
    inst_type = str(product.get("机构类型", ""))
    target    = str(product.get("适用人群", ""))
    loan_type = str(product.get("贷款类型", ""))
    prod_name = str(product.get("产品名称", ""))
    must = dcfg.get("must", [])
    nice = dcfg.get("nice", [])

    score = 55.0

    # 必要条件
    for c in must:
        if not _check_condition(p, c, product):
            score -= 22

    # 加分项
    for n in nice:
        if _check_nice(p, n, inst_name):
            score += 8

    # 地域（城商行/农商行关键差异化）
    if inst_type in ("城商行", "农商行"):
        score += _calc_geo_fit(p, inst_name)

    # 生态加分
    if ("网商" in inst_name or "蚂蚁" in inst_name) and p.alipay_active: score += 20
    if ("网商" in inst_name) and p.ecommerce_seller: score += 15
    if "微众" in inst_name and p.wechat_pay_active: score += 18
    if loan_type == "经营贷" and p.is_company_legal_person: score += 12
    if loan_type == "经营贷" and p.business_loan_balance > 500000: score += 6

    # 职业契合
    if "白领" in target:
        score += 12 if p.job_type in ("白领", "公务员", "事业单位", "央企", "国企") else -10
    if "代发" in target and p.has_provident_fund: score += 8
    if "农村" in target or "农业" in target:
        score += 10 if p.job_type in ("农民","农业经营") else -8
    if "新市民" in target and p.city_tier <= 2: score += 5

    # 存量银行关系
    bank_kw_set = {"工行","建行","中行","农行","交行","邮储","招行","招商","兴业","浦发","中信","光大","广发","民生","平安","华夏"}
    for kw in bank_kw_set:
        if kw in inst_name:
            if p.multi_bank_cards >= 6: score += 5
            if kw in ("招行","招商") and p.business_loan_balance > 0: score += 6
            break

    return max(0, min(100, score))


# ══════════════════════════════════════════════════════
#  五维征信评分
# ══════════════════════════════════════════════════════

def _d_history(p: CreditProfile) -> float:
    s = 70.0
    if p.overdue_accounts == 0: s += 22
    else:
        for i in range(min(p.overdue_accounts, 5)): s -= [20, 13, 9, 6, 4][i]
    if p.has_settled_mortgage: s += 8
    if p.has_settled_large_bizloan: s += 6
    s += min(8, p.settled_loan_count * 0.3)
    return max(0, min(100, s))

def _d_debt(p: CreditProfile, is_biz: bool) -> float:
    util = p.cny_utilization
    cu  = 95 if util<=0.10 else 88 if util<=0.20 else 78 if util<=0.30 else 60 if util<=0.50 else 40 if util<=0.70 else 22 if util<=0.85 else 8
    dr  = p.debt_ratio
    drs = 95 if dr<=0.20 else 82 if dr<=0.35 else 65 if dr<=0.50 else 45 if dr<=0.65 else 25 if dr<=0.80 else 8
    lc  = p.active_loan_count
    lcs = 90 if lc==0 else 80 if lc<=2 else 65 if lc<=4 else 45 if lc<=6 else 25
    return cu*0.25 + drs*0.50 + lcs*0.25 if is_biz else cu*0.40 + drs*0.40 + lcs*0.20

def _d_length(p: CreditProfile) -> float:
    y = p.oldest_card_years
    b = 95 if y>=15 else 88 if y>=12 else 78 if y>=8 else 65 if y>=5 else 50 if y>=3 else 35 if y>=1 else 15
    if p.multi_bank_cards >= 6: b += 8
    elif p.multi_bank_cards >= 4: b += 5
    if p.has_usd_card: b += 5
    return max(0, min(100, b))

def _d_inquiry(p: CreditProfile) -> float:
    s = 90.0
    if p.hard_inquiry_1m >= 4: s -= 50
    elif p.hard_inquiry_1m >= 3: s -= 30
    elif p.hard_inquiry_1m >= 2: s -= 15
    elif p.hard_inquiry_1m == 1: s -= 5
    if p.hard_inquiry_3m >= 6: s -= 25
    elif p.hard_inquiry_3m >= 4: s -= 15
    elif p.hard_inquiry_3m >= 2: s -= 7
    if p.hard_inquiry_6m >= 10: s -= 20
    elif p.hard_inquiry_6m >= 6: s -= 12
    return max(0, min(100, s))

def _d_diversity(p: CreditProfile) -> float:
    s = 50.0
    t = sum([p.mortgage_balance>0 or p.has_settled_mortgage, p.business_loan_balance>0 or p.has_settled_large_bizloan, p.consumer_loan_balance>0 or p.settled_loan_count>5])
    s += [0, 10, 22, 35][t]
    s += min(15, p.settled_loan_count * 0.4)
    return max(0, min(100, s))


# ══════════════════════════════════════════════════════
#  ★ v5 核心匹配分数
# ══════════════════════════════════════════════════════

def compute_match_score(p: CreditProfile, product_row: dict) -> tuple[int, float]:
    """
    v5 匹配分 = f(征信资质分, 身份契合度, 产品天花板)
    
    设计原理：
    1. 征信分(credit_score)：用户征信有多好 → 0~100
    2. 身份契合(identity_fit)：你是不是目标客群 → 0~100
    3. 加权合并 → 0~100
    4. 映射到 [floor, ceiling] → 产品天花板确保差异化
    
    关键：ceiling 决定了不同产品的分数范围：
    - 国有大行经营贷 ceiling=91 → 完美用户最高91分
    - 互联网平台     ceiling=77 → 完美用户最高77分
    - 结果：两类产品分数天然有14分差距，方便用户区分
    """
    inst_type  = str(product_row.get("机构类型", "消费金融"))
    loan_type  = str(product_row.get("贷款类型", "消费贷"))
    prod_name  = str(product_row.get("产品名称", ""))
    inst_name  = str(product_row.get("机构名称", ""))
    target_pop = str(product_row.get("适用人群", ""))
    pr  = INSTITUTION_PROFILE.get(inst_type, INSTITUTION_PROFILE["消费金融"])
    is_biz = (loan_type == "经营贷")

    dcfg      = _get_product_difficulty(product_row)
    difficulty = dcfg.get("d", 0.5)
    ceiling   = dcfg.get("ceiling", 84)

    # ── 硬性拒贷 ─────────────────────────────────────
    if p.is_blacklisted: return 0, 0
    if p.current_overdue and inst_type in ("国有大行", "股份制", "政策性银行"): return 0, 0
    if p.severe_overdue_accounts > 0 and inst_type in ("国有大行", "股份制"): return 0, 0
    if p.overdue_accounts > pr["max_overdue"]: return 0, 0
    if loan_type == "抵押贷" and not p.has_property: return 0, 0
    if is_biz and inst_type in ("国有大行", "政策性银行"):
        if not p.is_company_legal_person and p.business_loan_balance == 0 and p.job_type not in ("个体/企业主",):
            return 0, 0
    if "公积金" in target_pop and "公积金" in prod_name and not p.has_provident_fund: return 0, 0
    if p.hard_inquiry_1m > pr["max_hi_1m"]: return 0, 0
    if p.hard_inquiry_3m > pr["max_hi_3m"]: return 0, 0
    h_score = p._base_score if p._base_score and p._base_score > 0 else 60
    if h_score < pr["min_score"] * 0.80: return 0, 0

    # 硬性条件检查（必要条件未满足≥2个拒绝）
    must = dcfg.get("must", [])
    unmet = sum(1 for c in must if not _check_condition(p, c, product_row))
    # 关键条件无法替代
    if "green_cert" in must and not _check_condition(p, "green_cert", product_row): return 0, 0
    if "national_project" in must and not _check_condition(p, "national_project", product_row): return 0, 0
    if "ecommerce_seller" in must and not _check_condition(p, "ecommerce_seller", product_row): return 0, 0
    if unmet >= 2: return 0, 0

    # ── Part 1: 五维征信资质分 ────────────────────────
    d1 = _d_history(p)
    d2 = _d_debt(p, is_biz)
    d3 = _d_length(p)
    d4 = _d_inquiry(p)
    d5 = _d_diversity(p)
    credit_raw = d1*0.35 + d2*0.30 + d3*0.15 + d4*0.10 + d5*0.10

    # 征信评分门槛惩罚
    gap = h_score - pr["min_score"]
    if gap < 0:   credit_raw *= 0.30
    elif gap < 5: credit_raw *= 0.72
    elif gap < 10: credit_raw *= 0.88

    # 边界软惩罚
    max_dr = pr["max_dr_b"] if is_biz else pr["max_dr_c"]
    if p.hard_inquiry_6m > pr["max_hi_6m"]:
        credit_raw -= min(15, (p.hard_inquiry_6m - pr["max_hi_6m"]) * 2.5)
    if p.debt_ratio > max_dr:
        credit_raw -= min(20, (p.debt_ratio - max_dr) * 50)
    if p.cny_utilization > pr["max_util"]:
        credit_raw -= min(15, (p.cny_utilization - pr["max_util"]) * 40)
    credit_raw = max(0, min(100, credit_raw))

    # ── Part 2: 身份契合度 ────────────────────────────
    identity_fit = _calc_identity_fit(p, product_row, dcfg)

    # ── Part 3: 加权合并 ──────────────────────────────
    # 难度高的产品：征信权重更大
    # 难度低的产品：身份契合更重要（生态用户优先）
    credit_weight = 0.45 + difficulty * 0.20  # 难度0.2→0.49, 难度0.9→0.63
    identity_weight = 1 - credit_weight
    combined = credit_raw * credit_weight + identity_fit * identity_weight

    # ── Part 4: 映射到产品天花板 ──────────────────────
    # combined 0~100 映射到 [ceiling-30, ceiling]
    floor = max(20, ceiling - 32)
    mapped = floor + (combined / 100.0) * (ceiling - floor)

    # ── Part 5: 产品专属精细调分 ──────────────────────
    fine_tune = _calc_fine_tune(p, product_row, is_biz, inst_name, loan_type, prod_name, target_pop)

    final = mapped + fine_tune
    final = max(0, min(ceiling, round(final)))
    amount = _estimate(p, product_row, final)
    return int(final), amount


def _calc_fine_tune(p, product, is_biz, inst_name, loan_type, prod_name, target_pop) -> float:
    """精细调分 ±15，用于同类产品内部进一步区分"""
    b = 0.0
    inst_type = str(product.get("机构类型", ""))

    if "公积金" in prod_name or "公积金" in target_pop:
        b += 8 if p.has_provident_fund else -15
    if "代发" in target_pop:
        b += 6 if p.has_provident_fund else -8

    if is_biz:
        if p.is_company_legal_person: b += 10
        elif p.business_loan_balance > 0: b += 6
        elif p.job_type == "个体/企业主": b += 3
        if ("税" in prod_name or "税" in target_pop) and p.is_company_legal_person: b += 6
        if p.business_loan_balance > 1000000: b += 5  # 大额经营贷经验

    if "网商" in inst_name:
        if p.ecommerce_seller: b += 14
        elif p.alipay_active: b += 6
    if "微众" in inst_name:
        if p.wechat_pay_active: b += 12
        if p.is_company_legal_person and "微业" in prod_name: b += 8
    if ("蚂蚁" in inst_name or "借呗" in prod_name) and p.alipay_active: b += 10
    if p.sesame_score >= 700 and ("借呗" in prod_name or "花呗" in prod_name): b += 6

    if "白领" in target_pop:
        b += 10 if p.job_type in ("白领","公务员","事业单位","央企") else -8
    if "绿色" in prod_name: b -= 12
    if inst_type in ("城商行","农商行"):
        b += _calc_geo_fit(p, inst_name) * 0.15

    if p.city_tier == 1 and inst_type in ("国有大行","股份制"): b += 2
    if p.has_settled_mortgage and is_biz: b += 4
    if p.overdue_accounts == 0 and p.oldest_card_years >= 10 and not is_biz: b += 3

    return max(-15, min(15, b))


def _estimate(p: CreditProfile, row: dict, match: int) -> float:
    try: prod_max = float(str(row.get("最高额度(万)", "10")).replace("万","").strip())
    except: prod_max = 10.0
    loan_type = str(row.get("贷款类型", "消费贷"))
    mi = p.monthly_income

    if loan_type == "抵押贷":
        cap = min(p.property_value*0.70, prod_max) if p.has_property and p.property_value>0 else prod_max*0.3
    elif loan_type == "经营贷":
        if p.business_loan_balance > 0: cap = min(p.business_loan_balance/10000*1.2, prod_max)
        elif p.ecommerce_gmv > 0: cap = min(p.ecommerce_gmv*0.1, prod_max)
        elif mi > 0: cap = min(mi*36/10000, prod_max)
        else: cap = prod_max*0.4
    else:
        if mi > 0:
            mult = 24 if (p.overdue_accounts==0 and p.hard_inquiry_3m<=2) else 12
            cap = min(mi*mult/10000, prod_max)
        elif p.cny_total_limit > 0: cap = min(p.cny_total_limit*0.5/10000, prod_max)
        else: cap = prod_max*0.3

    base = min(cap, prod_max)
    factor = (match/100)**0.65
    mult = 1.0
    if p.has_settled_mortgage: mult += 0.08
    if p.overdue_accounts==0 and p.oldest_card_years>=10: mult += 0.06
    if p.cny_utilization <= 0.15: mult += 0.05
    est = base * factor * min(mult, 1.25)

    if est >= 100: est = round(est/10)*10
    elif est >= 20: est = round(est/5)*5
    elif est >= 5: est = round(est)
    else: est = round(est, 1)
    return max(0.5, min(prod_max, est))


def _parse_rate_min(rate_str: str) -> float:
    if not rate_str or str(rate_str) in ("—", ""): return 99.0
    nums = re.findall(r"(\d+\.?\d*)", str(rate_str))
    return float(nums[0]) if nums else 99.0


# ══════════════════════════════════════════════════════
#  解析模块
# ══════════════════════════════════════════════════════

def parse_credit_report(content: str) -> CreditProfile:
    try: data = json.loads(content); return _parse_json(data)
    except: return _parse_pboc_text(content)


def _parse_json(data: dict) -> CreditProfile:
    p = CreditProfile()
    info = data.get("basic_info", {}); summary = data.get("credit_summary", {})
    neg = data.get("negative_records", []); inq = data.get("inquiries", {}); assets = data.get("assets", {})
    p.name=info.get("name",""); p.age=info.get("age",0); p.marriage=info.get("marriage","")
    p.province=info.get("province",""); p.city_tier=info.get("city_tier",3)
    p.monthly_income=info.get("monthly_income",0); p.has_provident_fund=info.get("has_provident_fund",False)
    p.provident_fund_months=info.get("provident_fund_months",0); p.job_type=info.get("job_type","")
    p.income_stability=info.get("income_stability",""); p.ecommerce_seller=info.get("ecommerce_seller",False)
    p.ecommerce_gmv=info.get("ecommerce_gmv",0)
    p.has_property=assets.get("has_property",info.get("has_property",False)); p.property_value=assets.get("property_value",0)
    p.bank_assets=assets.get("bank_assets",0)
    p.cny_total_limit=summary.get("credit_card_total_limit",0); p.cny_used_amount=summary.get("credit_card_used_limit",0)
    p.cny_utilization=(p.cny_used_amount/p.cny_total_limit if p.cny_total_limit>0 else 0)
    p.active_card_count=summary.get("credit_card_count",0); p.overdue_accounts=summary.get("overdue_accounts",0)
    p.severe_overdue_accounts=summary.get("severe_overdue_accounts",0)
    p.current_overdue=any(r.get("current",False) for r in neg if isinstance(r,dict))
    p.is_blacklisted=summary.get("is_blacklisted",False); p.public_records_count=summary.get("public_records_count",0)
    p.active_loan_count=summary.get("loan_count",0); p.active_loan_balance=summary.get("loan_balance",0)
    p.business_loan_balance=summary.get("business_loan_balance",0); p.est_monthly_payment=summary.get("monthly_payment",0)
    p.settled_loan_count=summary.get("settled_loan_count",0); p.has_settled_mortgage=summary.get("has_settled_mortgage",False)
    p.has_settled_large_bizloan=summary.get("has_settled_large_bizloan",False)
    p.oldest_card_years=summary.get("oldest_card_years",0); p.multi_bank_cards=summary.get("multi_bank_cards",0)
    p.has_usd_card=summary.get("has_usd_card",False); p.is_company_legal_person=summary.get("is_company_legal_person",False)
    p.hard_inquiry_1m=inq.get("last_1m_count",0); p.hard_inquiry_3m=inq.get("last_3m_count",0)
    p.hard_inquiry_6m=inq.get("last_6m_count",0); p.hard_inquiry_24m=inq.get("last_24m_count",0)
    p.sesame_score=summary.get("sesame_score",0); p.alipay_active=summary.get("alipay_active",False)
    p.wechat_pay_active=summary.get("wechat_pay_active",False); p._base_score=summary.get("credit_score_estimate",0)
    if p.monthly_income>0 and p.est_monthly_payment>0: p.debt_ratio=min(1.0,p.est_monthly_payment/p.monthly_income)
    else: p.debt_ratio=summary.get("debt_ratio",0.3)
    return p


def _parse_pboc_text(content: str) -> CreditProfile:
    p = CreditProfile(); now = datetime.now(); ny = now.year
    if m := re.search(r"姓名[：:\s]+(\S+)", content): p.name = m.group(1)
    if m := re.search(r"\d{6}(\d{4})\d{2}\d{2}\d{3}[\dXx]", content): p.age = ny - int(m.group(1))
    if "未婚" in content: p.marriage = "未婚"
    elif "已婚" in content: p.marriage = "已婚"
    for prov, kws in {"广东":["广东","广州","440"],"北京":["北京","110"],"上海":["上海","310"],"浙江":["浙江","杭州"]}.items():
        if any(k in content for k in kws): p.province=prov; p.city_tier=1; break
    overdue_raw = re.findall(r"发生过逾期的账户数\s+(--|[\d]+)", content)
    p.overdue_accounts = sum(int(x) for x in overdue_raw if x.strip() != "--")
    if "失信" in content: p.is_blacklisted = True
    pairs = re.findall(r"信用额度([\d,]+)，已使用额度([\d,]+)", content)
    cny_l=[float(l.replace(",","")) for l,u in pairs]; cny_u=[float(u.replace(",","")) for l,u in pairs]
    p.cny_total_limit=sum(cny_l); p.cny_used_amount=sum(cny_u)
    p.cny_utilization=(p.cny_used_amount/p.cny_total_limit if p.cny_total_limit>0 else 0)
    if "美元" in content: p.has_usd_card=True
    card_years=[int(y) for y in re.findall(r"(\d{4})年\d{2}月\d{2}日.*?发放的贷记卡",content)]
    if card_years: p.oldest_card_years=ny-min(card_years)
    banks=re.findall(r"((?:招商|工商|建设|农业|中国|交通|兴业|光大|浦发|广发|中信|民生)银行)",content)
    p.multi_bank_cards=len(set(banks))
    biz=re.findall(r"发放的([\d,]+)元.*?个人经营性贷款，(\d{4})年(\d{2})月\d{2}日到期[^。]*?余额([\d,]+)",content)
    me=0.0
    for amt,dy,dm,bal in biz:
        b=float(bal.replace(",","")); ml=max(1,(int(dy)-ny)*12+int(dm)-now.month); me+=b/ml; p.business_loan_balance+=b
    p.active_loan_count=len(biz); p.active_loan_balance=p.business_loan_balance; p.est_monthly_payment=me
    if re.search(r"个人住房.*?已结清",content): p.has_settled_mortgage=True
    sb=re.findall(r"发放的([\d,]+)元.*?个人经营性贷款.*?已结清",content)
    for a in sb:
        p.settled_loan_count+=1; av=float(a.replace(",",""))
        p.max_settled_amount=max(p.max_settled_amount,av)
        if av>=1_000_000: p.has_settled_large_bizloan=True
    p.settled_loan_count=max(p.settled_loan_count,len(re.findall(r"已结清",content)))
    ql=re.findall(r"(\d{4})年(\d{2})月(\d{2})日\s+(.*?)\s+(贷款审批|贷后管理|担保资格审查|法人代表[^查]*?资信审查|本人查询)",content)
    hd=[]
    for y,mo,d,inst,reason in ql:
        try:
            qd=datetime(int(y),int(mo),int(d)); da=(now-qd).days
            if "贷款审批" in reason: hd.append(da)
            elif "法人" in reason: p.is_company_legal_person=True
        except: pass
    p.hard_inquiry_1m=sum(1 for d in hd if d<=30); p.hard_inquiry_3m=sum(1 for d in hd if d<=90)
    p.hard_inquiry_6m=sum(1 for d in hd if d<=180); p.hard_inquiry_24m=sum(1 for d in hd if d<=730)
    if p.is_company_legal_person or p.business_loan_balance>0:
        if not p.job_type: p.job_type="个体/企业主"
    if p.monthly_income>0: p.debt_ratio=min(1.0,p.est_monthly_payment/p.monthly_income)
    elif p.est_monthly_payment>0: p.monthly_income=p.est_monthly_payment/0.50; p.debt_ratio=0.50
    else: p.debt_ratio=0.20
    return p


# ══════════════════════════════════════════════════════
#  信用健康分 v6.0
# ══════════════════════════════════════════════════════
# 设计依据（2026年实地调研 + 监管文件）：
#
# 【五维权重参照来源】
#   A. 人行二代征信"中征信评分"五维度（满分1000分）：
#      还款历史 | 当前负债 | 信贷申请 | 信贷组合 | 信用历史
#      来源: 知乎万字解读二代征信报告 / CSDN番茄风控
#
#   B. FICO评分学术权重（各大行风控评分卡参照基准）：
#      还款历史35% | 欠款金额30% | 信用历史15% | 新账户10% | 信用组合10%
#      来源: 21财经《央行版信用评分推出在即》引用数据
#
#   C. 中国银行2018年财报：采用"基于历史违约率的评分卡模型"
#      中信银行："引入第三方外部数据，加大个人信贷数据深度挖掘"
#      建设银行："研发新版小微贷款评分模型"
#
#   D. 2026年一次性信用修复新政（人行）：
#      2020-2025年间单笔≤1万逾期，2026.03.31前还清可申请不展示
#
# 【各地区银行准入硬标准（多机构交叉验证）】
#   国有大行：近1月≤2次 近3月≤4次 近6月≤6次 负债率≤65%
#   股份制行：近3月≤6次 近6月≤8次 负债率≤70%
#   城商行  ：近6月≤10次 负债率≤75% （各地城商行标准有差异）
#   互联网行：近3月≤8次 基本无负债率硬限制（依大数据评分）
#   消费金融：近3月≤10次 大数据综合决策
#
# 【五维分值上限设计（最高99分）】
#   D1还款历史  满分35
#   D2负债状况  满分25
#   D3信用历史  满分16
#   D4信贷申请  满分14
#   D5信贷组合  满分9
#   合计       满分99（永不触达100，保留1分不确定性）
# ══════════════════════════════════════════════════════


def _d1_repayment_history(p: CreditProfile) -> float:
    """
    D1 还款历史 — 满分35分
    对标 FICO 权重最重维度（35%）+ 人行评分第一维度
    逻辑：零逾期 → 接近满分；逾期越严重/越多 → 分越低
    """
    # 一票否决项（归零）
    if p.is_blacklisted:       return 0.0
    if p.current_overdue:      return 0.0   # 当前仍逾期
    if p.severe_overdue_accounts >= 2: return 0.0  # 2+个90天以上严重逾期

    score = 35.0

    # 严重逾期（90天以上）：每笔扣14分，最多归零
    if p.severe_overdue_accounts == 1:
        score -= 14

    # 一般逾期次数（累计历史）
    # 参照：银行评分卡"连三累六"规则（3个月连续或6个月累计逾期为硬拒）
    ov = p.overdue_accounts
    if ov == 0:
        score += 0     # 已满分，零逾期基准
    elif ov == 1:
        score -= 8     # 1次轻微逾期，扣8分
    elif ov == 2:
        score -= 14    # 2次扣14分
    elif ov == 3:
        score -= 18    # 接近"连三"警戒线
    elif ov == 4:
        score -= 22
    else:
        score -= min(30, 22 + (ov - 4) * 2)  # 5次以上线性递增

    # 公共信息（失信/行政处罚/民事判决/欠税）
    # 来源：湖南金融监管局《如何解读个人信用报告》2025.08
    if p.has_lawsuit:
        score -= 8
    if p.public_records_count > 0:
        score -= min(12, p.public_records_count * 5)

    # 正向奖励：已结清的大额贷款（证明长期履约能力）
    if p.has_settled_mortgage:      score += 5   # 房贷结清：最强履约证明
    if p.has_settled_large_bizloan: score += 3   # 大额经营贷结清
    score += min(4, p.settled_loan_count * 0.4)  # 累计结清贷款笔数

    return max(0.0, min(35.0, score))


def _d2_debt_burden(p: CreditProfile) -> float:
    """
    D2 负债状况 — 满分25分
    对标 FICO 欠款金额维度（30%）+ 中国银行个人贷款评分卡负债率指标
    核心指标：信用卡使用率 + 整体负债率 + 绝对负债规模
    """
    score = 0.0

    # ① 信用卡使用率（授信利用率）—— 各行标准：≤30%良好，≤50%正常，>70%高风险
    u = p.cny_utilization
    if u <= 0.05:    score += 13   # 极低，显示充裕还款空间
    elif u <= 0.10:  score += 12
    elif u <= 0.20:  score += 10
    elif u <= 0.30:  score += 8
    elif u <= 0.40:  score += 5
    elif u <= 0.50:  score += 2
    elif u <= 0.65:  score += 0
    elif u <= 0.80:  score -= 3
    else:            score -= 8   # 超80%，被多家银行视为高负债警戒

    # ② 综合负债率（月还款/月收入）—— 各地银行准入硬标准
    # 国有大行≤65% / 股份制≤70% / 城商行≤75% / 互联网不设硬线
    dr = p.debt_ratio
    if dr <= 0.20:   score += 12   # 轻松还款，优质信号
    elif dr <= 0.30: score += 10
    elif dr <= 0.40: score += 7
    elif dr <= 0.50: score += 4
    elif dr <= 0.60: score += 1
    elif dr <= 0.70: score -= 2
    elif dr <= 0.80: score -= 6
    else:            score -= 12  # >80%，多数银行拒贷线

    # ③ 在贷笔数修正（过多分散风险信号）
    if p.active_loan_count == 0:   score += 2   # 无在贷：低负债
    elif p.active_loan_count <= 2: score += 1
    elif p.active_loan_count <= 4: score += 0
    elif p.active_loan_count <= 6: score -= 1
    else:                          score -= 3   # 7笔以上：多头借贷警示

    return max(0.0, min(25.0, score))


def _d3_credit_history(p: CreditProfile) -> float:
    """
    D3 信用历史 — 满分16分
    对标 FICO 立信时间（15%）+ 人行评分"信用历史"维度
    越长的信用历史 → 越可预测的还款行为
    """
    score = 0.0

    # ① 最早信用卡账龄（信用历史起点）
    y = p.oldest_card_years
    if y >= 20:    score += 10   # 20年以上：极度成熟信用档案
    elif y >= 15:  score += 9
    elif y >= 10:  score += 7
    elif y >= 7:   score += 5
    elif y >= 5:   score += 3
    elif y >= 3:   score += 1
    elif y >= 1:   score += 0
    else:          score -= 2   # 不足1年：信用历史过短

    # ② 多行持卡数量（信用广度）
    # 来源：各行评分卡显示多行持卡客户流失率低，信用稳定性高
    mc = p.multi_bank_cards
    if mc >= 8:    score += 4
    elif mc >= 6:  score += 3
    elif mc >= 4:  score += 2
    elif mc >= 2:  score += 1

    # ③ 外币卡（国际信用证明，招行/汇丰等评分均有体现）
    if p.has_usd_card: score += 2

    return max(0.0, min(16.0, score))


def _d4_credit_applications(p: CreditProfile) -> float:
    """
    D4 信贷申请（查询记录） — 满分14分
    对标 FICO 新开信用账户（10%）+ 人行评分"信贷申请"维度
    短期密集查询 → 资金紧张信号 → 各行风控核心关注点

    【各机构硬标准（来源：口子哥2026年银行产品真实申请难易度汇总）】
    国有大行：近1月≤2次，近3月≤4次，近6月≤6次
    股份制行：近3月≤6次，近6月≤8次（招行：近3月≤6次最稳）
    城商行  ：近6月≤10次
    互联网行：近3月≤8次（基于大数据综合判断）
    """
    score = 14.0  # 从满分开始扣减

    hi1 = p.hard_inquiry_1m
    hi3 = p.hard_inquiry_3m
    hi6 = p.hard_inquiry_6m
    hi12 = p.hard_inquiry_12m

    # 近1月查询（最敏感）：大行1月≤2次硬线
    if hi1 == 0:    score += 0
    elif hi1 == 1:  score -= 1
    elif hi1 == 2:  score -= 3
    elif hi1 == 3:  score -= 6
    else:           score -= 10  # ≥4次：触发大行拒贷线

    # 近3月查询（次敏感）：股份制3月≤6次
    if hi3 <= 1:    score += 0
    elif hi3 <= 3:  score -= 1
    elif hi3 <= 5:  score -= 3
    elif hi3 <= 7:  score -= 5
    else:           score -= 8   # ≥8次：触发多数银行警戒

    # 近6月查询（趋势判断）：大行6月≤6次
    if hi6 <= 3:    score += 0
    elif hi6 <= 6:  score -= 1
    elif hi6 <= 9:  score -= 3
    elif hi6 <= 12: score -= 5
    else:           score -= 7   # ≥13次：高多头风险

    # 近12月长期趋势（轻微影响）
    if hi12 >= 15:  score -= 2

    return max(0.0, min(14.0, score))


def _d5_credit_mix(p: CreditProfile) -> float:
    """
    D5 信贷组合 — 满分9分
    对标 FICO 信用组合（10%）+ 人行评分"信贷组合"维度
    多元化、健康的信贷产品组合 → 更强的风险管理能力证明

    【银行评分卡逻辑（来源：中原银行CCF数据/机器学习研究）】
    有房贷记录 > 有经营贷记录 > 纯消费信贷
    组合越多样 → 综合偿债能力越强
    """
    score = 0.0

    # ① 信贷类型多样性（是否覆盖抵押类/经营类/消费类）
    has_mortgage_exp  = p.mortgage_balance > 0 or p.has_settled_mortgage
    has_bizloan_exp   = p.business_loan_balance > 0 or p.has_settled_large_bizloan
    has_consumer_exp  = p.consumer_loan_balance > 0 or p.settled_loan_count > 3

    type_count = sum([has_mortgage_exp, has_bizloan_exp, has_consumer_exp])
    score += [0, 3, 6, 9][type_count]

    # ② 稳定收入证明体系
    if p.has_provident_fund:
        # 公积金：工行/建行/农行均视为强收入稳定性背书
        months = p.provident_fund_months
        if months >= 24:   score += 2
        elif months >= 12: score += 1
        else:              score += 0.5

    # ③ 职业加成（国有大行/股份制核心优先客群）
    if p.job_type in ("公务员", "事业单位", "央企"):
        score += 2
    elif p.job_type in ("国企", "教师", "医生", "律师", "会计师"):
        score += 1

    # ④ 法人身份（经营贷加分项：证明有真实经营场景）
    if p.is_company_legal_person: score += 1

    # ⑤ 城市层级（一二线城市金融资源更丰富，信用生态更完善）
    if p.city_tier == 1:   score += 1
    elif p.city_tier == 2: score += 0.5

    # ⑥ 互联网征信补充（芝麻分/微信支付：消费金融/互联网银行参考）
    if p.sesame_score >= 750: score += 1

    return max(0.0, min(9.0, score))


def compute_health_score(p: CreditProfile) -> tuple[int, str, str]:
    """
    信用健康分主函数 v6.0
    ─────────────────────────────────────────────────────
    架构：五维独立评分 → 加权合计 → 一票否决修正 → 封顶99
    满分设计：99分（永不触达100，体现"无完美信用"的金融逻辑）

    五维权重：
      D1 还款历史    35/99 = 35.4%  （参照FICO 35%）
      D2 负债状况    25/99 = 25.2%  （参照FICO 30%，中国特色适度降权）
      D3 信用历史    16/99 = 16.2%  （参照FICO 15%，略上调反映中国银行年限重视）
      D4 信贷申请    14/99 = 14.1%  （参照FICO 10%，中国多头风险更突出故上调）
      D5 信贷组合     9/99 =  9.1%  （参照FICO 10%）
    """
    d1 = _d1_repayment_history(p)
    d2 = _d2_debt_burden(p)
    d3 = _d3_credit_history(p)
    d4 = _d4_credit_applications(p)
    d5 = _d5_credit_mix(p)

    raw = d1 + d2 + d3 + d4 + d5  # 理论满分99

    # 一票否决硬扣（独立于五维，直接作用于最终分）
    if p.is_blacklisted:
        raw = min(raw, 12)   # 失信被执行：上限12分
    elif p.current_overdue and p.severe_overdue_accounts >= 1:
        raw = min(raw, 25)   # 当前逾期+严重逾期：上限25分

    score = max(0, min(99, round(raw)))

    dim_scores = {
        "D1还款历史": round(d1, 1),
        "D2负债状况": round(d2, 1),
        "D3信用历史": round(d3, 1),
        "D4信贷申请": round(d4, 1),
        "D5信贷组合": round(d5, 1),
    }

    return score, *_explanation_v6(p, score, dim_scores)


def _explanation_v6(p: CreditProfile, score: int, dims: dict) -> tuple[str, str]:
    """生成信用健康分等级与详细说明（v6）"""
    up  = round(p.cny_utilization * 100, 1)
    dr  = round(p.debt_ratio * 100, 1)
    hi1 = p.hard_inquiry_1m
    hi3 = p.hard_inquiry_3m

    # ── 一票否决等级 ──────────────────────────────────────
    if p.is_blacklisted:
        return ("极高风险（失信被执行）",
                "征信存在失信被执行记录，人行系统标记，所有持牌金融机构均系统性拒贷。"
                "需先向法院申请执行终结或履行义务，方可修复。")

    if p.current_overdue and p.severe_overdue_accounts >= 1:
        return ("极高风险（当前逾期+严重逾期）",
                f"存在当前未结清逾期且有90天以上严重逾期记录，银行系统将直接拒贷。"
                f"建议立即结清全部逾期款项；严重逾期记录保留5年，结清后可申请信用修复。")

    if p.current_overdue:
        return ("高风险（当前逾期未清）",
                "存在当前仍处于逾期状态的账户，须在结清后方可申请贷款。"
                "结清后建议等待1-3个月，待征信更新再申请。")

    if p.severe_overdue_accounts >= 2:
        return ("高风险（多次严重逾期）",
                f"累计{p.severe_overdue_accounts}个90天以上严重逾期账户，"
                "大中型银行基本拒贷，仅部分消费金融/互联网平台可尝试小额。")

    # ── 评分分级解读 ──────────────────────────────────────
    d1v = dims["D1还款历史"]
    d2v = dims["D2负债状况"]
    d4v = dims["D4信贷申请"]

    # 找出最薄弱维度，给出提升建议
    weak_tips = []
    if d2v < 15 and up > 30:
        weak_tips.append(f"信用卡使用率{up}%偏高（建议控制在30%以下）")
    if d2v < 15 and dr > 50:
        weak_tips.append(f"综合负债率{dr}%偏高（多数大行要求≤65%）")
    if d4v < 8:
        if hi1 >= 3:
            weak_tips.append(f"近1月{hi1}次贷款审批查询过多（建议近1月≤2次）")
        elif hi3 >= 5:
            weak_tips.append(f"近3月{hi3}次查询偏多（股份制要求近3月≤6次）")
    if p.oldest_card_years < 3:
        weak_tips.append("信用历史不足3年（建议保持最早开卡并持续使用）")
    if p.overdue_accounts > 0 and not p.current_overdue:
        weak_tips.append(f"历史存在{p.overdue_accounts}次逾期记录（结清后需5年消除）")

    # 强项列举
    strengths = []
    if p.overdue_accounts == 0: strengths.append("历史零逾期")
    if up <= 15:                strengths.append(f"信用卡使用率仅{up}%")
    if p.has_settled_mortgage:  strengths.append("曾结清房贷")
    if p.oldest_card_years >= 10: strengths.append(f"信用历史{int(p.oldest_card_years)}年")
    if p.has_usd_card:          strengths.append("持有外币信用卡")
    if p.has_provident_fund:    strengths.append("连续缴纳公积金")
    if hi1 == 0 and hi3 <= 1:   strengths.append("近期零查询压力")

    dim_str = " | ".join([f"{k.replace('D','').replace('还款历史','还款').replace('负债状况','负债').replace('信用历史','历史').replace('信贷申请','查询').replace('信贷组合','组合')}:{v}" for k,v in dims.items()])

    if score >= 88:
        level = "卓越（顶尖白名单客群）"
        main = (f"综合信用分{score}/99分，处于人行征信人群前5%区间。"
                f"{'、'.join(strengths[:4])}。"
                f"符合国有大行、优质股份制银行最严格的贷款准入标准。")
    elif score >= 78:
        level = "优质（白名单客群）"
        main = (f"综合信用分{score}/99分，属优质信用客群（前15%区间）。"
                f"{'、'.join(strengths[:3])}。"
                + (f"改善方向：{'；'.join(weak_tips[:2])}。" if weak_tips else ""))
    elif score >= 66:
        level = "良好（标准优质客群）"
        main = (f"综合信用分{score}/99分，信用状况良好，可申请主流银行及城商行产品。"
                f"信用卡使用率{up}%，负债率{dr}%，近1月{hi1}次/近3月{hi3}次查询。"
                + (f"提升建议：{'；'.join(weak_tips[:2])}。" if weak_tips else ""))
    elif score >= 52:
        level = "中等（标准客群）"
        main = (f"综合信用分{score}/99分，可申请城商行、互联网银行及消费金融产品。"
                + (f"主要弱项：{'；'.join(weak_tips[:3])}。" if weak_tips else ""))
    elif score >= 38:
        level = "偏低（次优客群）"
        main = (f"综合信用分{score}/99分，大中型银行审批较难，建议优先互联网/消费金融平台。"
                + (f"关键问题：{'；'.join(weak_tips[:3])}。" if weak_tips else ""))
    elif score >= 20:
        level = "较差（高风险客群）"
        main = (f"综合信用分{score}/99分，仅部分消费金融和小贷公司可尝试，额度和利率均不理想。"
                + (f"改善方向：{'；'.join(weak_tips[:3])}。" if weak_tips else ""))
    else:
        level = "极差（暂不建议申请）"
        main = (f"综合信用分{score}/99分，当前信用状况不建议主动申请贷款，申请失败会产生额外查询记录加重负担。"
                "建议先集中修复信用（结清逾期、降低负债），3-6个月后再评估。")

    detail = f"{main}【五维明细】{dim_str}"
    return level, detail


# ══════════════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════════════

def analyze_credit_report(content: str) -> dict:
    p = parse_credit_report(content)
    score, level, explanation = compute_health_score(p)
    # 五维明细分（供前端展示评分雷达图）
    d1 = _d1_repayment_history(p)
    d2 = _d2_debt_burden(p)
    d3 = _d3_credit_history(p)
    d4 = _d4_credit_applications(p)
    d5 = _d5_credit_mix(p)
    return {
        "credit_health_score": score, "risk_level": level,
        "detailed_explanation": explanation, "_profile": p,
        "score_dimensions": {
            "D1_repayment_history":  {"score": round(d1,1), "max": 35, "label": "还款历史"},
            "D2_debt_burden":        {"score": round(d2,1), "max": 25, "label": "负债状况"},
            "D3_credit_history":     {"score": round(d3,1), "max": 16, "label": "信用历史"},
            "D4_credit_applications":{"score": round(d4,1), "max": 14, "label": "信贷申请"},
            "D5_credit_mix":         {"score": round(d5,1), "max":  9, "label": "信贷组合"},
        },
        "_debug": {
            "hard_inq_1m": p.hard_inquiry_1m, "hard_inq_3m": p.hard_inquiry_3m,
            "hard_inq_6m": p.hard_inquiry_6m, "card_util_pct": round(p.cny_utilization*100,1),
            "debt_ratio_pct": round(p.debt_ratio*100,1), "overdue_accounts": p.overdue_accounts,
            "settled_loans": p.settled_loan_count, "oldest_card_yrs": p.oldest_card_years,
            "is_legal_person": p.is_company_legal_person, "has_settled_house": p.has_settled_mortgage,
            "provident_fund_months": p.provident_fund_months, "job_type": p.job_type,
            "severe_overdue": p.severe_overdue_accounts, "is_blacklisted": p.is_blacklisted,
        }
    }


def match_products(features: dict, df) -> list[dict]:
    p: CreditProfile = features.get("_profile") or CreditProfile()
    results = []
    for _, row in df.iterrows():
        product = row.to_dict()
        match, amount = compute_match_score(p, product)
        if match <= 5: continue
        dcfg = _get_product_difficulty(product)
        rate_str = str(product.get("贴息后有效利率(2026)", product.get("名义年化利率", "")))
        results.append({
            "bank": str(product.get("机构名称","")), "product_name": str(product.get("产品名称","")),
            "institution_type": str(product.get("机构类型","")), "loan_type": str(product.get("贷款类型","")),
            "effective_rate": rate_str, "rate_min": _parse_rate_min(rate_str),
            "max_amount": amount, "match_score": match,
            "approval_rate": f"{round(dcfg.get('apr',0.5)*100)}%",
            "difficulty": round(dcfg.get("d",0.5),2),
            "score_ceiling": dcfg.get("ceiling", 84),
            "term_months": str(product.get("最长期限(月)","")),
            "channel": str(product.get("申请渠道","")),
            "features": str(product.get("核心特点","")),
        })
    results.sort(key=lambda x: (-x["match_score"], x["rate_min"]))
    return results[:15]


# ══════════════════════════════════════════════════════
#  命令行测试
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    import pandas as pd
    df = pd.read_csv("loan_products.csv", encoding="utf-8-sig")
    print(f"产品库：{len(df)} 条\n")

    chen = {
        "basic_info": {"age":45,"marriage":"未婚","province":"广东","city_tier":1,"job_type":"个体/企业主"},
        "credit_summary": {
            "credit_score_estimate":88,"credit_card_total_limit":481800,"credit_card_used_limit":39478,
            "credit_card_count":12,"has_usd_card":True,"oldest_card_years":13,"multi_bank_cards":7,
            "overdue_accounts":0,"loan_count":2,"loan_balance":2403000,"business_loan_balance":2403000,
            "monthly_payment":73000,"settled_loan_count":45,"has_settled_mortgage":True,
            "has_settled_large_bizloan":True,"is_company_legal_person":True,
        },
        "inquiries": {"last_1m_count":1,"last_3m_count":2,"last_6m_count":5},
    }

    content = json.dumps(chen, ensure_ascii=False)
    features = analyze_credit_report(content)
    matches = match_products(features, df)

    print("=" * 90)
    print(f"陈永俊（真实征信 · v5算法）信用分：{features['credit_health_score']} | {features['risk_level']}")
    print(f"解读：{features['detailed_explanation']}")
    print(f"\n{'='*90}")
    print(f"{'排':3} {'类型':6} {'机构':10} {'产品':18} {'匹配':5} {'天花板':6} {'难度':5} {'通过率':6} {'利率':16} {'额度':6}")
    print("-"*90)
    for i, m in enumerate(matches, 1):
        print(f"{i:2}. [{m['institution_type']:5}] {m['bank']:10} {m['product_name']:16}"
              f"  {m['match_score']:3}分  ceil={m['score_ceiling']}  d={m['difficulty']}  apr={m['approval_rate']}"
              f"  {m['effective_rate']:16}  {m['max_amount']}万")

    print(f"\n{'='*90}")
    print("【v5分数分布验证（目标：20+种不同分数）】")
    p = features["_profile"]
    scores = []
    for _, row in df.iterrows():
        m, a = compute_match_score(p, row.to_dict())
        scores.append(m)
    dist = Counter(scores)
    print("分布：", dict(sorted(dist.items(), reverse=True)))
    non_zero = [s for s in scores if s > 0]
    print(f"最高:{max(scores)} 最低非零:{min(non_zero)} 均值:{sum(non_zero)/len(non_zero):.1f}")
    print(f"独立分数种数：{len(set(non_zero))} 种  拒贷：{scores.count(0)} 个")
