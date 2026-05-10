import { useState, useMemo } from 'react';
import { prompts, CATEGORIES, SEVERITY_LABELS, type Prompt } from './data/prompts';

// ─── Icons ────────────────────────────────────────────────
const IconCopy = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
  </svg>
);
const IconCheck = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);
const IconChevron = ({ open }: { open: boolean }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
    style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
    <polyline points="6 9 12 15 18 9"/>
  </svg>
);
const IconFilter = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
  </svg>
);
const IconSearch = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
);
const IconExternalLink = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
    <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
  </svg>
);

// ─── CopyButton ───────────────────────────────────────────
function CopyButton({ text, label = '复制提示词' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const handle = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button
      onClick={handle}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200 ${
        copied
          ? 'bg-green-100 text-green-700 border border-green-300'
          : 'bg-indigo-600 text-white hover:bg-indigo-700 active:scale-95'
      }`}
    >
      {copied ? <IconCheck /> : <IconCopy />}
      {copied ? '已复制！' : label}
    </button>
  );
}

// ─── PromptCard ───────────────────────────────────────────
function PromptCard({ p }: { p: Prompt }) {
  const [open, setOpen] = useState(false);
  const sev = SEVERITY_LABELS[p.severity];
  const cat = CATEGORIES[p.category];

  const catColors: Record<string, string> = {
    purple: 'bg-purple-100 text-purple-700',
    red: 'bg-red-100 text-red-700',
    orange: 'bg-orange-100 text-orange-700',
    blue: 'bg-blue-100 text-blue-700',
    green: 'bg-green-100 text-green-700',
    gray: 'bg-gray-100 text-gray-700',
  };

  return (
    <div className={`rounded-xl border-2 bg-white transition-all duration-200 ${open ? 'border-indigo-300 shadow-lg' : 'border-gray-200 hover:border-indigo-200 hover:shadow-md'}`}>
      {/* Header */}
      <button
        className="w-full text-left p-5 flex items-start gap-4"
        onClick={() => setOpen(!open)}
      >
        {/* Step badge */}
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-indigo-600 text-white font-bold text-sm flex items-center justify-center shadow">
          {p.step}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1.5">
            <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full border ${sev.bg} ${sev.text} ${sev.border}`}>
              {sev.label}
            </span>
            <span className={`text-xs font-semibold px-2.5 py-0.5 rounded-full ${catColors[cat.color] || 'bg-gray-100 text-gray-700'}`}>
              {cat.label}
            </span>
          </div>
          <h3 className="font-bold text-gray-900 text-base leading-snug">{p.title}</h3>
          <p className="text-sm text-gray-500 mt-1 leading-relaxed line-clamp-2">{p.problem}</p>
        </div>

        <div className="flex-shrink-0 text-gray-400 mt-1">
          <IconChevron open={open} />
        </div>
      </button>

      {/* Expanded */}
      {open && (
        <div className="border-t border-gray-100 px-5 pb-5 pt-4 space-y-4">

          {/* 问题 & 根因 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="rounded-lg bg-red-50 border border-red-200 p-4">
              <div className="text-xs font-bold text-red-600 uppercase tracking-wide mb-1.5">⚠️ 问题现象</div>
              <p className="text-sm text-red-900 leading-relaxed">{p.problem}</p>
            </div>
            <div className="rounded-lg bg-orange-50 border border-orange-200 p-4">
              <div className="text-xs font-bold text-orange-600 uppercase tracking-wide mb-1.5">🔍 根本原因</div>
              <p className="text-sm text-orange-900 leading-relaxed">{p.rootCause}</p>
            </div>
          </div>

          {/* 涉及文件 */}
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-semibold text-gray-500 self-center">涉及文件：</span>
            {p.files.map(f => (
              <span key={f} className="text-xs bg-gray-100 text-gray-700 font-mono px-2 py-1 rounded-md border border-gray-200">
                {f}
              </span>
            ))}
          </div>

          {/* 提示词 */}
          <div className="rounded-lg bg-gray-950 border border-gray-700 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-800 border-b border-gray-700">
              <span className="text-xs font-bold text-gray-300 tracking-wide">📋 TRAE 提示词（直接粘贴使用）</span>
              <CopyButton text={p.prompt} />
            </div>
            <pre className="text-xs text-gray-200 p-4 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto font-mono">
              {p.prompt}
            </pre>
          </div>

          {/* 验证方法 */}
          <div className="rounded-lg bg-green-50 border border-green-200 p-4">
            <div className="text-xs font-bold text-green-600 uppercase tracking-wide mb-1.5">✅ 验证方法</div>
            <code className="text-sm text-green-900 font-mono">{p.verify}</code>
          </div>

        </div>
      )}
    </div>
  );
}

// ─── Sidebar Progress ─────────────────────────────────────
function SidebarProgress({ done, total }: { done: number; total: number }) {
  const pct = Math.round((done / total) * 100);
  return (
    <div className="bg-white rounded-xl border-2 border-gray-200 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-gray-700">修复进度</span>
        <span className="text-sm font-bold text-indigo-600">{pct}%</span>
      </div>
      <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-500">{done} / {total} 步骤完成</p>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────
export default function App() {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [completedSteps] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    return prompts.filter(p => {
      if (selectedCategory !== 'all' && p.category !== selectedCategory) return false;
      if (selectedSeverity !== 'all' && p.severity !== selectedSeverity) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!p.title.toLowerCase().includes(q) && !p.problem.toLowerCase().includes(q) && !p.rootCause.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [selectedCategory, selectedSeverity, search]);

  const criticalCount = prompts.filter(p => p.severity === 'critical').length;
  const highCount = prompts.filter(p => p.severity === 'high').length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-indigo-50/30 to-purple-50/20">

      {/* ── Top Banner ── */}
      <div className="bg-gradient-to-r from-indigo-700 via-indigo-600 to-purple-700 text-white">
        <div className="max-w-6xl mx-auto px-4 py-8 md:py-12">
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-3xl">🚗</span>
                <span className="text-xs font-bold bg-white/20 border border-white/30 rounded-full px-3 py-1 tracking-wide">
                  weibo-hotsearch · V4.3 修复手册
                </span>
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold leading-tight mb-2">
                汽车舆情监控系统<br/>Trae AI 全套修复提示词
              </h1>
              <p className="text-indigo-200 text-sm leading-relaxed max-w-xl">
                深度分析项目代码后整理的 <strong className="text-white">{prompts.length} 个精准修复步骤</strong>，覆盖爬虫失效、清洗过滤、推送异常、调度崩溃全链路。
                每步提供"问题→根因→提示词→验证"四件套，复制粘贴给 Trae 即可。
              </p>
            </div>
            <div className="flex-shrink-0">
              <a
                href="https://github.com/sulcr1983/weibo-hotsearch"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 bg-white/15 hover:bg-white/25 border border-white/30 text-white text-sm font-semibold px-4 py-2.5 rounded-lg transition-all"
              >
                <IconExternalLink /> 查看项目源码
              </a>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
            {[
              { label: '修复步骤', value: prompts.length, color: 'bg-white/15' },
              { label: '致命问题', value: criticalCount, color: 'bg-red-500/40' },
              { label: '高危问题', value: highCount, color: 'bg-orange-400/40' },
              { label: '覆盖模块', value: Object.keys(CATEGORIES).length, color: 'bg-purple-400/30' },
            ].map(s => (
              <div key={s.label} className={`${s.color} border border-white/20 rounded-xl px-4 py-3 backdrop-blur-sm`}>
                <div className="text-2xl font-extrabold">{s.value}</div>
                <div className="text-xs text-indigo-200 font-medium mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 问题速览 ── */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="bg-amber-50 border-2 border-amber-300 rounded-xl p-5">
          <h2 className="font-bold text-amber-900 text-base mb-3 flex items-center gap-2">
            <span>📋</span> 你的项目核心问题一览（根据代码深度分析）
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { icon: '💥', tag: '致命', text: 'main.py 引用了不存在的 stealth_scraper、ai_scraper 模块，导致启动直接崩溃' },
              { icon: '💥', tag: '致命', text: '微博 API 正则兜底方案有转义 Bug，两个方案都失效时0条入库' },
              { icon: '🔴', tag: '高危', text: '四维度过滤器 + LLM双失败 → 所有新闻在 NO_DIMENSION 被丢弃，日报空数据' },
              { icon: '🔴', tag: '高危', text: 'RSS 源依赖 SharedSession 工具类，该文件可能不存在，采集层整体崩溃' },
              { icon: '🟡', tag: '中等', text: '日报 score>=65 阈值太高，实际入库文章几乎都达不到，飞书/邮件收到空报告' },
              { icon: '🟡', tag: '中等', text: '飞书卡片内容可能超过4000字符限制，邮件SMTP的SSL/STARTTLS端口混用' },
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 bg-white rounded-lg p-3 border border-amber-200">
                <span className="text-lg flex-shrink-0">{item.icon}</span>
                <div>
                  <span className={`text-xs font-bold mr-2 ${item.tag === '致命' ? 'text-red-600' : item.tag === '高危' ? 'text-orange-600' : 'text-yellow-600'}`}>
                    [{item.tag}]
                  </span>
                  <span className="text-sm text-gray-700">{item.text}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Main Layout ── */}
      <div className="max-w-6xl mx-auto px-4 pb-16 flex flex-col lg:flex-row gap-6">

        {/* ── Sidebar ── */}
        <aside className="lg:w-64 flex-shrink-0 space-y-4">

          <SidebarProgress done={completedSteps.size} total={prompts.length} />

          {/* 搜索 */}
          <div className="bg-white rounded-xl border-2 border-gray-200 p-3">
            <div className="flex items-center gap-2 text-gray-400 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
              <IconSearch />
              <input
                type="text"
                placeholder="搜索问题..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="bg-transparent text-sm text-gray-700 placeholder-gray-400 outline-none flex-1"
              />
            </div>
          </div>

          {/* 分类筛选 */}
          <div className="bg-white rounded-xl border-2 border-gray-200 p-4">
            <div className="flex items-center gap-2 text-sm font-bold text-gray-600 mb-3">
              <IconFilter /><span>按模块筛选</span>
            </div>
            <div className="space-y-1">
              <button
                onClick={() => setSelectedCategory('all')}
                className={`w-full text-left text-sm px-3 py-2 rounded-lg transition-colors ${selectedCategory === 'all' ? 'bg-indigo-100 text-indigo-700 font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
              >
                📦 全部 <span className="float-right text-xs font-bold">{prompts.length}</span>
              </button>
              {Object.entries(CATEGORIES).map(([key, cat]) => {
                const count = prompts.filter(p => p.category === key).length;
                return (
                  <button
                    key={key}
                    onClick={() => setSelectedCategory(key)}
                    className={`w-full text-left text-sm px-3 py-2 rounded-lg transition-colors ${selectedCategory === key ? 'bg-indigo-100 text-indigo-700 font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
                  >
                    {cat.label} <span className="float-right text-xs font-bold">{count}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 严重度筛选 */}
          <div className="bg-white rounded-xl border-2 border-gray-200 p-4">
            <div className="text-sm font-bold text-gray-600 mb-3">⚡ 按严重度</div>
            <div className="space-y-1">
              {[
                { key: 'all', label: '全部', badge: '' },
                { key: 'critical', label: '💥 致命', badge: 'bg-red-100 text-red-700' },
                { key: 'high', label: '🔴 高危', badge: 'bg-orange-100 text-orange-700' },
                { key: 'medium', label: '🟡 中等', badge: 'bg-yellow-100 text-yellow-700' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setSelectedSeverity(key)}
                  className={`w-full text-left text-sm px-3 py-2 rounded-lg transition-colors ${selectedSeverity === key ? 'bg-indigo-100 text-indigo-700 font-semibold' : 'text-gray-600 hover:bg-gray-50'}`}
                >
                  {label}
                  <span className="float-right text-xs font-bold">
                    {key === 'all' ? prompts.length : prompts.filter(p => p.severity === key).length}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* 操作顺序提示 */}
          <div className="bg-blue-50 rounded-xl border-2 border-blue-200 p-4">
            <div className="text-xs font-bold text-blue-700 mb-2">💡 推荐操作顺序</div>
            <ol className="text-xs text-blue-800 space-y-1.5 list-decimal list-inside leading-relaxed">
              <li>先做<strong>诊断自检</strong>（步骤1-2）</li>
              <li>再修<strong>爬虫采集</strong>（步骤3-5）</li>
              <li>调整<strong>清洗过滤</strong>（步骤6-8）</li>
              <li>验证<strong>推送报告</strong>（步骤9-11）</li>
              <li>最后稳定<strong>调度+运维</strong></li>
            </ol>
          </div>
        </aside>

        {/* ── Prompt List ── */}
        <main className="flex-1 min-w-0 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-gray-700">
              {filtered.length === prompts.length ? `全部 ${prompts.length} 个修复步骤` : `筛选结果：${filtered.length} 个步骤`}
            </h2>
            <button
              onClick={() => {
                const allText = filtered.map(p =>
                  `=== 步骤${p.step}: ${p.title} ===\n\n${p.prompt}`
                ).join('\n\n' + '─'.repeat(60) + '\n\n');
                navigator.clipboard.writeText(allText);
              }}
              className="flex items-center gap-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-lg font-medium transition-colors"
            >
              <IconCopy /> 复制全部提示词
            </button>
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <div className="text-4xl mb-3">🔍</div>
              <p className="font-medium">没有匹配的步骤</p>
              <p className="text-sm">请尝试调整筛选条件</p>
            </div>
          ) : (
            filtered.map((p) => <PromptCard key={p.id} p={p} />)
          )}
        </main>
      </div>

      {/* ── 使用说明底栏 ── */}
      <div className="bg-gray-900 text-white">
        <div className="max-w-6xl mx-auto px-4 py-10">
          <h2 className="text-lg font-bold mb-6 text-center">📖 如何使用本手册</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { step: '①', icon: '🔢', title: '按步骤顺序操作', desc: '从步骤1开始，不要跳步。前面的问题可能是后面问题的根因。' },
              { step: '②', icon: '📋', title: '复制提示词', desc: '点击"复制提示词"按钮，打开 Trae，把提示词粘贴进去，让 AI 执行。' },
              { step: '③', icon: '✅', title: '执行验证命令', desc: '每步完成后，执行绿色框里的验证命令，确认修复生效再进行下一步。' },
              { step: '④', icon: '🔄', title: '遇到问题回溯', desc: '如果某步骤执行后验证不通过，把 Trae 的错误信息告诉它，让它继续修复。' },
            ].map(item => (
              <div key={item.step} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
                <div className="text-2xl mb-2">{item.icon}</div>
                <div className="text-sm font-bold text-white mb-1.5">{item.title}</div>
                <p className="text-xs text-gray-400 leading-relaxed">{item.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 bg-gray-800 rounded-xl p-5 border border-gray-700">
            <h3 className="font-bold text-sm text-yellow-400 mb-3">⚡ 最快修复路径（预计2-3小时）</h3>
            <div className="flex flex-wrap gap-2 text-xs">
              {[
                { label: '步骤1 启动自检', color: 'bg-red-900 text-red-200' },
                { label: '→ 步骤2 删坏import', color: 'bg-red-900 text-red-200' },
                { label: '→ 步骤3 修微博爬虫', color: 'bg-red-900 text-red-200' },
                { label: '→ 步骤6 放宽过滤', color: 'bg-orange-900 text-orange-200' },
                { label: '→ 步骤9 修日报推送', color: 'bg-orange-900 text-orange-200' },
                { label: '→ 步骤10 修飞书格式', color: 'bg-blue-900 text-blue-200' },
                { label: '→ 步骤12 修调度器', color: 'bg-green-900 text-green-200' },
                { label: '→ 验证完整推送流程 ✅', color: 'bg-green-800 text-green-200' },
              ].map(item => (
                <span key={item.label} className={`${item.color} px-2.5 py-1 rounded-full font-medium`}>{item.label}</span>
              ))}
            </div>
          </div>

          <p className="text-center text-xs text-gray-500 mt-6">
            基于项目 <code className="text-gray-400">weibo-hotsearch V4.3</code> 代码深度分析生成 · 如有疑问请对照日志逐步排查
          </p>
        </div>
      </div>
    </div>
  );
}
