#!/usr/bin/env python3
"""高质量题库生成器 — 每科每知识点生成10道选择题，严格验证格式"""

import json, os, urllib.request, time, re

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/chat/completions"

SUBJECTS = {
    "语文": {
        "icon": "📖", "color": "#e74c3c",
        "kps": [
            "字音字形", "成语辨析", "病句修改", "文言文实词", "文言文虚词",
            "古诗词鉴赏", "现代文阅读", "文学常识", "修辞手法", "语言表达",
            "文言文翻译", "名句默写", "通假字与古今异义", "词类活用", "特殊句式"
        ]
    },
    "数学": {
        "icon": "📐", "color": "#3498db",
        "kps": [
            "集合的概念与运算", "函数的概念与定义域", "函数的单调性与奇偶性",
            "指数与对数运算", "指数函数与对数函数", "等差数列", "等比数列",
            "三角函数的定义", "三角恒等变换", "平面向量", "向量的坐标运算",
            "不等式的性质与解法", "排列组合与概率", "统计图表与数据特征",
            "直线与圆的方程", "椭圆双曲线抛物线"
        ]
    },
    "英语": {
        "icon": "🌍", "color": "#2ecc71",
        "kps": [
            "名词与冠词", "动词时态语态", "定语从句", "名词性从句",
            "状语从句", "非谓语动词", "虚拟语气", "完形填空",
            "阅读理解", "词汇辨析", "介词搭配", "倒装与强调"
        ]
    },
    "政治": {
        "icon": "⚖️", "color": "#f39c12",
        "kps": [
            "商品与货币", "价格与供求", "生产与经济制度", "财政与税收",
            "市场经济与宏观调控", "公民政治参与", "政府职能与责任",
            "人大制度与民主政治", "国际关系与外交政策", "唯物论与辩证法",
            "认识论与真理", "历史唯物主义", "价值观与人生价值", "文化传承与创新"
        ]
    },
    "历史": {
        "icon": "📜", "color": "#9b59b6",
        "kps": [
            "先秦时期", "秦汉统一", "三国两晋南北朝", "隋唐盛世",
            "宋元经济文化", "明清政治经济", "鸦片战争与近代开端",
            "洋务运动与民族工业", "辛亥革命与民国建立", "五四运动与中共成立",
            "抗日战争", "解放战争与建国", "改革开放", "世界古代文明", "工业革命与资本主义"
        ]
    },
    "地理": {
        "icon": "🌏", "color": "#1abc9c",
        "kps": [
            "地球与地图", "大气环流与气候", "水循环与河流", "地质作用与地貌",
            "人口增长与迁移", "城市化", "农业区位与地域类型", "工业区位与工业区",
            "交通运输布局", "区域可持续发展", "中国地理分区", "世界地理概况",
            "资源开发与保护", "自然灾害与防治", "地理信息技术"
        ]
    }
}

PER_KP = 10  # questions per knowledge point

def call_deepseek(prompt, max_retries=3):
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是高中题库专家。只输出有效JSON数组，不要markdown包裹，不要任何解释文字。输出必须是可直接解析的JSON。"},
            {"role": "user", "content": prompt}
        ],
        "stream": False, "temperature": 0.7, "max_tokens": 8000
    }).encode('utf-8')
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(API_URL, data=payload, headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}"
            })
            resp = urllib.request.urlopen(req, timeout=90)
            text = json.loads(resp.read().decode())["choices"][0]["message"]["content"]
            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r'^```\w*\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
            return json.loads(text)
        except Exception as e:
            print(f"  Retry {attempt+1}/{max_retries}: {e}")
            time.sleep(5)
    return None

def validate_question(q):
    """Return list of issues, empty = valid"""
    issues = []
    if len(q.get('question_text', '')) < 10: issues.append('question_too_short')
    if len(q.get('answer', '')) < 1: issues.append('no_answer')
    for opt in ['a','b','c','d']:
        val = q.get(f'option_{opt}', '')
        if len(val) < 1: issues.append(f'option_{opt}_empty')
    if q.get('correct_option', '') not in 'ABCD': issues.append('bad_correct')
    if q.get('difficulty', 0) not in [1,2,3]: issues.append('bad_diff')
    return issues

def main():
    print("🚀 Generating high-quality question bank...")
    
    # Build fresh data from scratch
    subjects_data = []
    kps_data = []
    questions = []
    
    sid = 1
    kpid = 101
    qid = 10001
    
    for sub_name, cfg in SUBJECTS.items():
        subjects_data.append({
            "id": sid, "name": sub_name, "icon": cfg["icon"], "color": cfg["color"]
        })
        
        for i, kp_name in enumerate(cfg["kps"]):
            print(f"\n📝 {sub_name} > {kp_name} ({PER_KP} questions)")
            
            kps_data.append({
                "id": kpid, "subject_id": sid, "name": kp_name,
                "unit": f"知识点{i+1}", "semester": "高三"
            })
            
            prompt = f"""生成{PER_KP}道高中{sub_name}选择题，知识点：「{kp_name}」。
要求：
- 4个选项(A/B/C/D)，每题标明正确选项
- 难度分布：3道简单(difficulty=1)、4道中等(2)、3道困难(3)
- 题目用中文，选项完整有意义（不能是单个数字/字母）
- 每题包含简短hint（10-30字解题提示）

输出纯JSON数组（不要markdown）：
[
  {{
    "question_text": "...",
    "answer": "标准答案",
    "hint": "解题提示",
    "difficulty": 1,
    "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...",
    "correct_option": "A"
  }},
  ...
]"""
            
            result = call_deepseek(prompt)
            if not result or not isinstance(result, list):
                print(f"  ❌ Failed, retrying once...")
                time.sleep(3)
                result = call_deepseek(prompt)
            
            if not result or not isinstance(result, list):
                print(f"  ❌ Skipping {kp_name}")
                kpid += 1
                continue
            
            valid_count = 0
            for q in result:
                if not isinstance(q, dict): continue
                issues = validate_question(q)
                if issues:
                    print(f"  ⚠ Bad question: {issues}")
                    continue
                try:
                    questions.append({
                        "id": qid, "kp_id": kpid, "subject_id": sid,
                        "question_text": q.get("question_text",""),
                        "answer": q.get("answer",""),
                        "accept_answers": "",
                        "hint": q.get("hint", ""),
                        "difficulty": q.get("difficulty", 1),
                        "option_a": q.get("option_a",""), "option_b": q.get("option_b",""),
                        "option_c": q.get("option_c",""), "option_d": q.get("option_d",""),
                        "correct_option": q.get("correct_option",""),
                        "kp_name": kp_name, "subject_name": sub_name,
                        "icon": cfg["icon"], "color": cfg["color"]
                    })
                except Exception as e:
                    print(f"  ⚠ Append error: {e}")
                    continue
                qid += 1
                valid_count += 1
            
            print(f"  ✅ {valid_count}/{PER_KP} valid")
            kpid += 1
            time.sleep(0.5)
        
        sid += 1
    
    # Build output
    output = {
        "questions": questions,
        "knowledge_points": kps_data,
        "subjects": subjects_data
    }
    
    with open("static/offline-data.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"✅ Done! {len(questions)} questions, {len(kps_data)} KPs, {len(subjects_data)} subjects")
    from collections import Counter
    subs = Counter(q["subject_name"] for q in questions)
    for s, c in sorted(subs.items()):
        print(f"  {s}: {c}")

if __name__ == "__main__":
    main()
