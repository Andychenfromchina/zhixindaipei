import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

interface DimScore {
  score: number;
  max: number;
  label: string;
}

interface Product {
  bank: string;
  name: string;
  rate: string;
  max_amount: number;
  match: number;
  loan_type: string;
  term_months: string;
  channel: string;
  features: string;
  approval_rate: string;
  difficulty: number;
}

interface AnalysisResult {
  score: number;
  level: string;
  text: string;
  products: Product[];
  dimensions: Record<string, DimScore>;
}

/* ── 五维雷达图（SVG） ── */
function RadarChart({ dims }: { dims: Record<string, DimScore> }) {
  const entries = Object.values(dims);
  if (!entries.length) return null;
  const N = entries.length;
  const cx = 80, cy = 80, R = 62;
  const pcts = entries.map(d => d.score / d.max);

  const angleOf = (i: number) => (Math.PI * 2 * i) / N - Math.PI / 2;
  const pt = (i: number, r: number) => ({
    x: cx + r * Math.cos(angleOf(i)),
    y: cy + r * Math.sin(angleOf(i)),
  });

  const gridLevels = [0.25, 0.5, 0.75, 1.0];
  const shapePoints = pcts.map((p, i) => pt(i, p * R));
  const shapePath = shapePoints.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ') + ' Z';

  return (
    <svg viewBox="0 0 160 160" className="w-full max-w-[160px]">
      {/* Grid */}
      {gridLevels.map(lv => (
        <polygon key={lv}
          points={Array.from({length: N}, (_, i) => { const p = pt(i, lv * R); return `${p.x},${p.y}`; }).join(' ')}
          fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth="0.8"
        />
      ))}
      {/* Spokes */}
      {Array.from({length: N}, (_, i) => {
        const p = pt(i, R);
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="rgba(255,255,255,0.12)" strokeWidth="0.8" />;
      })}
      {/* Shape */}
      <path d={shapePath} fill="rgba(220,30,50,0.22)" stroke="#e8192c" strokeWidth="1.5" />
      {/* Dots */}
      {shapePoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r="2.5" fill="#e8192c" />
      ))}
      {/* Labels */}
      {entries.map((d, i) => {
        const p = pt(i, R + 14);
        return (
          <text key={i} x={p.x} y={p.y} textAnchor="middle" dominantBaseline="middle"
            fontSize="9" fill="rgba(255,255,255,0.65)" fontFamily="PingFang SC, sans-serif">
            {d.label}
          </text>
        );
      })}
    </svg>
  );
}

/* ── 五维明细条 ── */
function DimBar({ label, score, max }: { label: string; score: number; max: number }) {
  const pct = Math.round((score / max) * 100);
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)' }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#f5d070' }}>{score}<span style={{ color: 'rgba(255,255,255,0.35)', fontWeight: 400 }}>/{max}</span></span>
      </div>
      <div className="dim-bar-bg">
        <div className="dim-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/* ── 难度小徽章 ── */
function DiffBadge({ v }: { v: number }) {
  const label = v >= 0.70 ? '高门槛' : v >= 0.50 ? '中等' : '容易申请';
  const color = v >= 0.70 ? 'rgba(220,30,50,0.25)' : v >= 0.50 ? 'rgba(212,168,67,0.18)' : 'rgba(40,180,100,0.20)';
  const border = v >= 0.70 ? 'rgba(220,30,50,0.45)' : v >= 0.50 ? 'rgba(212,168,67,0.35)' : 'rgba(40,180,100,0.40)';
  const text = v >= 0.70 ? '#ff7788' : v >= 0.50 ? '#f5d070' : '#60e898';
  return (
    <span style={{ background: color, border: `1px solid ${border}`, color: text, borderRadius: 999, padding: '2px 10px', fontSize: 11, fontWeight: 500 }}>
      {label}
    </span>
  );
}

function App() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState('');

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const allowed = ['application/pdf', 'image/jpeg', 'image/png', 'application/json', 'text/plain'];
    if (!allowed.includes(file.type) && !file.name.endsWith('.json')) {
      setError('不支持的文件类型，请上传 PDF、JPG、PNG 或 JSON');
      return;
    }
    if (file.size > 10 * 1024 * 1024) { setError('文件不能超过 10MB'); return; }
    setLoading(true); setError(''); setResult(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `请求失败（${res.status}）`); }
      const data = await res.json();
      const products: Product[] = data.matches.map((p: {
        bank: string; product_name: string; effective_rate_after_subsidy: string;
        max_amount: number; match_score: number; loan_type: string; term_months: string;
        channel: string; features: string; approval_rate: string; difficulty: number;
      }) => ({
        bank: p.bank, name: p.product_name, rate: p.effective_rate_after_subsidy,
        max_amount: p.max_amount, match: p.match_score, loan_type: p.loan_type ?? '',
        term_months: p.term_months ?? '', channel: p.channel ?? '', features: p.features ?? '',
        approval_rate: p.approval_rate ?? '', difficulty: p.difficulty ?? 0.5,
      })).sort((a: Product, b: Product) => b.match - a.match);
      setResult({
        score: data.credit_health_score, level: data.risk_level,
        text: data.detailed_explanation, products,
        dimensions: data.score_dimensions ?? {},
      });
    } catch (err: unknown) {
      if (err instanceof TypeError) setError('无法连接后端，请确保后端窗口正在运行');
      else if (err instanceof Error) setError(`分析失败：${err.message}`);
      else setError('发生未知错误，请稍后重试');
    } finally { setLoading(false); }
  };

  const handleReset = () => { setResult(null); setError(''); };

  /* ── 评分颜色 ── */
  const scoreColor = (s: number) =>
    s >= 88 ? '#f5d070' : s >= 66 ? '#ff8844' : s >= 38 ? '#ff5566' : '#ff3344';

  return (
    <div className="bg-scene" style={{ minHeight: '100vh', paddingBottom: 80 }}>

      {/* ── 导航栏 ── */}
      <nav className="glass-nav" style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 680, margin: '0 auto', padding: '14px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="brand-mark" style={{ width: 38, height: 38, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}>
              ¥
            </div>
            <div>
              <div className="font-display text-gold" style={{ fontSize: 20, fontWeight: 700, letterSpacing: '0.05em' }}>百信百配</div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.38)', letterSpacing: '0.08em', marginTop: -2 }}>AI 智能贷款匹配平台</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#3ec96e', boxShadow: '0 0 6px #3ec96e' }} />
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', letterSpacing: '0.06em' }}>数据加密传输</span>
          </div>
        </div>
      </nav>

      <div style={{ paddingTop: 88, paddingLeft: 24, paddingRight: 24, maxWidth: 680, margin: '0 auto' }}>

        {/* ── Hero ── */}
        {!result && !loading && (
          <div className="fade-up" style={{ textAlign: 'center', marginBottom: 48, paddingTop: 40 }}>
            <div className="badge fade-up fade-up-1" style={{ marginBottom: 24 }}>
              ⚡ 30秒出结果 · 2026最新贴息政策 · 100款产品实时匹配
            </div>
            <h1 className="font-display" style={{ fontSize: 52, fontWeight: 900, lineHeight: 1.05, marginBottom: 16, letterSpacing: '-0.01em' }}>
              <span style={{ color: '#fff' }}>智能匹配</span><br />
              <span className="text-red-glow">最低利率贷款</span>
            </h1>
            <p style={{ fontSize: 18, color: 'rgba(255,255,255,0.60)', lineHeight: 1.6 }}>
              上传征信报告，AI为您精准匹配最优银行产品<br />
              <span style={{ fontSize: 14, color: 'rgba(255,255,255,0.35)' }}>基于人行征信评分模型 · 五维信用健康分 · 百家机构覆盖</span>
            </p>
            {/* 三项特性 */}
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 32, flexWrap: 'wrap' }}>
              {[['🔒','隐私保护','上传即加密，分析后销毁'],['📊','五维评分','对标人行征信体系'],['🏦','百款产品','覆盖全国主要金融机构']].map(([icon, t, s]) => (
                <div key={t} className="glass" style={{ padding: '14px 20px', textAlign: 'left', minWidth: 160, flex: 1 }}>
                  <div style={{ fontSize: 22, marginBottom: 6 }}>{icon}</div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 2 }}>{t}</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>{s}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── 错误提示 ── */}
        {error && (
          <div className="glass fade-up" style={{ marginBottom: 24, border: '1px solid rgba(220,30,50,0.50)', background: 'rgba(180,10,25,0.20)', padding: '16px 24px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 20 }}>⚠️</span>
            <span style={{ color: '#ff9999', fontSize: 15 }}>{error}</span>
          </div>
        )}

        {/* ── 上传区 ── */}
        {!result && !loading && (
          <label htmlFor="fileInput" className="upload-zone fade-up fade-up-2" style={{
            display: 'block', cursor: 'pointer',
            background: 'rgba(180,10,25,0.08)',
            border: '2px dashed rgba(220,30,50,0.30)',
            borderRadius: 24, padding: '56px 32px', textAlign: 'center',
          }}>
            {/* 文件图标 */}
            <div style={{
              width: 88, height: 88, margin: '0 auto 24px',
              background: 'linear-gradient(135deg, rgba(192,21,42,0.35), rgba(232,25,44,0.20))',
              border: '1px solid rgba(220,30,50,0.35)',
              borderRadius: 22, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 44,
              boxShadow: '0 4px 32px rgba(220,30,50,0.20)',
            }}>📄</div>

            <h2 className="font-display" style={{ fontSize: 26, fontWeight: 700, marginBottom: 10, color: '#fff' }}>
              上传您的征信报告
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.55)', marginBottom: 6, fontSize: 15 }}>支持 PDF · JPG · PNG · JSON</p>
            <p style={{ color: 'rgba(255,255,255,0.30)', marginBottom: 32, fontSize: 13 }}>可使用 test_sample_1.json 快速体验</p>

            <div className="btn-red" style={{
              display: 'inline-block', padding: '14px 40px', borderRadius: 14, fontSize: 16,
            }}>
              选取文件
            </div>

            <div className="divider-gold" style={{ maxWidth: 300, margin: '32px auto 24px' }} />
            <div style={{ display: 'flex', justifyContent: 'center', gap: 24, fontSize: 12, color: 'rgba(255,255,255,0.30)' }}>
              <span>🔐 AES-256加密</span>
              <span>⚡ 极速分析</span>
              <span>🏦 百款产品</span>
            </div>

            <input id="fileInput" type="file" accept=".pdf,.jpg,.jpeg,.png,.json,.txt" style={{ display: 'none' }} onChange={handleFileSelect} />
          </label>
        )}

        {/* ── 加载中 ── */}
        {loading && (
          <div className="fade-up" style={{ textAlign: 'center', padding: '80px 0' }}>
            <div className="spinner-red" style={{ margin: '0 auto 32px' }} />
            <h3 className="font-display" style={{ fontSize: 28, fontWeight: 700, marginBottom: 10 }}>
              <span className="text-gold">AI</span> 正在深度分析...
            </h3>
            <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 15 }}>正在匹配100款产品，对照五维征信模型</p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 32 }}>
              {['解析报告','评估五维','产品匹配','排序推荐'].map((s, i) => (
                <div key={s} style={{
                  background: 'rgba(220,30,50,0.15)', border: '1px solid rgba(220,30,50,0.30)',
                  borderRadius: 999, padding: '4px 14px', fontSize: 12, color: 'rgba(255,255,255,0.55)',
                  animation: `fade-up 0.4s ease ${i * 0.15}s both`,
                }}>
                  {s}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── 结果页 ── */}
        {result && (
          <div>
            {/* 返回 */}
            <div className="fade-up" style={{ textAlign: 'center', marginBottom: 28 }}>
              <button onClick={handleReset} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.40)', fontSize: 13, textDecoration: 'underline', textUnderlineOffset: 4 }}>
                ← 重新上传
              </button>
            </div>

            {/* 信用健康分卡片 */}
            <div className="glass-red fade-up fade-up-1" style={{ padding: '40px 32px', marginBottom: 20, position: 'relative', overflow: 'hidden' }}>
              {/* 背景装饰圆 */}
              <div style={{ position: 'absolute', top: -60, right: -60, width: 200, height: 200, background: 'radial-gradient(circle, rgba(220,30,50,0.18) 0%, transparent 70%)', pointerEvents: 'none' }} />
              <div style={{ position: 'absolute', bottom: -40, left: -40, width: 160, height: 160, background: 'radial-gradient(circle, rgba(212,168,67,0.12) 0%, transparent 70%)', pointerEvents: 'none' }} />

              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 24, flexWrap: 'wrap' }}>
                {/* 分数 */}
                <div style={{ flex: 1, minWidth: 160 }}>
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.50)', letterSpacing: '0.12em', marginBottom: 8, textTransform: 'uppercase' }}>信用健康分</div>
                  <div className="score-display" style={{ fontSize: 100 }}>
                    {typeof result.score === 'number' ? result.score : '—'}
                  </div>
                  <div style={{ fontSize: 15, color: 'rgba(255,255,255,0.45)', marginTop: -4 }}>/99分</div>
                  <div style={{ marginTop: 16 }}>
                    <span style={{
                      background: 'rgba(0,0,0,0.30)', border: `1px solid ${scoreColor(result.score)}44`,
                      color: scoreColor(result.score), borderRadius: 10, padding: '6px 16px', fontSize: 14, fontWeight: 600,
                    }}>
                      {result.level}
                    </span>
                  </div>
                </div>

                {/* 雷达图 */}
                {Object.keys(result.dimensions).length > 0 && (
                  <div style={{ flexShrink: 0 }}>
                    <RadarChart dims={result.dimensions} />
                  </div>
                )}
              </div>

              {/* 五维条形 */}
              {Object.keys(result.dimensions).length > 0 && (
                <div style={{ marginTop: 28, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 24px' }}>
                  {Object.values(result.dimensions).map(d => (
                    <DimBar key={d.label} label={d.label} score={d.score} max={d.max} />
                  ))}
                </div>
              )}
            </div>

            {/* 诊断说明 */}
            <div className="glass fade-up fade-up-2" style={{ padding: '24px 28px', marginBottom: 20 }}>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.40)', letterSpacing: '0.10em', marginBottom: 12 }}>▌ AI 诊断说明</div>
              <p style={{ fontSize: 14, lineHeight: 1.75, color: 'rgba(255,255,255,0.75)', margin: 0 }}>{result.text}</p>
            </div>

            {/* 产品推荐 */}
            <div className="fade-up fade-up-3">
              <div style={{ textAlign: 'center', marginBottom: 24 }}>
                <h3 className="font-display" style={{ fontSize: 24, fontWeight: 700, marginBottom: 6 }}>
                  <span className="text-gold">专属推荐</span> · {result.products.length} 款产品
                </h3>
                <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.38)' }}>按匹配度从高到低排序，优先展示通过率最高方案</p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {result.products.map((p, i) => (
                  <div
                    key={i}
                    className={`glass card-hover fade-up fade-up-${Math.min(i + 3, 5)}`}
                    style={{ padding: '24px 24px 20px', animationDelay: `${0.20 + i * 0.06}s` }}
                  >
                    {/* 产品头部行 */}
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, flex: 1 }}>
                        {/* 排名 */}
                        <div className={`rank-num ${i === 0 ? 'rank-1' : i === 1 ? 'rank-2' : i === 2 ? 'rank-3' : 'rank-n'}`}>
                          {i + 1}
                        </div>
                        <div>
                          <div style={{ fontSize: 17, fontWeight: 700, color: '#fff', lineHeight: 1.2 }}>{p.name}</div>
                          <div style={{ fontSize: 13, color: 'rgba(220,30,50,0.90)', marginTop: 3 }}>{p.bank}</div>
                          {p.loan_type && <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>{p.loan_type}</div>}
                        </div>
                      </div>
                      {/* 利率 */}
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div style={{ fontSize: 24, fontWeight: 800, color: '#f5d070', lineHeight: 1.1 }}>{p.rate}</div>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.40)', marginTop: 2 }}>年化（贴息后）</div>
                      </div>
                    </div>

                    <div className="divider-gold" style={{ margin: '16px 0 14px' }} />

                    {/* 数据行 */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 14 }}>
                      {/* 匹配度 */}
                      <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 12, padding: '12px 14px' }}>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', marginBottom: 4 }}>匹配度</div>
                        <div style={{ fontSize: 22, fontWeight: 800, color: p.match >= 80 ? '#f5d070' : p.match >= 60 ? '#ff8844' : '#ff5566' }}>
                          {p.match}
                        </div>
                        <div style={{ height: 4, background: 'rgba(255,255,255,0.10)', borderRadius: 999, marginTop: 6, overflow: 'hidden' }}>
                          <div className="progress-red" style={{ width: `${p.match}%` }} />
                        </div>
                      </div>
                      {/* 最高额度 */}
                      <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 12, padding: '12px 14px' }}>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', marginBottom: 4 }}>最高额度</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: '#fff' }}>
                          {p.max_amount}<span style={{ fontSize: 12, fontWeight: 400, color: 'rgba(255,255,255,0.50)' }}>万</span>
                        </div>
                        {p.term_months && <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 4 }}>≤{p.term_months}月</div>}
                      </div>
                      {/* 通过率 */}
                      <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 12, padding: '12px 14px' }}>
                        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', marginBottom: 4 }}>参考通过率</div>
                        <div style={{ fontSize: 20, fontWeight: 800, color: '#3ec96e' }}>{p.approval_rate}</div>
                        <div style={{ marginTop: 6 }}><DiffBadge v={p.difficulty} /></div>
                      </div>
                    </div>

                    {/* 核心特点 */}
                    {p.features && (
                      <div style={{ background: 'rgba(220,30,50,0.08)', border: '1px solid rgba(220,30,50,0.18)', borderRadius: 10, padding: '8px 14px', fontSize: 12, color: 'rgba(255,255,255,0.58)', marginBottom: 10 }}>
                        💡 {p.features}
                      </div>
                    )}

                    {/* 申请渠道 + 按钮 */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                      {p.channel && (
                        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.30)' }}>申请渠道：{p.channel}</span>
                      )}
                      <button
                        className="btn-red"
                        onClick={() => alert(`即将跳转至 ${p.bank} — ${p.name} 申请页面`)}
                        style={{ flex: 1, padding: '12px 20px', borderRadius: 12, fontSize: 14 }}
                      >
                        立即申请
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* 底部重置 */}
            <div style={{ textAlign: 'center', marginTop: 40 }}>
              <button onClick={handleReset} className="glass" style={{
                border: '1px solid rgba(220,30,50,0.25)', padding: '14px 40px', borderRadius: 14, fontSize: 15,
                color: 'rgba(255,255,255,0.70)', cursor: 'pointer', background: 'rgba(180,10,25,0.10)',
                transition: 'all 0.2s',
              }}>
                重新分析另一份报告
              </button>
            </div>
          </div>
        )}

        {/* ── 底部说明 ── */}
        {!result && !loading && (
          <div className="fade-up fade-up-4" style={{ marginTop: 56, textAlign: 'center' }}>
            <div className="divider-gold" />
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)', lineHeight: 1.8 }}>
              百信百配 · AI智能贷款匹配平台<br />
              数据仅用于本次分析，不留存 · 不共享 · 不用于任何商业目的<br />
              <span style={{ color: 'rgba(220,30,50,0.50)' }}>©2026 百信百配</span>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
