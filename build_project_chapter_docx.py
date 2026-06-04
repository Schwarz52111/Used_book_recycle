from html import escape
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


OUT = Path("第三章_项目产品与技术体系.docx")


TITLE = "第三章 项目产品与技术体系"
SUBTITLE = "二手图书自助回收售卖一体机软件系统方案"


SECTIONS = [
    (
        "3.1 项目整体方案概述（零硬件改造、纯软件系统重构）",
        [
            "本项目拟构建一款面向校园师生的二手图书自助回收售卖一体机，其核心定位并不是重新研发一套复杂昂贵的硬件设备，而是在已有自助终端设备形态的基础上完成面向二手书流通场景的软件系统重构。校园中每学期都会产生大量教材、教辅、专业参考书和课外读物的闲置问题，一方面学生在课程结束后缺少便捷、可信、价格合理的处理渠道，另一方面新生或后续选课学生又存在低价购书的现实需求。传统二手书交易主要依靠微信群、线下摊位或个人转让，交易效率较低，价格缺乏统一标准，书籍品相难以快速判断，也无法形成持续稳定的库存管理机制。因此，本项目试图将图书馆自助借还机中成熟的自助交互模式迁移到校园二手书回收与售卖场景中，通过软件系统重新定义设备功能，使其成为集图书识别、价值评估、回收入库、库存管理和自助售卖于一体的校园循环利用终端。",
            "从整体方案来看，系统的技术实现重点集中在软件层面，包括图像采集与识别、数据库匹配、品相检测、智能定价、库存状态管理、热度统计和规则调控等模块。设备仍可沿用原有摄像装置、触控屏、扫码组件、储书结构和支付交互能力，项目主要通过重写业务流程和后台数据逻辑来改变设备用途。与从零设计硬件相比，这种零硬件改造或低硬件改造的方式能够显著降低落地成本，也便于在校园现有自助设备或闲置终端基础上进行试点部署。项目的软件系统会围绕“回收端”和“售卖端”两个方向形成闭环：在回收端，学生将闲置书籍放置在识别区域，系统采集图书封面、书脊或条码图像，识别书籍身份并评估品相；在售卖端，学生可通过设备界面浏览当前库存中的二手书，查看书籍信息、品相等级和售价，并完成自助购买。",
            "该方案的价值不仅在于提供一个二手书交易工具，更在于建立校园内部图书资源循环利用的数字化管理体系。过去二手书流转更多依赖个人之间的零散交易，缺乏统一的数据沉淀，学校或运营方难以判断哪些书籍需求量高、哪些书籍长期滞销，也无法根据真实交易数据优化回收规则。本项目通过设备端和数据库系统持续记录书籍回收量、售出量、库存周期、浏览量和成交价格等信息，使二手书流通从偶发性交易转变为可统计、可分析、可调控的资源再分配过程。由此，设备不仅可以帮助学生处理闲置书籍，也可以为校园绿色低碳建设、教材循环使用和资源节约提供可量化的数据支撑。",
        ],
    ),
    (
        "3.2 设备功能重构逻辑（废弃原有借还功能，全新二手书专属系统）",
        [
            "传统图书馆自助借还机的业务逻辑主要服务于馆藏图书管理，其核心任务是识别馆藏条码或 RFID 信息，完成借阅登记、归还登记和读者账户状态更新。此类设备面对的对象通常是图书馆已经入库、信息完整、状态受控的馆藏图书，系统并不需要判断图书是否属于可回收资源，也不需要独立评估图书价格和品相。相比之下，二手图书回收售卖一体机面对的是学生个人闲置书籍，这些书籍来源分散、版本多样、磨损程度不一，甚至可能存在条码遮挡、封面破损、书名识别困难等情况。因此，本项目必须废弃原有借还逻辑，将设备功能重新设计为二手书专属业务流程。",
            "功能重构的第一层是识别对象和数据来源的变化。原有借还系统依赖图书馆馆藏数据库，而本项目需要建立面向二手书交易的书籍基础数据库和库存数据库。系统不再默认每本书已经存在于馆藏系统中，而是需要通过 ISBN 条码识别、OCR 文字识别和 AI 图像识别等方式主动提取书籍信息，并将识别结果与本地数据库或后续扩展的网络书籍信息库进行匹配。对于已经在数据库中登记的常见教材和热门书籍，系统可以快速获得作者、出版社、分类、原价、二手市场参考价等信息；对于数据库中暂未收录的书籍，则可以进入人工复核或后台补录流程，从而逐步扩充可识别书籍范围。",
            "功能重构的第二层是业务目标的变化。借还机的目标是管理图书借阅状态，而本项目设备的目标是完成二手书的价值判断与流通转化。学生投入书籍后，系统需要判断该书是否符合回收条件、是否具有校园流通价值、当前库存是否已经过量，并在此基础上给出建议回收价格。如果学生接受价格，设备会生成回收记录并将书籍纳入库存；如果学生不接受价格，则系统应允许取消回收并归还书籍。进入库存后的图书不再是简单的“已归还”状态，而是具有待复核、可售卖、已售出、滞销、下架等多种状态。由此可见，本项目的设备重构并不是界面层面的简单替换，而是业务逻辑、数据模型和管理规则的整体转换。",
            "功能重构的第三层是从单向管理转向双向流通。传统借还机只服务于图书馆和读者之间的借阅关系，而二手书一体机需要同时服务“卖书学生”和“买书学生”两个群体。设备既要保证回收环节价格合理、操作简便，也要保证售卖环节信息透明、库存可查、购买便捷。系统通过将回收端和售卖端连接在同一个库存管理体系中，使一本书从学生闲置物品转化为可被其他学生低价购买的校园资源。该过程提升了设备的使用频率和服务半径，也使原本相对单一的自助终端具备更高的校园公共服务价值。",
        ],
    ),
    (
        "3.3 AI图像识别书籍品相质检技术原理",
        [
            "二手书回收过程中的关键问题在于品相判断。一本书即使书名、版本和出版社完全相同，其实际回收价值也会因为使用痕迹、封面磨损、书页缺失、污渍程度和装订完整性不同而产生明显差异。传统人工回收虽然可以依靠经验判断品相，但效率较低，且不同人员之间标准不完全一致，容易导致定价不稳定。为解决这一问题，本项目设计 AI 图像识别书籍品相质检模块，通过摄像装置采集图书图像，并结合图像预处理、文字识别、视觉模型分析和人工复核机制，对书籍状态进行相对标准化的判断。",
            "在识别流程上，系统首先对图书进行图像采集。设备摄像头可拍摄封面、封底、书脊和条码区域，系统对采集图像进行亮度校正、角度修正、分辨率压缩和清晰度检测，以保证后续识别模型获得较稳定的输入。系统会优先识别 ISBN 条码，因为 ISBN 是确定图书身份最直接、最准确的依据。当条码清晰可见时，系统可以直接通过 ISBN 在数据库中检索书籍信息，减少 OCR 识别误差。若条码识别失败，系统则对封面文字进行 OCR 识别，提取书名、作者、出版社等关键词，并通过模糊匹配算法与数据库中已有书籍进行比对。这样的多路径识别方式能够提升系统对不同摆放角度、不同封面样式和不同磨损情况书籍的适应能力。",
            "在品相质检方面，AI 图像识别并不只是识别书名，而是对书籍外观状态进行综合判断。系统可以根据图像中封面边角是否卷曲、表面是否存在明显污渍、封面是否撕裂、书脊是否破损、书页是否明显变形等特征，对书籍品相进行等级划分。项目中可将品相分为近全新、良好、可接受和破损四类，不同品相等级对应不同价格系数。近全新书籍通常只有极轻微使用痕迹，适合按较高系数回收；良好书籍允许少量折角或标注；可接受书籍虽然存在明显使用痕迹，但内容完整且仍具备阅读价值；破损书籍则可能存在缺页、严重污渍、装订松散等问题，应显著降低回收价格，甚至拒绝回收。",
            "需要强调的是，AI 质检在本项目中承担的是辅助决策功能，而不是完全替代人工判断。二手书品相具有一定主观性，且部分问题需要翻页检查才能确认，例如内页缺失、大量笔记、局部水渍和装订开裂等。对于识别置信度较低、系统判断结果与价格差异较大、图像质量不佳或图书价值较高的情况，系统应进入人工复核流程，由后台工作人员对书籍信息和品相等级进行确认。通过“AI 初筛+人工复核”的组合机制，既可以提高处理效率，又可以降低误判风险，使系统在技术可行性和运营可靠性之间取得平衡。",
        ],
    ),
    (
        "3.4 大数据书籍热度分析与准入调控系统",
        [
            "二手书回收系统如果只关注单本书的识别和估价，容易出现库存结构失衡的问题。校园中不同类型书籍的需求差异明显，例如公共基础课教材、热门专业课教材、考研资料和等级考试辅导书通常具有较高流通性，而部分过期教材、版本更新较快的参考书或受众较窄的冷门书籍则可能长期滞销。如果设备对所有书籍都按照固定规则回收，就会造成热门书供给不足、冷门书库存积压的问题。因此，本项目在系统设计中加入大数据书籍热度分析与准入调控模块，用数据反馈机制指导回收规则调整。",
            "该模块的核心思想是将每一本书的回收、浏览、购买和库存变化转化为可统计指标，并通过这些指标判断书籍在校园场景中的真实流通价值。系统可以记录书籍 ISBN、分类、回收时间、回收数量、品相等级、售卖价格、成交次数、平均售出周期、库存剩余数量和用户浏览次数等数据。随着设备运行时间增加，数据库会逐步形成校园二手书流通画像：哪些书在开学初需求较高，哪些书在考试季浏览量上升，哪些书虽然回收数量多但售出速度慢，哪些书长期处于缺货状态。这些数据可以帮助系统从被动接收书籍转变为主动调控库存。",
            "在热度指标设计上，系统可综合考虑浏览量、成交量、库存周转率和缺货频次等因素。浏览量反映学生对某本书的关注程度，成交量反映真实购买需求，库存周转率反映书籍从入库到售出的速度，缺货频次则说明该书可能存在供不应求的情况。对于浏览量高、成交快、库存低的书籍，系统可判断其为高热度书籍，并适当提高回收价格或扩大回收准入范围，鼓励学生投放同类书籍。对于库存高、售出慢、浏览少的书籍，系统可判定其流通性较弱，降低回收价格、限制回收数量，必要时暂停回收。通过这种动态调控，系统能够使库存结构更加贴合校园实际需求。",
            "该模块还具有明显的时间周期价值。高校教材需求往往与学期节奏密切相关，新学期开学前后教材需求集中，期末和考研阶段复习资料需求上升，毕业季则会出现大量教材和参考书回收。系统通过长期数据积累，可以识别这些周期性变化，并提前调整回收策略。例如，在开学前提高公共课教材和专业基础课教材回收权重，在考试季提高教辅资料和考研书籍的准入等级，在毕业季对大量重复教材设置库存上限。由此，大数据分析不只是事后统计工具，而是可以参与设备运营决策的调控系统。",
        ],
    ),
    (
        "3.5 智能算法定价与库存管理系统设计",
        [
            "合理定价是二手图书回收售卖系统能否持续运行的核心。回收价格过高会压缩运营空间，增加库存风险；回收价格过低则会降低学生参与意愿，使设备无法获得稳定书源。因此，本项目采用综合定价思路，将书籍基础信息、二手市场参考价、品相等级、库存状态和热度数据结合起来，形成相对动态的智能定价机制。在该机制中，图书原价主要作为基础参考信息，而实际回收价格更应以二手市场参考价为基础。原因在于原价反映的是新书定价，并不能代表当前二手流通价值，尤其对于旧版教材、内容更新较快的考试资料或市场供给过多的书籍，若直接依据原价计算回收价格，容易明显高估其可售价值。",
            "系统可将回收价格设定为二手市场参考价、基础回收率、品相系数、热度修正系数和库存修正系数的综合结果。其中，二手市场参考价表示该书在二手交易场景中的大致可售价格，是定价的基础；基础回收率表示平台愿意按二手市场价的一定比例进行回收，用于覆盖设备运营、人工复核、库存占用和交易风险；品相系数反映书籍实际保存状态，近全新书籍系数较高，破损书籍系数较低；热度修正系数用于鼓励回收需求量高的书籍；库存修正系数则用于抑制库存过量书籍继续进入系统。通过这些因子的组合，系统可以在学生可接受价格和平台可持续运营之间取得相对平衡。",
            "从算法表达上，系统可采用“回收价格=二手市场参考价×基础回收率×品相系数×热度修正系数×库存修正系数”的思路。该公式并不意味着系统只能采用固定线性模型，而是提供了清晰的定价逻辑框架。随着项目运行数据增加，平台可以进一步优化各类系数，例如对高频成交教材设置更高的基础回收率，对长期滞销书籍降低库存修正系数，对品相较差但仍有较高需求的教材保留一定回收空间。对于售卖价格，系统则可在回收价格基础上结合运营成本、目标利润、市场接受度和库存周转要求进行设定，使售卖价格低于新书购买成本，同时保证设备运行具有基本经济合理性。",
            "库存管理系统与定价系统相互关联。每本书入库后都应形成独立库存记录，包括 ISBN、书名、作者、出版社、分类、品相等级、回收价格、售卖价格、入库时间、当前状态和售出时间等信息。库存状态可细分为待复核、可售卖、已售出、下架、报废等类型，便于后台管理人员进行查询和维护。系统还应设置库存预警机制，当某类热门书籍库存不足时，提醒提高回收力度；当某类书籍库存过高且长期未售出时，提示降价、促销或停止回收。通过定价算法和库存管理的协同，项目能够减少盲目回收造成的资金占用和空间浪费，提高二手书流通效率。",
        ],
    ),
    (
        "3.6 系统整体运行流程与技术落地优势",
        [
            "从完整业务流程来看，本项目系统可以划分为图书回收、信息识别、品相质检、价格评估、用户确认、入库管理、自助售卖和数据反馈等环节。学生首先将待回收图书放入设备指定识别区域，系统通过摄像头采集图像，并尝试识别 ISBN 条码或封面文字。在书籍身份确认后，系统调用品相质检模块判断书籍外观状态，并结合数据库中的二手市场参考价、基础回收率和动态修正规则计算建议回收价格。学生确认价格后，系统生成回收记录，书籍进入库存；若学生不接受价格或系统判断书籍不符合回收条件，则流程终止并退回书籍。",
            "在图书进入库存之后，系统会根据复核结果将其转为可售卖状态，并在设备端展示给有购书需求的学生。购买者可以在设备界面中按照分类、课程、价格、品相等级等条件浏览库存图书，查看书籍详细信息并完成支付购买。书籍售出后，系统自动更新库存状态和销售记录，同时将成交数据反馈给热度分析模块。随着回收和销售数据持续积累，系统能够不断优化书籍准入规则、回收价格和库存策略，使设备运营从静态规则逐渐转向数据驱动。",
            "本项目的技术落地优势首先体现在改造成本可控。由于方案强调软件系统重构，设备可以尽量复用现有自助终端硬件，不需要进行大规模结构改造。这种方式降低了试点成本和实施门槛，也便于在高校图书馆、教学楼、宿舍区或校园服务中心等场景逐步推广。其次，项目具有较强的校园场景适配性。高校学生群体具有稳定的教材更替周期和二手书交易需求，且同一校园内课程设置相对集中，热门书籍类型较为明确，系统更容易通过数据积累形成有效的回收和售卖规则。",
            "项目的另一项优势在于将人工经验转化为可计算、可复用的系统规则。传统二手书回收依赖人工判断，难以保证标准统一，而本项目通过 ISBN 识别、OCR 识别、AI 品相检测和人工复核相结合的方式，建立相对标准化的处理流程。智能定价模块使价格形成过程更加透明，库存管理模块使运营方能够及时掌握库存结构，大数据分析模块则使回收规则能够根据真实需求动态调整。这些技术模块共同构成了可落地、可扩展的系统体系。",
            "从社会价值角度看，二手图书自助回收售卖一体机有助于促进校园旧书循环利用，降低学生购书成本，减少纸质资源浪费，符合绿色低碳和可持续发展的理念。它不仅解决了学生闲置书籍处理不便的问题，也为有购书需求的学生提供了低价、便捷、可信的购书渠道。随着系统规模扩大，项目还可以进一步接入线上预约、移动端查询、跨设备库存共享和校园数据看板等功能，形成更完整的校园二手书循环服务平台。",
        ],
    ),
]


def p(text, style="BodyText", keep_next=False):
    jc = "both" if style == "BodyText" else "left"
    keep = "<w:keepNext/>" if keep_next else ""
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{keep}<w:jc w:val="{jc}"/></w:pPr>'
        f"<w:r><w:t>{escape(text)}</w:t></w:r></w:p>"
    )


def document_xml():
    body = []
    body.append(p(TITLE, "DocTitle", True))
    body.append(p(SUBTITLE, "Subtitle", True))
    body.append(
        p(
            "本章围绕二手图书自助回收售卖一体机的软件系统建设展开，重点论述设备功能重构、图像识别质检、数据分析、智能定价和库存管理等技术模块之间的协同关系。",
            "Lead",
        )
    )
    for heading, paragraphs in SECTIONS:
        body.append(p(heading, "Heading1", True))
        for para in paragraphs:
            body.append(p(para, "BodyText"))
    sect = """
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
      <w:cols w:space="720"/>
      <w:docGrid w:linePitch="312"/>
    </w:sectPr>
    """
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {''.join(body)}
    {sect}
  </w:body>
</w:document>
"""


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:rPrDefault>
    <w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="320" w:lineRule="auto"/></w:pPr></w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:after="160" w:line="320" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/><w:sz w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="DocTitle">
    <w:name w:val="Document Title"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="0" w:after="120"/><w:keepNext/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="黑体"/><w:b/><w:sz w:val="36"/><w:color w:val="0B2545"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Subtitle">
    <w:name w:val="Subtitle"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="0" w:after="240"/><w:keepNext/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/><w:sz w:val="24"/><w:color w:val="555555"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Lead">
    <w:name w:val="Lead"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="0" w:after="220" w:line="320" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/><w:sz w:val="23"/><w:color w:val="333333"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:next w:val="BodyText"/>
    <w:qFormat/>
    <w:pPr><w:keepNext/><w:spacing w:before="360" w:after="200"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="黑体"/><w:b/><w:sz w:val="32"/><w:color w:val="2E74B5"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="BodyText">
    <w:name w:val="Body Text"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:pPr><w:spacing w:before="0" w:after="160" w:line="320" w:lineRule="auto"/><w:jc w:val="both"/><w:firstLine w:val="440"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/><w:sz w:val="22"/><w:color w:val="000000"/></w:rPr>
  </w:style>
</w:styles>
"""


CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>第三章 项目产品与技术体系</dc:title>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-06-02T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-06-02T00:00:00Z</dcterms:modified>
</cp:coreProperties>
"""


APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
</Properties>
"""


def main():
    with ZipFile(OUT, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", document_xml())
        z.writestr("word/styles.xml", STYLES)
        z.writestr("docProps/core.xml", CORE)
        z.writestr("docProps/app.xml", APP)
    print(OUT.resolve())


if __name__ == "__main__":
    main()
