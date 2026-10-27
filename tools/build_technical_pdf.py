"""Build the technical handoff PDF using actual project evidence and screenshots."""
from html import escape
import sys
import json
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import __version__

OUT = ROOT / "output/pdf/初到-技术与复现说明.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont("CN", "C:/Windows/Fonts/msyh.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("CNBold", "C:/Windows/Fonts/msyhbd.ttc", subfontIndex=0))
GREEN = colors.HexColor("#164c47")
MUTED = colors.HexColor("#60716e")
LINE = colors.HexColor("#dce6e3")
BODY = ParagraphStyle("body", fontName="CN", fontSize=9.5, leading=16.5, textColor=colors.HexColor("#203837"), spaceAfter=11)
TITLE = ParagraphStyle("title", parent=BODY, fontName="CNBold", fontSize=21, leading=31, spaceAfter=22, textColor=GREEN)
H2 = ParagraphStyle("h2", parent=BODY, fontName="CNBold", fontSize=12, leading=20, spaceBefore=9, spaceAfter=10)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=13, textColor=MUTED)
story = []


def p(text, style=BODY):
    story.append(Paragraph(escape(text).replace("\n", "<br/>"), style))


def title(text):
    p(text, TITLE)


def heading(text):
    p(text, H2)


def bullets(items):
    for item in items:
        p("• " + item)


def table(rows, widths):
    values = [[Paragraph(escape(str(cell)), SMALL) for cell in row] for row in rows]
    grid = Table(values, colWidths=widths, hAlign="LEFT")
    grid.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4eeeb")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), .4, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.extend([grid, Spacer(1, 14)])


def screenshot(name, max_height=500):
    path = ROOT / "output/screenshots" / name
    if not path.is_file():
        return
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        width, height = im.size
    scale = min(511 / width, max_height / height)
    story.append(Image(str(path), width=width * scale, height=height * scale))
    story.append(Spacer(1, 15))


def newpage():
    story.append(PageBreak())


verification = json.loads((ROOT / "docs/verification.json").read_text(encoding="utf-8"))
before = json.loads((ROOT / "docs/evaluation-before.json").read_text(encoding="utf-8"))
after = json.loads((ROOT / "docs/evaluation-after.json").read_text(encoding="utf-8"))

story.append(Spacer(1, 95))
p("初到", ParagraphStyle("cover", parent=TITLE, fontSize=56, leading=70, spaceAfter=20))
p("河南科技职业大学\n新生指南", ParagraphStyle("cover-sub", parent=TITLE, fontSize=27, leading=42))
p("功能设计 · 资料溯源 · 本地复现", H2)
p("情景演练 / 校园探索 / 有来源的问答 / 持续行动计划")
story.append(Spacer(1, 35))
table([["交付版本", __version__], ["交付核查", "2026-10-15"], ["默认运行", "Python 标准库，本地资料模式，外部API关闭"], ["开发来源", "原作者项目接手后的委托协助开发，真实基线与变更记录已保留"]], [110, 380])
p("本文件说明当前实现与可验证的结果，不代替原作者完整AI对话、原创性证明或真实协同录屏。", SMALL)

newpage(); title("1  问题与产品闭环")
p("新生报到信息分散在通知、指南和地图中，年份不同、来源质量不一。直接给出一段看似确定的答案，可能把历史报到日期或第三方建议当成当前安排。")
heading("围绕三件真实任务")
bullets(["问清楚：从现有材料查找报到、缴费、手续和生活信息，展开每条来源。", "找得到：点选校园地点，对照原图理解相对位置，先确认宿舍名称与楼号。", "准备好：把材料和手续变成可勾选的清单，刷新后继续，并导出自己的记录。"])
heading("回答方式与诚实边界")
p("默认模式使用本地BM25和意图关键词检索，并摘录有依据的资料，不冒充大模型生成。有授权的新密钥可以显式启用DeepSeek生成；交接密钥始终在拒绝列表内。")
p("未确认当年日期、具体金额或开放状态时，程序明确提示未知。当前资料中的2024参考不能作为2026通知。地图只给图上位置，不提供测量坐标或实时路线。")
heading("已有功能")
table([["模块", "能力"], ["问答", "常见问题、自由问题、短追问、逐段响应、可展开引用"], ["地图", "45地点、搜索、区域筛选、缩放、大图"], ["准备清单", "11项建议、SQLite保存、刷新恢复、打印"], ["记录与来源", "对话保存、反馈、JSON导出、文档原文搜索"]], [100, 390])

newpage(); title("2  架构与额度保护")
table([["层", "职责"], ["浏览器", "同源静态界面；文本通过textContent展示"], ["HTTP服务", "Python标准库；静态白名单、参数验证、SSE"], ["检索", "中文二元词BM25；意图及专名权重；弱结果过滤"], ["回答", "来源限制、年份提醒、本地摘录、可选模型适配"], ["存储", "SQLite保存对话、清单、反馈、偏好和收藏，按会话隔离"]], [100, 390])
heading("默认不存在付费调用路径")
bullets(["程序不自动加载原backend/.env，不读取旧DEEPSEEK_API_KEY。", "GUIDE_ALLOW_REMOTE_LLM默认false；填入密钥本身不会启动模型调用。", "交接文件内同一个密钥只记录SHA-256指纹；即使显式启用，命中指纹仍拒绝请求。", "模型请求固定HTTPS目标，异常不回显供应商详细信息，引用编号异常回退本地回答。"])
p("本轮没有进行密钥有效性、余额或真实在线生成检查。默认启动与验收中的remote_calls为0。可选在线路径用模拟响应测试，不能据此声称在线回答质量已验证。", SMALL)

newpage(); title("3  资料来源与时效")
p("每个章节块继承文档头，稳定id由来源文件名和文本内容计算。来源链接、适用年份、采集日期、来源类型和限制随检索结果传到页面。")
table([["字段", "含义"], ["source / section / text", "来源文件、章节、原文"], ["source_header / urls", "不会因切分丢失的来源说明与链接"], ["effective_year", "参考内容的适用年份；未知与采集日期分开"], ["source_type / verified", "官方入口核对、继承参考、第三方参考、地图参考"], ["caveat", "该资料的限制与仍需核对的信息"]], [160, 330])
heading("核对范围")
p("学校官网服务入口、地址与咨询电话于2026-10-08核对。其他继承资料尚未逐项核实，当年完整入学须知未收录为已验证事实。官方页面入口存在，并不证明继承文章中的所有政策当前有效。")
heading("地图修正")
p("原图左侧的馨园宿舍分两片；右上部为沁园宿舍。旧文本“馨园1–20全部位于北部”与图中文字不符，已修正为图上位置，保留地图年代及设施开放情况未知的说明。")
heading("来源网页")
p("学校官网：https://www.hnvust.cn/\n招生信息网：https://zhaoshengchu.hnvust.cn/", SMALL)

newpage(); title("4  检索与意图控制")
bullets(["中文二元词与英文/数字词用于BM25；常见问句词降低影响。", "饭卡、交钱等口语规范为资料中的词；材料、缴费、报到点和具体建筑获得相应章节权重。", "结果必须命中主题关键词，按排名过滤弱结果；最多返回三个证据块。", "短指代追问只使用用户前文，不把AI已生成的内容当作检索事实。", "日期、收费金额、设施开放状态的未知信息，先提示适用范围，再提供可核对的摘录。"])
heading("实际失败驱动的迭代")
p("浏览器中，“报到要带什么材料？”首版把户口迁移排第一，并夹带报到日期。增加材料意图匹配、过滤弱结果后，首条变为“入学准备清单·必备材料”，回答集中在录取通知书、身份证和照片等准备信息。")
table([["固定FAQ检查", "修改前", "修改后"], ["首条结果关键词覆盖", f"{before['passed']}/{before['total']}", f"{after['passed']}/{after['total']}"]], [270, 110, 110])
p("该指标是显式18题的小规模检索覆盖检查，不是模型准确率，不证明任意问题均有正确答案。政策事实仍需要官方资料核对和人工答复质量评审。", SMALL)
heading("可选大模型约束")
p("系统提示要求只根据编号资料回答，保留年份、不确定性和缺失事实；资料与用户文字不作为系统指令执行。生成结果须引用已给出的编号，编号缺失或越界则回退。格式校验不能替代逐项事实核查。")

newpage(); title("5  问答与成长计划界面")
screenshot("plan.png", 490)
p("1.1.0个人成长计划的真实浏览器验证截图。左侧设置兴趣与位置偏好，右侧展示推荐、理由、取舍与收藏操作。验证场景选编程兴趣，结果来自本地参考资料。", SMALL)
bullets(["引用原文使用原生details展开，可通过键盘操作。", "用户文本和来源不作为HTML执行；异步状态与提示使用aria-live。", "390px手机布局已核查无横向溢出；减弱动画偏好被尊重。"])

newpage(); title("6  校园地图与准备清单")
screenshot("map-110.png", 445)
p("实际地图界面截图。热点位置来自交接原图，明确区分馨园和沁园。移动端提供地点列表操作，避免密集热点重叠。", SMALL)
p("11项准备建议按出发前、报到当天、入校后分组。状态保存于SQLite，刷新可继续；材料数量、地点、缴费方式以当年学校通知为准。清单不收集姓名、证件或银行卡信息。")

newpage(); title("7  工程验证与局限")
p(f"最终回归：{verification['tests']}项；失败{verification['failures']}项；错误{verification['errors']}项。检查包括本地HTTP与被mock的外部适配器。")
table([["验证维度", "核查内容"], ["额度保护", "默认禁用、环境变量不触发、交接指纹拒绝、外部失败回退"], ["资料与回答", "来源年份不丢失、材料排序、专名、陌生问题、追问、未知日期/金额/开放时间"], ["持久化", "会话隔离、清单刷新、反馈归属、清空对话保留清单"], ["接口", "健康统计、中文SSE、跨站Origin/陌生Host拒绝、输入限制、私有路径拒绝、CSP"], ["浏览器", "问答引用、反馈保存、清单刷新、地图选点缩放、手机无横向溢出，控制台无报错"]], [110, 380])
heading("Windows真实故障与修复")
p("SQLite事务上下文不自动关闭连接，最初测试清理数据库出现文件占用。显式关闭连接后通过；服务沙箱回环访问受阻，批准在本机回环地址启动后完成浏览器验收。")
p("1.0.1交付前复查修正了行李问题排序、军训历史来源、反向日期问法与时长提醒、外部失败回退提示，并统一旧说明。干净会话中核对问答引用、刷新恢复和实际导出JSON；新增五项回归全部通过。")
heading("能力边界")
bullets(["本地摘录的表达与推理能力有限，不能等同在线大模型质量。", "继承资料尚未逐项验证当前政策；在线生成尚未消耗真实额度验收。", "服务面向单机评审，未提供公网身份认证、学校正式办理或实时导航。"])

newpage(); title("8  十分钟内复现")
p("环境：Python3.10或以上、现代浏览器。无需第三方运行依赖，不携带原1.61GB虚拟环境。资料读取和索引发生在启动时。")
table([["步骤", "操作"], ["1 解压", "解压运行包至任意目录，保留原目录结构"], ["2 启动", "项目根目录：python -X utf8 -S run.py"], ["3 访问", "http://127.0.0.1:8765/"], ["4 检查", "/api/health：status=ok，remote_enabled=false，remote_calls=0"], ["5 验证", "python -X utf8 -I -S tools/verify.py"], ["6 复核检索", "python -X utf8 -I -S tools/evaluate_retrieval.py"]], [90, 400])
heading("常见问题")
bullets(["端口占用：使用--port 8766，浏览器访问对应端口。", "修改资料后：重启服务，无需联网入库或模型下载。", "记录保存：默认写入.runtime；保持目录可写，浏览器保留本地会话标识。", "无法访问：确认服务正在运行；严格沙箱需允许本机回环网络，应用仍保持离线。"])
p("启动README、完整接口、实际验证JSON与运行包一同交付。Git历史以bundle保留；原始交付、密钥文件、虚拟环境与个人运行数据不包含在运行包内。")

newpage(); title("9  真实演进与参赛材料")
table([["提交", "实际内容"], ["969ca1e", "记录接收到的现有项目基线与文件哈希核查"], ["b6fc7c4", "定位交接密钥、保存拒绝指纹、显式启用外部请求"], ["3e36860", "来源/年份元数据、本地证据问答、模拟外部边界与回归"], ["0190f52", "新生指南界面、地图、清单、持久化与来源阅读"]], [100, 390])
p("这些是收到已有项目之后实际发生的提交。初始完整基线不伪装成从零开发；未倒填早期日期、未编造AI对话。实际后续提交可通过git log查看。")
heading("仍需原作者完成的真实材料")
bullets(["核实赛事对委托协助开发的要求，按真实贡献说明来源；确认个人参赛资格与组别。", "导出原始AI聊天/截图/录屏，补齐至少三个核心迭代的完整Prompt链。总结日志不能替代这些证据。", "录制5–8分钟1080p演示，含至少2分钟真实AI协同过程。已提供6分30秒脚本。", "核对官方赛程与正式提交入口，设置仓库评审访问权限；本轮未公开发布或推送。"])
p("赛事评分、日期和材料规格依据用户提供文本。该文本存在赛程顺序与奖项比例矛盾，尚未取得官方同名页面独立确认。PDF页数与演示脚本时长满足准备规格，但完整参赛合规性不能由软件测试证明。", SMALL)


newpage(); title("10  从资料浏览到参考选择")
p("作者在1.0.1上新增宿舍、竞赛、社团和学生组织模块。收到2026-10-11雏形后，本轮按其方向增加可保存偏好、解释推荐、同类对比、收藏进度和下一步建议。输入基线365f93e和后续优化分开记录。")
table([["模块", "可使用的行为"], ["统一目录", "10床位参考、67不同名称竞赛、16社团示例、14组织示例"], ["偏好", "9个兴趣、专业方向、课外时间、4个位置因素"], ["推荐", "每类最多6项；显示命中理由、取舍和同分提示"], ["对比", "同类最多3项，原生表格，对照内容、适合人群和资料限制"], ["收藏", "最多30项；准备了解、正在尝试、已完成了解"], ["保存与导出", "SQLite按会话保存；JSON包含偏好、收藏及下一步"]], [110,380])
heading("老师可以实际验证的变化")
p("六人寝安静权重设3，其他设0，2和5号中间位并列优先；改采光权重为3，则3和4号靠阳台位优先。选择编程兴趣可看到计算机、电子科技和建模协会示例，每项列出命中的原文词。保存收藏后刷新，修改了解进度再导出，记录会保留。")
p("规则分数仅作同类排序，不是适配概率、录取率或官方评分。课外时间用于提醒，未虚构每个组织的投入小时。")

newpage(); title("11  同类对比与位置取舍")
screenshot("bed-comparison.png", 460)
p("实际网页对比表：中间位的2和5号在位置因子上并列。图上因素0–3是开发者按相对位置给出的参考值，不是实测噪音、湿度或采光。不能据此保证环境。", SMALL)
p("六人寝已纠正原雏形的标注：1与6靠门，2与5为中间位，3与4靠阳台和卫浴。收藏只是偏好记录，不能预订实际床位。")
p("竞赛、社团和学生组织也可对比。它们仍为交接参考，未确认本校当年实际开设、招新、参赛资格或认定；原指南A/B/C保留为参考标签，取消统一等级和加分承诺。")

newpage(); title("12  新模块验证与交回作者")
p("1.1.0当时44项回归通过；1.2.0为59项；1.3.0当时68项；1.4.0为80项；1.5.0为81项；当前1.6.0为82项。原18个FAQ首条关键词覆盖18/18，新增4题4/4；这些指标不等于问答正确率。网页实际验证保存偏好、两类收藏、三项对比上限、了解进度、刷新恢复和导出的JSON内容。")
p("修复了电子竞技误命中技术兴趣、地图大类引用粒度不足及页面切换滚动位置的问题。当前19份资料中的235个文本块均保留来源限制；新增成长资料标为第三方参考。")
screenshot("mobile-plan.png", 330)
p("390像素手机验证场景，无横向溢出。导航、偏好控件、推荐和对比都有触屏与键盘可操作入口。", SMALL)
p("原作者可沿README启动并复现上述场景；代码、当前回归结果、PDF、截图和真实Git bundle一同交付。默认API关闭，没有消耗作者额度，未公开发布或完成赛事提交。")


newpage(); title("13  持续行动：日程、任务与备份")
p("2026-10-13接收作者新版，输入以979aa7d保存。本轮新增个人任务、下一步转待办、7天视图、可恢复归档、全天日历与备份预览合并。截图来自独立测试数据库，日期和进度为验证场景。")
screenshot("tasks-120.png", 490)
p("日期由使用者安排，最多100项（含归档）；网页只显示提示。日历只导出有日期的未完成任务，实际日历应用导入及其提醒未测试。备份只合并任务，跳过重复并保留旧进度，超限或非法字段整批拒绝。", SMALL)
p("移除作者包中的自动百度/必应抓取与Playwright启动，改为主动公开通知核对链接。固定主题搜索不会发送完整问题，不把搜索摘要变成事实。默认未使用作者API，所有新增功能可离线验证。", SMALL)
p("1.2.0当时59项回归通过，包含会话隔离、上限、备份原子合并与ICS转义/UTF-8折行。390px任务页与弹窗无横向溢出；历史证据见功能优化与验收-1.2.0.md。", SMALL)

newpage(); title("14  在出发前演练真实问题")
p("1.3.0新增出发前、报到当天、入校后9个场景。选择处理方式后提供解释、建议和可展开的原文依据，记录最近一次选择，允许复习和修改。截图为独立测试会话，准备清单没有因答对自动勾选。")
screenshot("arrival-130.png", 400)
p("练习覆盖往年日期、重要证件、收款码、接站、同名建筑、床位收藏、设施开放、社团开设与竞赛认定。推荐选项属于参考建议，不是考试、官方评分或完成报到的证明。", SMALL)
p("原文保持来源类别、历史年份和限制；不新增虚构的当年通知。题目、解释和记录均在本机运行，不调用API。", SMALL)

newpage(); title("15  从单地点地图到探索行程")
p("从45个示意地点选择最多8个；提供生活服务、学习空间、课后探索3条参考行程。支持上下移、到访勾选、只看行程、刷新保存及TXT导出。截图中图书馆已上移并标记到访。")
screenshot("itinerary-130.png", 430)
p("地图连线仅表示探索先后顺序，可能跨过建筑，不是实际道路、最短路或实时导航。没有GPS、距离、步行时长和开放时段推断。", SMALL)
p("1.3.0当时68项回归通过。实际浏览器验证了演练修改、行程排序、到访持久化及TXT下载；390px手机和1280px桌面无页面横溢出。多页操作使用revision与事务防止覆盖；新功能不修改旧任务和准备进度。", SMALL)
p("最后修复切换场景与移动/删除地点的焦点衔接，5项受控DOM脚本回归通过，独立复核确认这两项已解决。原生浏览器键盘、焦点外观与滚动位置尚未复测。", SMALL)


newpage(); title("16  出发准备、行李与备忘卡")
p("1.4.0新增出发准备台。自己填写出行日期、到校时间、宿舍区域与备注，显示个人倒计时；15种参考物品可修改数量与状态，最多补充20种自己的物品。")
screenshot("preparation-overview-140.png", 390)
p("从物品打开可编辑待办，购买日期默认自己的预计到校日；已保存宿舍可在地图定位。备忘卡汇总保存记录，支持TXT和打印；专用备份先预览再恢复，只替换准备台。", SMALL)
p("1.4.0当时80项回归通过。Edge真实页面验证保存、刷新、备份恢复、任务、地图和手机Enter键焦点。打印CSS与Edge生成PDF已检查，未测试实体打印机。默认外部模型关闭，调用次数为0。", SMALL)
p("这些是个人安排与参考打包建议，不是学校当年通知或统一采购清单。照片规格、床品尺寸、档案方式和交通携带要求仍需自行核对。", SMALL)


newpage(); title("17  自定义外观与开场动画")
p("1.5.0保留浅色、深色，新增冷蓝科技自定义模式。右上角外观入口在手机同样可用；自己的背景图可调整遮罩、模糊和位置，浏览器本机保存，不上传或调用API。")
screenshot("custom-grid-150.png", 235)
screenshot("intro-150.png", 170)
p("开场约2.4秒，标志与文字依次出现，可点击跳过或按Esc；同标签刷新不重播，可关闭及预览。减少动态效果时自动跳过，预览静态显示。没有音频、假进度或联网加载承诺。", SMALL)
p("1.5.0当时81项回归与15项Edge浏览器检查通过，包含图片保存恢复、异常保留旧图、三模式、手机布局、动画和记录保持。背景按浏览器站点存储，换浏览器/端口需重设，不随任务备份同步。", SMALL)

newpage(); title("18  校园形象：由线条到色彩")
p("1.6.0使用用户提供的学校形象参考，通过内置imagegen提取完整透明角色，保留深蓝长发、伸手姿势、校服披风与红色地标饰件。属于参考图的衍生素材，并非另行确认的校方官方新形象。最终提示词与素材哈希随源码保存。")
screenshot("mascot-lines-160.png", 210)
screenshot("mascot-color-160.png", 210)
p("每种姿势各自的SVG轮廓按顺序绘制，约2.3秒后显色，总开场约4.2秒；默认坐姿阅读1161条轮廓。可即时跳过、关闭、重播。减少动态效果时自动略过，预览显示静态角色。手机重新编排文字与完整角色，素材缺失时欢迎文案仍可读且自动退出。", SMALL)
p("内置校园形象背景显示完整人物，可调虚化、遮罩和位置；个人图片选项仍可用，已有偏好与指南记录保留。82项回归、26项Edge检查通过，项目外部模型调用为0；图像制作使用内置生成工具。", SMALL)

newpage(); title("19  更多动作、表情与视角")
p("素材库共14张透明PNG：4款原画、6款Q版日常、4款表情与视角。新增侧脸低头专注、仰头闭眼大笑、背身惊喜回眸、趴桌小憩，让视线、眉眼、嘴型及头部透视有明显变化；腿部重心、裙摆和披风随姿势重绘。")
screenshot("mascot-expression-gallery-160.png", 280)
screenshot("creative-rest-160.png", 180)
p("选取素材后，开场和校园形象背景同步使用该姿势；支持大图查看、真实PNG下载和刷新恢复。单独素材包包含PNG、各自SVG描线数据、完整提示词和哈希，可用于作者后续展示或继续制作动作。", SMALL)
p("本轮为姿势插画与描线/显色开场，不提供连续走路、坐下过程的逐帧视频或骨骼工程。已有记录保持不变，快速切换素材不会被旧加载结果覆盖。", SMALL)


def page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(GREEN)
    canvas.setFont("CN", 8)
    canvas.drawString(42, height - 28, "初到  /  新生指南技术交付")
    canvas.setStrokeColor(LINE)
    canvas.line(42, height - 36, width - 42, height - 36)
    canvas.line(42, 35, width - 42, 35)
    canvas.setFillColor(MUTED)
    canvas.drawString(42, 22, __version__ + "  |  2026-10-15  |  协助开发交付版")
    canvas.drawRightString(width - 42, 22, str(doc.page))
    canvas.restoreState()


document = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=56, bottomMargin=48, title="初到-技术与复现说明", author="项目协助开发记录")
document.build(story, onFirstPage=page, onLaterPages=page)
print(OUT)
