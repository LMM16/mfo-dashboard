"""
MFO Brasil — Dashboard Builder
Fonte: CVM Dados Abertos — cad_adm_cart.zip (pj + pf)
"""
import pandas as pd
import requests, zipfile, io, json, sys
from datetime import datetime, date
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)

CVM_ADM_URL    = "https://dados.cvm.gov.br/dados/ADM_CART/CAD/DADOS/cad_adm_cart.zip"
CVM_CONSUL_URL = "https://dados.cvm.gov.br/dados/CONSUL_VALOR/CAD/DADOS/cad_consul_val.zip"

# Keywords genéricas para identificar MFOs por tipo
MFO_KEYWORDS = [
    "family office", "family", "patrimônio", "patrimonio", "wealth",
    "familiar", "multifamily", "multi-family", "gestão patrimonial",
    "gestao patrimonial", "private wealth", "private", "fortune",
    "multi family", "mfo",
]

# Lista curada de MFOs conhecidos (nomes parciais em lowercase)
KNOWN_MFOS = [
    "1618", "051 capital", "adduntia", "aeternus", "amb family",
    "aqua wealth", "aram capital", "arbitral", "attimo", "aware",
    "azimut", "bevas", "bnr family", "brasil wm", "capital advisors",
    "capri family", "carpa family", "centuria", "cimo family",
    "consist mfo", "criteria", "ekho", "eleva invest", "enseada family",
    "ethos investimentos", "etrnty", "fd international", "g5 partners",
    "galacticos", "genesis", "ghia", "grupo independiente",
    "gutierrez group", "hieron", "horizonte mx", "ibbra", "incipio",
    "investport", "jera capital", "legend", "lombard odier", "lxg family",
    "mandatto", "setta", "mercury", "mfo advisors", "milenium family",
    "misti capital", "moma family", "naopim", "nau capital", "oikos",
    "orion advisors", "oriz partners", "patagonia capital", "perfin",
    "portofino", "portogallo", "pragma", "privatto", "promecap",
    "sastre", "seven pounds", "sg mfo", "sonata", "sow capital",
    "sten capital", "sten gestão", "taler gestão", "tempus asset",
    "tera capital", "trafalgar", "troon capital", "turim",
    "veneto family", "vokin", "we capital", "whg", "wisdom family",
    "wright", "vitra", "ventura",
]

def fetch_zip(url, label):
    print(f"  Baixando {label}...")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return zipfile.ZipFile(io.BytesIO(resp.content))
    except Exception as e:
        print(f"    ERRO: {e}")
        return None

def read_csv_from_zip(z, filename):
    try:
        with z.open(filename) as f:
            df = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)
        df.columns = [c.strip().upper() for c in df.columns]
        return df.fillna("")
    except Exception as e:
        print(f"    ERRO ao ler {filename}: {e}")
        return pd.DataFrame()

def is_mfo(nome):
    nome_lower = nome.lower()
    # Checa keywords genéricas
    if any(kw in nome_lower for kw in MFO_KEYWORDS):
        return True
    # Checa lista curada de MFOs conhecidos
    if any(kw in nome_lower for kw in KNOWN_MFOS):
        return True
    return False

def main():
    print("=== MFO Brasil Dashboard Builder ===")
    print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

    # ── Administradores PJ (firmas) ───────────────────
    print("1. Coletando administradores de carteira (PJ)...")
    z_adm = fetch_zip(CVM_ADM_URL, "ADM_CART")
    df_pj = pd.DataFrame()
    if z_adm:
        print(f"   Arquivos no ZIP: {z_adm.namelist()}")
        df_pj = read_csv_from_zip(z_adm, "cad_adm_cart_pj.csv")
        print(f"   PJ: {len(df_pj)} linhas | colunas: {list(df_pj.columns)}")

    # ── Consultores PJ ────────────────────────────────
    print("\n2. Coletando consultores de valores mobiliários...")
    z_consul = fetch_zip(CVM_CONSUL_URL, "CONSUL_VALOR")
    df_consul = pd.DataFrame()
    if z_consul:
        print(f"   Arquivos no ZIP: {z_consul.namelist()}")
        # tenta pj primeiro, depois o primeiro csv disponível
        csv_files = [f for f in z_consul.namelist() if f.endswith('.csv')]
        for fname in csv_files:
            if 'pj' in fname.lower():
                df_consul = read_csv_from_zip(z_consul, fname)
                print(f"   Lido {fname}: {len(df_consul)} linhas")
                break
        if df_consul.empty and csv_files:
            df_consul = read_csv_from_zip(z_consul, csv_files[0])
            print(f"   Lido {csv_files[0]}: {len(df_consul)} linhas")

    # ── Normalizar PJ admins ──────────────────────────
    print("\n3. Normalizando...")
    rows = []
    for _, r in df_pj.iterrows():
        nome   = str(r.get("DENOM_SOCIAL","") or r.get("DENOM_COMERC","")).strip()
        cnpj   = str(r.get("CNPJ","")).strip()
        sit    = str(r.get("SIT","")).strip()
        dt_reg = str(r.get("DT_REG","")).strip()
        uf     = str(r.get("UF","")).strip()
        categ  = str(r.get("CATEG_REG","")).strip()
        email  = str(r.get("EMAIL","")).strip()
        site   = str(r.get("SITE_ADMIN","")).strip()
        patrim = str(r.get("VL_PATRIM_LIQ","")).strip()
        rows.append(dict(
            NOME_SOCIAL=nome, CNPJ_CPF=cnpj, SITUACAO=sit,
            DT_REGISTRO=dt_reg, UF=uf, CATEG_REG=categ,
            EMAIL=email, SITE=site, PATRIM_LIQ=patrim, FONTE="ADM_PJ"
        ))

    # normalizar consultores se tiver colunas compatíveis
    if not df_consul.empty:
        col_nome = next((c for c in ["DENOM_SOCIAL","NOME","NOME_SOCIAL"] if c in df_consul.columns), None)
        col_cnpj = next((c for c in ["CNPJ","CNPJ_CPF"] if c in df_consul.columns), None)
        col_sit  = next((c for c in ["SIT","SITUACAO"] if c in df_consul.columns), None)
        col_uf   = next((c for c in ["UF","ESTADO"] if c in df_consul.columns), None)
        col_dt   = next((c for c in ["DT_REG","DT_REGISTRO"] if c in df_consul.columns), None)
        if col_nome and col_cnpj:
            for _, r in df_consul.iterrows():
                rows.append(dict(
                    NOME_SOCIAL=str(r.get(col_nome,"")).strip(),
                    CNPJ_CPF=str(r.get(col_cnpj,"")).strip(),
                    SITUACAO=str(r.get(col_sit,"")).strip() if col_sit else "",
                    DT_REGISTRO=str(r.get(col_dt,"")).strip() if col_dt else "",
                    UF=str(r.get(col_uf,"")).strip() if col_uf else "",
                    CATEG_REG="", EMAIL="", SITE="", PATRIM_LIQ="", FONTE="CONSUL"
                ))

    df = pd.DataFrame(rows)
    if df.empty:
        print("ERRO: nenhum dado.")
        sys.exit(1)

    df = df.drop_duplicates(subset=["CNPJ_CPF"])
    print(f"   Total único: {len(df)}")

    # Ativos
    df_ativos = df[df["SITUACAO"].str.upper().str.contains("FUNCIONAMENTO|AUTORIZADO|ATIVO", na=False)].copy()
    if df_ativos.empty:
        print("   AVISO: filtro de situação não encontrou ativos — usando todos")
        df_ativos = df.copy()
    print(f"   Ativos: {len(df_ativos)}")

    # ── Classificar MFOs ──────────────────────────────
    print("\n4. Identificando MFOs...")
    df_ativos["IS_MFO"] = df_ativos["NOME_SOCIAL"].apply(is_mfo)
    # também marca se categoria contiver patrimônio
    df_ativos["IS_MFO"] = df_ativos["IS_MFO"] | df_ativos["CATEG_REG"].str.lower().str.contains("patrimônio|patrimonio|wealth", na=False)
    df_ativos["CLASSIFICACAO"] = df_ativos["IS_MFO"].map({True:"MFO/Wealth Management", False:"Outro"})
    n_mfo = df_ativos["IS_MFO"].sum()
    print(f"   MFOs identificados: {n_mfo}")

    # ── Score M&A ─────────────────────────────────────
    print("\n5. Calculando scores...")
    def score(r):
        s = 0.0
        try:
            ano = int(str(r["DT_REGISTRO"])[:4])
            anos = date.today().year - ano
            if 5 <= anos <= 15: s += 2.0
            elif 3 <= anos < 5 or 15 < anos <= 20: s += 1.0
            elif anos > 0: s += 0.5
        except: pass
        if r["IS_MFO"]: s += 2.0
        if str(r["UF"]).strip().upper() in ("SP","RJ"): s += 1.0
        elif str(r["UF"]).strip().upper() in ("MG","RS","PR","DF"): s += 0.5
        if str(r.get("EMAIL","")).strip() not in ("","nan","N/A"): s += 0.5
        if str(r.get("SITE","")).strip() not in ("","nan","N/A"): s += 0.5
        # PL da gestora como proxy de porte (peso 4.0)
        try:
            pl = float(str(r.get("PATRIM_LIQ","")).replace(",","."))
            if pl >= 50_000_000:   s += 4.0   # >= R$50M
            elif pl >= 10_000_000: s += 3.0   # >= R$10M
            elif pl >= 1_000_000:  s += 2.0   # >= R$1M
            elif pl > 0:           s += 1.0
        except: pass
        return round(min(s, 10.0), 1)

    df_ativos["SCORE_MA"] = df_ativos.apply(score, axis=1)
    df_mfo = df_ativos[df_ativos["IS_MFO"]].sort_values("SCORE_MA", ascending=False).reset_index(drop=True)

    # Evolução
    df_ativos["ANO_REG"] = df_ativos["DT_REGISTRO"].str[:4]
    evolucao = (df_ativos.groupby("ANO_REG").size()
                .reset_index(name="count")
                .pipe(lambda d: d[d["ANO_REG"].str.match(r"^\d{4}$")])
                .sort_values("ANO_REG"))

    geo       = df_mfo["UF"].value_counts().head(10).to_dict()
    tipo_dist = df_ativos["CLASSIFICACAO"].value_counts().to_dict()
    n_alvos   = int((df_mfo["SCORE_MA"] >= 7).sum())
    n_novos   = int((df_ativos["ANO_REG"] == str(date.today().year)).sum())

    print("\n6. Gerando HTML...")
    html = build_html(df_mfo, df_ativos, evolucao, geo, tipo_dist, n_alvos, n_novos)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    df_mfo.to_csv(DOCS_DIR / "mfos.csv", index=False, encoding="utf-8-sig")
    print(f"   MFOs no CSV: {len(df_mfo)}")
    print("=== Concluído! ===")

def build_html(df_mfo, df_all, evolucao, geo, tipo_dist, n_alvos, n_novos):
    now     = datetime.now().strftime("%d/%m/%Y %H:%M")
    n_total = len(df_all)
    n_mfo   = len(df_mfo)

    rows = ""
    for i, (_, r) in enumerate(df_mfo.head(50).iterrows(), 1):
        score = r["SCORE_MA"]
        sc    = "score-high" if score >= 8 else ("score-mid" if score >= 6 else "score-low")
        ano   = str(r.get("DT_REGISTRO",""))[:4] or "—"
        uf    = str(r.get("UF","")).strip() or "—"
        cnpj  = str(r.get("CNPJ_CPF","")).strip()
        nome  = str(r.get("NOME_SOCIAL","")).strip().title() or "—"
        email = str(r.get("EMAIL","")).strip()
        site  = str(r.get("SITE","")).strip()
        categ = str(r.get("CATEG_REG","")).strip()
        em_html = (f'<a href="mailto:{email}" style="color:var(--gold);font-size:9px">{email[:30]}</a>'
                   if email and email not in ("nan","N/A","") else "—")
        site_html = (f'<a href="{site}" target="_blank" style="color:var(--blue);font-size:9px">↗ site</a>'
                     if site and site not in ("nan","N/A","") else "")
        # Formatar PL
        try:
            pl_val = float(str(r.get("PATRIM_LIQ","")).replace(",","."))
            if pl_val >= 1_000_000_000:
                pl_fmt = f"R$ {pl_val/1_000_000_000:.1f}B"
            elif pl_val >= 1_000_000:
                pl_fmt = f"R$ {pl_val/1_000_000:.1f}M"
            elif pl_val > 0:
                pl_fmt = f"R$ {pl_val/1_000:.0f}K"
            else:
                pl_fmt = "—"
        except:
            pl_fmt = "—"

        rows += f"""<tr>
          <td><span class="mono subtle">{i:02d}</span></td>
          <td><div class="firm-name">{nome}</div><div class="mono micro subtle">{cnpj}</div></td>
          <td><span class="mono small">{uf}</span></td>
          <td><span class="mono micro">{ano}</span></td>
          <td><span class="mono small" style="color:var(--ink);font-weight:600">{pl_fmt}</span></td>
          <td><span class="score-dot {sc}">{score}</span></td>
          <td>{em_html} {site_html}</td>
        </tr>"""

    anos_evo   = json.dumps(evolucao["ANO_REG"].tolist())
    counts_evo = json.dumps(evolucao["count"].tolist())
    geo_labels = json.dumps(list(geo.keys()))
    geo_vals   = json.dumps(list(geo.values()))
    tipo_labels= json.dumps(list(tipo_dist.keys()))
    tipo_vals  = json.dumps(list(tipo_dist.values()))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MFO Brasil — Inteligência de Mercado</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{{--ink:#0d0d0d;--muted:#5a5a5a;--subtle:#a0a0a0;--line:#e0ddd8;--bg:#f5f3ee;--card:#fdfcfa;--gold:#b8965a;--gold-pale:#f5eed9;--green:#2d6a4f;--green-pale:#d8ede2;--red:#9b2335;--red-pale:#f5dde0;--blue:#1a3a6b}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Syne',sans-serif;background:var(--bg);color:var(--ink);min-height:100vh}}
.shell{{display:grid;grid-template-columns:210px 1fr;min-height:100vh}}
.sidebar{{background:var(--ink);color:#fff;display:flex;flex-direction:column;padding:28px 0;position:sticky;top:0;height:100vh}}
.brand{{padding:0 22px 24px;border-bottom:1px solid #222}}
.brand-label{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.12em;color:var(--gold);text-transform:uppercase;margin-bottom:5px}}
.brand-name{{font-size:20px;font-weight:800;letter-spacing:-.02em}}
.brand-name span{{color:var(--gold)}}
.brand-sub{{font-family:'DM Mono',monospace;font-size:9px;color:#444;margin-top:3px}}
.nav{{padding:16px 0;flex:1}}
.nav-sec{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.1em;color:#333;text-transform:uppercase;padding:12px 22px 5px}}
.nav-item{{display:flex;align-items:center;gap:9px;padding:8px 22px;font-size:12px;font-weight:600;color:#666;border-left:3px solid transparent}}
.nav-item.active{{color:#fff;border-left-color:var(--gold);background:#141414}}
.sid-foot{{padding:18px 22px;border-top:1px solid #1a1a1a;font-family:'DM Mono',monospace;font-size:9px;color:#333;line-height:1.8}}
.dot{{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-right:4px;vertical-align:middle}}
.main{{overflow-y:auto}}
.topbar{{background:var(--card);border-bottom:1px solid var(--line);padding:14px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}}
.topbar-t{{font-size:14px;font-weight:700}}.topbar-m{{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);margin-top:2px}}
.updated{{font-family:'DM Mono',monospace;font-size:9px;background:var(--green-pale);color:var(--green);padding:4px 10px;border-radius:20px}}
.content{{padding:24px 28px}}
.kpi-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}}
.kpi-l{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.08em;color:var(--subtle);text-transform:uppercase;margin-bottom:8px}}
.kpi-v{{font-size:28px;font-weight:800;letter-spacing:-.03em;line-height:1}}
.kpi-d{{font-family:'DM Mono',monospace;font-size:10px;margin-top:5px;color:var(--green)}}
.grid-3{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;margin-bottom:24px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px 22px}}
.card-t{{font-size:12px;font-weight:700;margin-bottom:4px}}.card-sub{{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);margin-bottom:16px}}
.sec-hd{{display:flex;align-items:center;gap:10px;margin-bottom:14px}}
.sec-hd h2{{font-size:13px;font-weight:700}}.sec-cnt{{font-family:'DM Mono',monospace;font-size:10px;color:var(--subtle)}}
.ml-auto{{margin-left:auto}}
.btn{{font-family:'DM Mono',monospace;font-size:10px;padding:6px 14px;border-radius:6px;background:var(--gold);color:#fff;text-decoration:none;display:inline-block}}
.table-wrap{{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse}}
thead th{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.08em;color:var(--subtle);text-transform:uppercase;padding:9px 20px;text-align:left;background:var(--bg);border-bottom:1px solid var(--line);white-space:nowrap}}
tbody tr{{transition:background .1s}}tbody tr:hover{{background:var(--gold-pale)}}
tbody tr:not(:last-child){{border-bottom:1px solid var(--line)}}
tbody td{{padding:11px 20px;font-size:12px;vertical-align:middle}}
.firm-name{{font-weight:700;font-size:12px}}
.mono{{font-family:'DM Mono',monospace}}.micro{{font-size:9px}}.small{{font-size:11px}}.subtle{{color:var(--subtle)}}
.score-dot{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-family:'DM Mono',monospace;font-size:10px;font-weight:500}}
.score-high{{background:var(--green-pale);color:var(--green)}}.score-mid{{background:var(--gold-pale);color:#7a5c00}}.score-low{{background:var(--red-pale);color:var(--red)}}
.blist{{list-style:none;margin-top:12px}}.bitem{{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--line);font-size:11px}}
.bitem:last-child{{border:none}}.bcolor{{width:9px;height:9px;border-radius:2px;flex-shrink:0}}.bname{{flex:1;font-weight:600}}.bcnt{{font-family:'DM Mono',monospace;font-size:10px;color:var(--muted)}}
.fnote{{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);text-align:center;padding:20px 0 4px;border-top:1px solid var(--line);margin-top:8px;line-height:1.8}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
  <div class="brand">
    <div class="brand-label">Inteligência de Mercado</div>
    <div class="brand-name">MFO<span>BR</span></div>
    <div class="brand-sub">CVM · ANBIMA · RFB</div>
  </div>
  <nav class="nav">
    <div class="nav-sec">Análise</div>
    <div class="nav-item active">◈ Dashboard</div>
    <div class="nav-sec">Dados</div>
    <div class="nav-item"><a href="mfos.csv" style="color:#666;text-decoration:none">↓ Exportar CSV</a></div>
  </nav>
  <div class="sid-foot"><span class="dot"></span>Dados CVM ao vivo<br>Atualização semanal<br>GitHub Actions</div>
</aside>
<main class="main">
  <div class="topbar">
    <div><div class="topbar-t">MFOs &amp; Gestores de Patrimônio — Brasil</div>
    <div class="topbar-m">Cadastro CVM · Ref. {now}</div></div>
    <span class="updated">⬤ Atualizado {now}</span>
  </div>
  <div class="content">
    <div class="kpi-strip">
      <div class="kpi"><div class="kpi-l">Firmas ativas (CVM)</div><div class="kpi-v">{n_total:,}</div><div class="kpi-d">Adm. carteira + Consultores</div></div>
      <div class="kpi"><div class="kpi-l">MFOs identificados</div><div class="kpi-v">{n_mfo:,}</div><div class="kpi-d">Heurística multicritério</div></div>
      <div class="kpi"><div class="kpi-l">Alvos M&amp;A (score ≥ 7)</div><div class="kpi-v">{n_alvos:,}</div><div class="kpi-d" style="color:var(--gold)">⬤ Alta prioridade</div></div>
      <div class="kpi"><div class="kpi-l">Novos em {date.today().year}</div><div class="kpi-v">{n_novos:,}</div><div class="kpi-d">Registros no ano</div></div>
    </div>
    <div class="grid-3">
      <div class="card">
        <div class="card-t">Crescimento da indústria</div>
        <div class="card-sub">Registros ativos por ano · CVM</div>
        <div style="height:180px"><canvas id="growthChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-t">Perfil do universo</div>
        <div class="card-sub">Por classificação</div>
        <div style="height:110px"><canvas id="typeChart"></canvas></div>
        <ul class="blist">{"".join(f'<li class="bitem"><span class="bcolor" style="background:{c}"></span><span class="bname">{k}</span><span class="bcnt">{v}</span></li>' for (k,v),c in zip(sorted(tipo_dist.items(),key=lambda x:-x[1]),["#b8965a","#1a3a6b","#4a2d7a","#2d6a4f","#888"]))}</ul>
      </div>
      <div class="card">
        <div class="card-t">Concentração por UF</div>
        <div class="card-sub">Top estados · MFOs</div>
        <div style="height:180px"><canvas id="stateChart"></canvas></div>
      </div>
    </div>
    <div class="sec-hd">
      <h2>Ranking MFOs — Score M&amp;A</h2>
      <span class="sec-cnt">Top 50 de {n_mfo} identificados</span>
      <div class="ml-auto"><a href="mfos.csv" class="btn">↓ CSV completo ({n_mfo} firmas)</a></div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>#</th><th>Firma</th><th>UF</th><th>Registro</th><th>PL Gestora</th><th>Score M&A</th><th>Contato</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div class="fnote">
      Fonte: CVM Dados Abertos (dados.cvm.gov.br) · Atualização automática via GitHub Actions · {now}<br>
      MFOs identificados por heurística: nome social + categoria CVM. Score M&A: modelo 0–10.<br>
      Este dashboard não constitui recomendação de investimento.
    </div>
  </div>
</main>
</div>
<script>
const mono="'DM Mono',monospace",gold="#b8965a",lineC="#e0ddd8",ink="#0d0d0d";
new Chart(document.getElementById('growthChart'),{{type:'line',data:{{labels:{anos_evo},datasets:[{{label:'Registros',data:{counts_evo},borderColor:ink,backgroundColor:'transparent',borderWidth:2,pointRadius:0,tension:.4}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{color:lineC}},ticks:{{font:{{family:mono,size:8}},color:'#aaa',maxTicksLimit:8}}}},y:{{grid:{{color:lineC}},ticks:{{font:{{family:mono,size:8}},color:'#aaa'}}}}}}}}}});
new Chart(document.getElementById('typeChart'),{{type:'doughnut',data:{{labels:{tipo_labels},datasets:[{{data:{tipo_vals},backgroundColor:['#b8965a','#1a3a6b','#4a2d7a'],borderWidth:0}}]}},options:{{responsive:true,maintainAspectRatio:false,cutout:'65%',plugins:{{legend:{{display:false}}}}}}}});
new Chart(document.getElementById('stateChart'),{{type:'bar',data:{{labels:{geo_labels},datasets:[{{data:{geo_vals},backgroundColor:gold+'cc',borderWidth:0,borderRadius:3}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{display:false}},ticks:{{font:{{family:mono,size:9}},color:'#aaa'}}}},y:{{grid:{{color:lineC}},ticks:{{font:{{family:mono,size:9}},color:'#aaa'}}}}}}}}}});
</script>
</body></html>"""

if __name__ == "__main__":
    main()
