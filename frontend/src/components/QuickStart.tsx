interface Props {
  onSelect: (task: string) => void;
}

const EXAMPLES = [
  {
    icon: "📚",
    title: "图书价格对比",
    desc: "打开 books.toscrape.com，进入 Mystery 分类，列出首页所有书的名称和价格",
  },
  {
    icon: "🌐",
    title: "百度百科查询",
    desc: "打开百度百科，搜索'人工智能'，看看这个词条的中文名、外文名、提出时间分别是什么，然后找到页面里'机器学习'的链接点进去，看看那页介绍的是什么",
  },
  {
    icon: "📖",
    title: "豆瓣图书查询",
    desc: "打开豆瓣，搜索'三体'，找到第一本《三体》，把评分、评分人数、作者列出来，再看前3条热门短评说了什么",
  },
  {
    icon: "📰",
    title: "IT之家新闻浏览",
    desc: "打开IT之家，看看首页有哪些新闻，点进置顶的第一篇文章，把标题、发布时间、评论数列出来，再看看热评第一条说了什么",
  },
  {
    icon: "⭐",
    title: "GitHub 趋势",
    desc: "打开 GitHub Trending，列出前5个最热项目名称和 Star 数",
  },
  {
    icon: "📺",
    title: "B站视频搜索",
    desc: "打开b站，在首页搜索框输入'Agent开发'，从搜索结果里找到播放量最高的视频点进去，把视频标题、播放量、UP主名字和发布时间列出来",
  },
  {
    icon: "🔍",
    title: "百度搜索",
    desc: "在百度搜索「今天天气」，提取搜索结果第一条的内容",
  },
  {
    icon: "🎮",
    title: "TapTap 游戏查询",
    desc: "打开TapTap，搜索'原神'，找到评分、下载量、游戏类型，然后看看最热门的3条玩家评价",
  },
  {
    icon: "💻",
    title: "CSDN技术文章",
    desc: "打开CSDN，搜索'Python爬虫'，找到阅读量最高的那篇点进去，把文章标题、作者、阅读量、点赞数列出来",
  },
  {
    icon: "🕹️",
    title: "3DM游戏新闻",
    desc: "打开3dmgame.com，看看首页有什么游戏新闻，点进第一条，列出标题和发布时间",
  },
  {
    icon: "🎯",
    title: "游侠网游戏新闻",
    desc: "打开游侠网ali213.net，看首页第一条新闻的标题和发布时间",
  },
  {
    icon: "💬",
    title: "知乎热榜",
    desc: "打开知乎，看看热榜第一是什么问题，有多少人关注和浏览，高赞回答说了什么",
  },
];

export default function QuickStart({ onSelect }: Props) {
  return (
    <div className="quick-start">
      {EXAMPLES.map((ex) => (
        <div
          key={ex.title}
          className="quick-card"
          onClick={() => onSelect(ex.desc)}
        >
          <div className="quick-card-icon">{ex.icon}</div>
          <div className="quick-card-title">{ex.title}</div>
          <div className="quick-card-desc">{ex.desc}</div>
        </div>
      ))}
    </div>
  );
}
