# -*- coding: utf-8 -*-
"""自然拼读（Phonics）内容库：字母音 / 元音 / 辅音组合 / 词族。

每个音素条目包含：
    g      拼写形式（grapheme），如 "sh"
    ipa    音标提示，如 "/sh/"
    note   发音要点（中文）
    words  [(英文, 音素拆分, 中文), ...]  拆分用 | 分隔，拼接后必须等于原文

音素拆分用于在打字板上按"音块"着色，建立"音 — 形"对应关系。
"""

GROUPS = [
    # ------------------------------------------------------------ 字母音
    {
        "key": "alphabet",
        "title": "字母音 A-Z",
        "level": "初级",
        "desc": "26 个字母最常发的音（Letter Sounds），拼读的地基。",
        "entries": [
            {"g": "a", "ipa": "/ae/", "note": "短音，嘴张大，舌尖抵下齿",
             "words": [("apple", "a|p|ple", "苹果"), ("ant", "a|n|t", "蚂蚁")]},
            {"g": "b", "ipa": "/b/", "note": "双唇紧闭后爆开，声带振动",
             "words": [("ball", "b|a|ll", "球"), ("bed", "b|e|d", "床")]},
            {"g": "c", "ipa": "/k/", "note": "舌根抵软腭，送气清音",
             "words": [("cat", "c|a|t", "猫"), ("cup", "c|u|p", "杯子")]},
            {"g": "d", "ipa": "/d/", "note": "舌尖抵上齿龈后弹开",
             "words": [("dog", "d|o|g", "狗"), ("desk", "d|e|sk", "书桌")]},
            {"g": "e", "ipa": "/e/", "note": "嘴微张，短促有力",
             "words": [("egg", "e|gg", "鸡蛋"), ("end", "e|n|d", "结束")]},
            {"g": "f", "ipa": "/f/", "note": "上齿轻咬下唇，送气",
             "words": [("fish", "f|i|sh", "鱼"), ("fan", "f|a|n", "风扇")]},
            {"g": "g", "ipa": "/g/", "note": "舌根抵软腭，声带振动",
             "words": [("goat", "g|oa|t", "山羊"), ("girl", "g|ir|l", "女孩")]},
            {"g": "h", "ipa": "/h/", "note": "喉部送气，如哈气",
             "words": [("hat", "h|a|t", "帽子"), ("hand", "h|a|nd", "手")]},
            {"g": "i", "ipa": "/i/", "note": "短音，嘴唇微展",
             "words": [("ink", "i|nk", "墨水"), ("igloo", "i|g|loo", "冰屋")]},
            {"g": "j", "ipa": "/j/", "note": "舌面抵上颚，声带振动",
             "words": [("jump", "j|u|mp", "跳"), ("jam", "j|a|m", "果酱")]},
            {"g": "k", "ipa": "/k/", "note": "与 c 同音，送气更足",
             "words": [("kite", "k|i|te", "风筝"), ("key", "k|ey", "钥匙")]},
            {"g": "l", "ipa": "/l/", "note": "舌尖抵上齿龈，气流从两侧出",
             "words": [("leg", "l|e|g", "腿"), ("lion", "l|i|on", "狮子")]},
            {"g": "m", "ipa": "/m/", "note": "双唇闭合，鼻音",
             "words": [("moon", "m|oo|n", "月亮"), ("map", "m|a|p", "地图")]},
            {"g": "n", "ipa": "/n/", "note": "舌尖抵上齿龈，鼻音",
             "words": [("nose", "n|o|se", "鼻子"), ("net", "n|e|t", "网")]},
            {"g": "o", "ipa": "/o/", "note": "嘴圆张，短音",
             "words": [("ox", "o|x", "公牛"), ("on", "o|n", "在…上")]},
            {"g": "p", "ipa": "/p/", "note": "双唇闭合后爆开，送气",
             "words": [("pen", "p|e|n", "钢笔"), ("pig", "p|i|g", "猪")]},
            {"g": "qu", "ipa": "/kw/", "note": "q 后面总跟着 u，合读 /kw/",
             "words": [("queen", "qu|een", "女王"), ("quick", "qu|ick", "快的")]},
            {"g": "r", "ipa": "/r/", "note": "舌尖卷起不碰上颚",
             "words": [("rain", "r|ai|n", "雨"), ("red", "r|e|d", "红色")]},
            {"g": "s", "ipa": "/s/", "note": "舌尖近齿龈，气流细长",
             "words": [("sun", "s|u|n", "太阳"), ("sit", "s|i|t", "坐")]},
            {"g": "t", "ipa": "/t/", "note": "舌尖抵齿龈后弹开，送气",
             "words": [("tiger", "t|i|ger", "老虎"), ("ten", "t|e|n", "十")]},
            {"g": "u", "ipa": "/u/", "note": "嘴自然张开，短促",
             "words": [("umbrella", "u|m|bre|lla", "雨伞"), ("up", "u|p", "向上")]},
            {"g": "v", "ipa": "/v/", "note": "上齿咬下唇，声带振动",
             "words": [("van", "v|a|n", "货车"), ("vest", "v|e|st", "背心")]},
            {"g": "w", "ipa": "/w/", "note": "双唇收圆后快速放开",
             "words": [("water", "w|a|ter", "水"), ("window", "w|i|ndow", "窗户")]},
            {"g": "x", "ipa": "/ks/", "note": "结尾常发 /ks/",
             "words": [("box", "b|o|x", "盒子"), ("fox", "f|o|x", "狐狸")]},
            {"g": "y", "ipa": "/y/", "note": "词首发 /y/，如 yes",
             "words": [("yellow", "y|e|llow", "黄色"), ("yes", "y|e|s", "是的")]},
            {"g": "z", "ipa": "/z/", "note": "同 s 的口型，声带振动",
             "words": [("zoo", "z|oo", "动物园"), ("zip", "z|i|p", "拉链")]},
        ],
    },
    # ------------------------------------------------------------ 短元音
    {
        "key": "short_vowel",
        "title": "短元音 a e i o u",
        "level": "初级",
        "desc": "CVC 结构（辅音-元音-辅音）中的短元音，最基础的解码能力。",
        "entries": [
            {"g": "a", "ipa": "/ae/", "note": "cat / map / hat 中的 a",
             "words": [("cat", "c|a|t", "猫"), ("map", "m|a|p", "地图"), ("hat", "h|a|t", "帽子")]},
            {"g": "e", "ipa": "/e/", "note": "bed / pen / ten 中的 e",
             "words": [("bed", "b|e|d", "床"), ("pen", "p|e|n", "钢笔"), ("net", "n|e|t", "网")]},
            {"g": "i", "ipa": "/i/", "note": "pig / big / sit 中的 i",
             "words": [("pig", "p|i|g", "猪"), ("big", "b|i|g", "大的"), ("sit", "s|i|t", "坐")]},
            {"g": "o", "ipa": "/o/", "note": "dog / hot / box 中的 o",
             "words": [("dog", "d|o|g", "狗"), ("hot", "h|o|t", "热的"), ("box", "b|o|x", "盒子")]},
            {"g": "u", "ipa": "/u/", "note": "cup / bus / sun 中的 u",
             "words": [("cup", "c|u|p", "杯子"), ("bus", "b|u|s", "公交车"), ("sun", "s|u|n", "太阳")]},
        ],
    },
    # ------------------------------------------------------------ 长元音 magic e
    {
        "key": "magic_e",
        "title": "Magic e 长元音",
        "level": "初级",
        "desc": "结尾的 e 不发音，却让前面的元音『读自己的名字』。",
        "entries": [
            {"g": "a_e", "ipa": "/ay/", "note": "cap → cap e，a 读字母音",
             "words": [("cake", "c|a|ke", "蛋糕"), ("name", "n|a|me", "名字"), ("game", "g|a|me", "游戏")]},
            {"g": "i_e", "ipa": "/ai/", "note": "kit → kite，i 读字母音",
             "words": [("bike", "b|i|ke", "自行车"), ("kite", "k|i|te", "风筝"), ("time", "t|i|me", "时间")]},
            {"g": "o_e", "ipa": "/oh/", "note": "not → note，o 读字母音",
             "words": [("nose", "n|o|se", "鼻子"), ("home", "h|o|me", "家"), ("rose", "r|o|se", "玫瑰")]},
            {"g": "u_e", "ipa": "/yoo/", "note": "cut → cute，u 读字母音",
             "words": [("cute", "c|u|te", "可爱的"), ("use", "u|se", "使用"), ("June", "J|u|ne", "六月")]},
            {"g": "e_e", "ipa": "/ee/", "note": "较少见，如 these / eve",
             "words": [("these", "th|e|se", "这些"), ("eve", "e|ve", "前夕")]},
        ],
    },
    # ------------------------------------------------------------ 元音字母组合
    {
        "key": "vowel_team",
        "title": "元音字母组合",
        "level": "初级",
        "desc": "『两个元音一起走，第一个读字母音』（部分例外）。",
        "entries": [
            {"g": "ai", "ipa": "/ay/", "note": "多在词中：rain / train",
             "words": [("rain", "r|ai|n", "雨"), ("train", "tr|ai|n", "火车"), ("tail", "t|ai|l", "尾巴")]},
            {"g": "ay", "ipa": "/ay/", "note": "多在词尾：day / play",
             "words": [("day", "d|ay", "天"), ("play", "pl|ay", "玩"), ("say", "s|ay", "说")]},
            {"g": "ea", "ipa": "/ee/", "note": "长音：eat / sea；也读 /e/ 如 bread",
             "words": [("eat", "ea|t", "吃"), ("sea", "s|ea", "海"), ("read", "r|ead", "读")]},
            {"g": "ee", "ipa": "/ee/", "note": "两个 e 一起读长音：see / tree",
             "words": [("see", "s|ee", "看见"), ("tree", "tr|ee", "树"), ("feet", "f|ee|t", "脚")]},
            {"g": "oa", "ipa": "/oh/", "note": "boat / coat 中的 oa",
             "words": [("boat", "b|oa|t", "船"), ("coat", "c|oa|t", "外套"), ("goat", "g|oa|t", "山羊")]},
            {"g": "oo", "ipa": "/oo/", "note": "长音：food / moon；短音 /u/：book / look",
             "words": [("food", "f|oo|d", "食物"), ("moon", "m|oo|n", "月亮"), ("book", "b|oo|k", "书")]},
            {"g": "ie", "ipa": "/ai/", "note": "词尾常读字母音 i：pie / tie",
             "words": [("pie", "p|ie", "派"), ("tie", "t|ie", "领带"), ("lie", "l|ie", "躺；说谎")]},
            {"g": "ew", "ipa": "/yoo/", "note": "new / few 中的 ew",
             "words": [("new", "n|ew", "新的"), ("few", "f|ew", "少数"), ("blue", "bl|ue", "蓝色")]},
        ],
    },
    # ------------------------------------------------------------ R 控元音
    {
        "key": "r_vowel",
        "title": "R 控元音 ar er ir or ur",
        "level": "中级",
        "desc": "元音后跟 r 时，发音被 r 控制，要连着一起记。",
        "entries": [
            {"g": "ar", "ipa": "/ah/", "note": "嘴张大，car / star",
             "words": [("car", "c|ar", "汽车"), ("star", "st|ar", "星星"), ("park", "p|ar|k", "公园")]},
            {"g": "er", "ipa": "/er/", "note": "卷舌长音，her / person",
             "words": [("her", "h|er", "她的"), ("person", "p|er|son", "人"), ("winter", "w|in|ter", "冬天")]},
            {"g": "ir", "ipa": "/er/", "note": "与 er 同音，bird / girl",
             "words": [("bird", "b|ird", "鸟"), ("girl", "g|ir|l", "女孩"), ("shirt", "sh|ir|t", "衬衫")]},
            {"g": "or", "ipa": "/aw/", "note": "嘴收圆，for / fork",
             "words": [("for", "f|or", "为了"), ("fork", "f|or|k", "叉子"), ("horse", "h|or|se", "马")]},
            {"g": "ur", "ipa": "/er/", "note": "与 er / ir 同音，nurse / turn",
             "words": [("nurse", "n|ur|se", "护士"), ("turn", "t|urn", "转弯"), ("purple", "p|ur|ple", "紫色")]},
        ],
    },
    # ------------------------------------------------------------ 双元音
    {
        "key": "diphthong",
        "title": "双元音与特殊组合",
        "level": "中级",
        "desc": "两个元音滑读，从一个音滑到另一个音。",
        "entries": [
            {"g": "oi", "ipa": "/oy/", "note": "多在词中：oil / coin",
             "words": [("oil", "oi|l", "油"), ("coin", "c|oi|n", "硬币"), ("boil", "b|oi|l", "煮沸")]},
            {"g": "oy", "ipa": "/oy/", "note": "多在词尾：boy / toy",
             "words": [("boy", "b|oy", "男孩"), ("toy", "t|oy", "玩具"), ("joy", "j|oy", "快乐")]},
            {"g": "ou", "ipa": "/ow/", "note": "house / mouse 中的 ou",
             "words": [("house", "h|ou|se", "房子"), ("mouse", "m|ou|se", "老鼠"), ("out", "ou|t", "出去")]},
            {"g": "ow", "ipa": "/ow/", "note": " cow / down；也可读 /oh/ 如 snow",
             "words": [("cow", "c|ow", "奶牛"), ("down", "d|own", "向下"), ("snow", "sn|ow", "雪")]},
            {"g": "au", "ipa": "/aw/", "note": "autumn / because 中的 au",
             "words": [("autumn", "au|tumn", "秋天"), ("sauce", "s|au|ce", "酱汁")]},
            {"g": "aw", "ipa": "/aw/", "note": "词尾常见：saw / draw",
             "words": [("saw", "s|aw", "看见（过去式）"), ("draw", "dr|aw", "画"), ("law", "l|aw", "法律")]},
            {"g": "igh", "ipa": "/ai/", "note": "gh 不发音：light / night",
             "words": [("light", "l|igh|t", "光"), ("night", "n|igh|t", "夜晚"), ("high", "h|igh", "高的")]},
            {"g": "ind", "ipa": "/aind/", "note": "find / kind 中的 ind",
             "words": [("find", "f|ind", "找到"), ("kind", "k|ind", "善良的"), ("mind", "m|ind", "介意")]},
        ],
    },
    # ------------------------------------------------------------ 辅音二合字母
    {
        "key": "digraph",
        "title": "辅音二合字母",
        "level": "初级",
        "desc": "两个字母合起来发一个新音，不能拆开读。",
        "entries": [
            {"g": "sh", "ipa": "/sh/", "note": "嘘声，ship / fish",
             "words": [("ship", "sh|i|p", "船"), ("fish", "f|i|sh", "鱼"), ("shop", "sh|o|p", "商店")]},
            {"g": "ch", "ipa": "/ch/", "note": "类似『吃』的音，chair / lunch",
             "words": [("chair", "ch|air", "椅子"), ("chip", "ch|i|p", "薯片"), ("lunch", "l|u|nch", "午餐")]},
            {"g": "th (清)", "ipa": "/th/", "note": "舌尖轻放齿间送气：think / three",
             "words": [("think", "th|i|nk", "思考"), ("three", "th|r|ee", "三"), ("math", "m|a|th", "数学")]},
            {"g": "th (浊)", "ipa": "/th/", "note": "同口型但声带振动：this / that",
             "words": [("this", "th|i|s", "这个"), ("that", "th|a|t", "那个"), ("mother", "m|o|th|er", "妈妈")]},
            {"g": "wh", "ipa": "/w/", "note": "多数读 /w/：what / when；o 前读 /h/：who",
             "words": [("what", "wh|a|t", "什么"), ("when", "wh|e|n", "什么时候"), ("white", "wh|i|te", "白色")]},
            {"g": "ph", "ipa": "/f/", "note": "ph 读 f，多来自希腊语",
             "words": [("phone", "ph|o|ne", "电话"), ("photo", "ph|o|to", "照片"), ("graph", "gr|a|ph", "图表")]},
            {"g": "ck", "ipa": "/k/", "note": "短元音后常用 ck 表示 /k/",
             "words": [("back", "b|a|ck", "后面"), ("duck", "d|u|ck", "鸭子"), ("clock", "cl|o|ck", "时钟")]},
            {"g": "ng", "ipa": "/ng/", "note": "后鼻音，sing / king",
             "words": [("sing", "s|i|ng", "唱歌"), ("king", "k|i|ng", "国王"), ("long", "l|o|ng", "长的")]},
            {"g": "nk", "ipa": "/ngk/", "note": "ng + k，thank / drink",
             "words": [("thank", "th|a|nk", "感谢"), ("drink", "dr|i|nk", "喝"), ("bank", "b|a|nk", "银行")]},
        ],
    },
    # ------------------------------------------------------------ 辅音连缀
    {
        "key": "blend",
        "title": "辅音连缀（L / R / S 系列）",
        "level": "中级",
        "desc": "两个辅音各自发音但快速连读，中间不加元音。",
        "entries": [
            {"g": "bl", "ipa": "/bl/", "note": "blue / black",
             "words": [("blue", "bl|ue", "蓝色"), ("black", "bl|a|ck", "黑色")]},
            {"g": "cl", "ipa": "/kl/", "note": "clean / clock",
             "words": [("clean", "cl|ean", "干净的"), ("clock", "cl|o|ck", "时钟")]},
            {"g": "fl", "ipa": "/fl/", "note": "fly / flag",
             "words": [("fly", "fl|y", "飞"), ("flag", "fl|a|g", "旗帜")]},
            {"g": "gl", "ipa": "/gl/", "note": "glass / glue",
             "words": [("glass", "gl|a|ss", "玻璃杯"), ("glue", "gl|ue", "胶水")]},
            {"g": "pl", "ipa": "/pl/", "note": "play / plant",
             "words": [("play", "pl|ay", "玩"), ("plant", "pl|a|nt", "植物")]},
            {"g": "sl", "ipa": "/sl/", "note": "sleep / slow",
             "words": [("sleep", "sl|ee|p", "睡觉"), ("slow", "sl|ow", "慢的")]},
            {"g": "br", "ipa": "/br/", "note": "bread / brown",
             "words": [("bread", "br|ead", "面包"), ("brown", "br|own", "棕色")]},
            {"g": "cr", "ipa": "/kr/", "note": "cry / cross",
             "words": [("cry", "cr|y", "哭"), ("cross", "cr|o|ss", "穿过")]},
            {"g": "dr", "ipa": "/dr/", "note": "dress / drink",
             "words": [("dress", "dr|e|ss", "连衣裙"), ("drink", "dr|i|nk", "喝")]},
            {"g": "fr", "ipa": "/fr/", "note": "frog / from",
             "words": [("frog", "fr|o|g", "青蛙"), ("from", "fr|o|m", "来自")]},
            {"g": "gr", "ipa": "/gr/", "note": "green / great",
             "words": [("green", "gr|ee|n", "绿色"), ("great", "gr|eat", "很棒的")]},
            {"g": "pr", "ipa": "/pr/", "note": "price / prince",
             "words": [("price", "pr|i|ce", "价格"), ("prince", "pr|i|nce", "王子")]},
            {"g": "tr", "ipa": "/tr/", "note": "tree / train",
             "words": [("tree", "tr|ee", "树"), ("train", "tr|ai|n", "火车")]},
            {"g": "sk / sc", "ipa": "/sk/", "note": "sky / scarf",
             "words": [("sky", "sk|y", "天空"), ("scarf", "sc|ar|f", "围巾")]},
            {"g": "sm / sn", "ipa": "/sm/ /sn/", "note": "small / snow",
             "words": [("small", "sm|a|ll", "小的"), ("snow", "sn|ow", "雪")]},
            {"g": "sp / st", "ipa": "/sp/ /st/", "note": "spell / stop",
             "words": [("spell", "sp|e|ll", "拼写"), ("stop", "st|o|p", "停止")]},
            {"g": "sw", "ipa": "/sw/", "note": "swim / sweet",
             "words": [("swim", "sw|i|m", "游泳"), ("sweet", "sw|ee|t", "甜的")]},
            {"g": "tw", "ipa": "/tw/", "note": "twelve / twin",
             "words": [("twelve", "tw|e|lve", "十二"), ("twin", "tw|i|n", "双胞胎")]},
        ],
    },
]

# ---------------------------------------------------------------- 词族短句
FAMILY_SENTENCES = [
    {"g": "-at", "ipa": "/at/", "note": "cat / sat / mat / hat 同韵",
     "en": "The cat sat on the mat.",
     "zh": "猫坐在垫子上。",
     "phonics": "The |c|at |s|at |on |the |m|at."},
    {"g": "-en", "ipa": "/en/", "note": "ten / pen / men 同韵",
     "en": "Ten men have red pens.",
     "zh": "十个男人有红色的钢笔。",
     "phonics": "T|en |m|en |have |r|e|d |p|en|s."},
    {"g": "-ig", "ipa": "/ig/", "note": "big / pig / dig 同韵",
     "en": "The big pig can dig.",
     "zh": "这只大猪会挖土。",
     "phonics": "The |b|i|g |p|i|g |can |d|i|g."},
    {"g": "-op", "ipa": "/op/", "note": "hop / mop / stop 同韵",
     "en": "The dog can hop and stop.",
     "zh": "这只狗会跳，也会停。",
     "phonics": "The |d|o|g |can |h|o|p |and |st|o|p."},
    {"g": "-un", "ipa": "/un/", "note": "run / sun / fun 同韵",
     "en": "We run in the sun for fun.",
     "zh": "我们在阳光下跑着玩。",
     "phonics": "We |r|u|n |in |the |s|u|n |for |f|u|n."},
    {"g": "-ake", "ipa": "/ayk/", "note": "cake / make / lake 同韵",
     "en": "I can make a cake by the lake.",
     "zh": "我能在湖边做一个蛋糕。",
     "phonics": "I |can |m|a|ke |a |c|a|ke |by |the |l|a|ke."},
    {"g": "-ight", "ipa": "/ait/", "note": "light / night / bright 同韵",
     "en": "The light is bright at night.",
     "zh": "夜晚的灯光很明亮。",
     "phonics": "The |l|igh|t |is |br|igh|t |at |n|igh|t."},
    {"g": "-ink", "ipa": "/ingk/", "note": "think / drink / pink 同韵",
     "en": "I think I will drink the pink juice.",
     "zh": "我想我会喝那瓶粉色果汁。",
     "phonics": "I |th|i|nk |I |will |dr|i|nk |the |p|i|nk |j|ui|ce."},
]


def _check(en, phonics):
    """拆分拼接必须等于原文，否则放弃着色（降级为普通打字）。"""
    if not phonics:
        return ""
    return phonics if "".join(phonics.split("|")) == en else ""


def build_courses():
    """返回 [(key, title, level, desc, [(en, zh, note, phonics)]), ...]。"""
    out = []
    for group in GROUPS:
        key = "ph_" + group["key"]
        title = "自然拼读 · " + group["title"]
        items = []
        for e in group["entries"]:
            note = "%s %s｜%s" % (e["g"], e["ipa"], e["note"])
            for word, split, zh in e["words"]:
                items.append((word, zh, note, _check(word, split)))
        out.append((key, title, group["level"], group["desc"], items))

    items = []
    for f in FAMILY_SENTENCES:
        note = "%s %s｜%s" % (f["g"], f["ipa"], f["note"])
        items.append((f["en"], f["zh"], note, _check(f["en"], f["phonics"])))
    out.append(("ph_family", "自然拼读 · 词族短句（-at / -ight / -ake…）", "初级",
                "同韵词族短句，一口气练会一组押韵词。", items))
    return out


def seed():
    """把自然拼读课程写入数据库（已存在则跳过）。"""
    from . import db

    conn = db.connect()
    exist = {r["builtin_key"] for r in conn.execute("SELECT builtin_key FROM courses").fetchall()}
    conn.close()
    for key, title, level, desc, items in build_courses():
        if key in exist:
            continue
        cid = db.add_course(title, desc, level, "builtin", key)
        db.add_sentences(cid, items)
