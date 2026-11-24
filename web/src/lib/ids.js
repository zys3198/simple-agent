export function idInfo(id) {
  let m = id.match(/^PMID (\d+)$/);
  if (m) return { url: `https://pubmed.ncbi.nlm.nih.gov/${m[1]}/`, site: 'PubMed' };
  if (/^ENSG\d+$/.test(id)) return { url: `https://www.ensembl.org/id/${id}`, site: 'Ensembl' };
  if (/^(MONDO|EFO|Orphanet|HP)_?\d+$/.test(id)) return { url: `https://platform.opentargets.org/disease/${id}`, site: 'Open Targets' };
  return { url: '', site: '来源不明' };
}

/* 台账 snippet 是标识符所在的那一行（工具输出是 tab 分隔的表）：
   从中认出人能读的名字——PubMed 的标题、基因符号、疾病名；编号降到第二行 */
export function describeId(id, snippet) {
  const cols = String(snippet || '').split('\t').map(s => s.trim()).filter(Boolean);
  const line = cols.join(' · ').slice(0, 160);
  const m = id.match(/^PMID (\d+)$/);
  if (m) {
    if ((cols[0] || '').startsWith('PMID ')) {
      // PubMed 检索行：PMID / 年份 / 期刊 / 标题
      return { title: cols.slice(3).join(' ') || `PubMed PMID ${m[1]}`, sub: cols.slice(1, 3).join(' · ') || line };
    }
    return { title: `PubMed PMID ${m[1]}`, sub: line };
  }
  const at = cols.indexOf(id);
  const nearby = at < 0 ? cols : [...cols.slice(0, at), ...cols.slice(at + 1)];
  const name = nearby.find(c => c.length > 1 && !/[\/=]/.test(c) && !/^\d+$/.test(c));
  return { title: name || id, sub: cols.filter(c => c !== name).join(' · ').slice(0, 160) };
}
