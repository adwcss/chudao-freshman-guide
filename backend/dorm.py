"""Received dorm photos and illustrative positions; no booking or real availability."""
DORM_GALLERY = [
    {"id": "toilet", "title": "卫生间参考", "desc": "交接照片，实际设施请现场核对。", "img": "/dorm-images/siren-toilet.jpg"},
    {"id": "washstand", "title": "洗漱台参考", "desc": "交接照片，实际设施请现场核对。", "img": "/dorm-images/siren-sink.jpg"},
    {"id": "bathroom", "title": "卫浴间参考", "desc": "交接照片，实际设施请现场核对。", "img": "/dorm-images/liuren-bath.jpg"},
    {"id": "laundry", "title": "洗衣房参考", "desc": "交接照片，不代表当前设备或开放情况。", "img": "/dorm-images/laundry.jpg"},
]
POSITIONS = {
    "window": {"tags": ["靠阳台/窗侧", "上床下桌"], "pros": ["图上更接近阳台与窗户，可能有较好采光和通风", "洗漱与晾晒路径较短"], "cons": ["可能受光线、阳台活动和卫浴声影响", "实际朝向、温度与湿度需现场核对"], "fit": "比较在意采光、能接受阳台活动的同学可优先了解。", "metrics": {"quiet": 1, "light": 3, "access": 1, "dry": 1}},
    "middle": {"tags": ["中间位", "上床下桌"], "pros": ["图上离入口和卫浴都有一段距离", "在门窗距离之间较为均衡"], "cons": ["不保证安静，仍受室友作息影响", "采光和通风需现场观察"], "fit": "在意睡眠、想减少门口和卫浴影响的同学可优先了解。", "metrics": {"quiet": 3, "light": 2, "access": 2, "dry": 2}},
    "door": {"tags": ["靠门侧", "上床下桌"], "pros": ["图上距入口更近，进出路径较短", "图上离卫浴较远"], "cons": ["可能受走廊声音和开关门影响", "隐私与冷暖感受需现场核对"], "fit": "经常进出、对门口声音不敏感的同学可优先了解。", "metrics": {"quiet": 1, "light": 1, "access": 3, "dry": 3}},
}


def bed(number, x, y, position):
    return {"id": str(number), "name": f"{number}号床", "x": x, "y": y, "position": position, **POSITIONS[position]}


DORM_ROOMS = {
    "siren": {"name": "四人寝", "env_img": "/dorm-images/siren-env.jpg", "env_desc": "交接照片中的上床下桌布局，仅作环境参考。", "select_img": "/dorm-images/siren-plan.jpg", "layout": "4 个床位，编号由本模块为示意添加。", "tip": "1、2号靠阳台侧；3、4号靠门侧。此处不能预订床位，实际分配以学校安排为准。", "beds": [bed(1, 15, 45, "window"), bed(2, 85, 45, "window"), bed(3, 15, 82, "door"), bed(4, 85, 82, "door")]},
    "liuren": {"name": "六人寝", "env_img": "/dorm-images/liuren-env.jpg", "env_desc": "交接照片中的六人布局，仅作环境参考。", "select_img": "/dorm-images/liuren-plan.jpg", "layout": "图上为 1–6 号，左右各三个床位。", "tip": "1、6号靠门；2、5号为中间位；3、4号靠阳台与卫浴侧。不同因素各有取舍，没有固定最优床位。", "beds": [bed(1, 17, 88, "door"), bed(2, 17, 66, "middle"), bed(3, 17, 43, "window"), bed(4, 84, 43, "window"), bed(5, 84, 66, "middle"), bed(6, 84, 88, "door")]},
}
