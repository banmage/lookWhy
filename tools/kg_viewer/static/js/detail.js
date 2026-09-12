/* kg_viewer 文档详情弹窗（2026-09-12）：
 * 拉取 /api/doc/<doc_id>/detail，以分层可折叠结构展示文档级信息——
 * 基本信息 / 时间与关系 / 组织机构 / 术语和定义（可逐条展开）/ 标准要素（可逐层展开、
 * 点击跳结构树）/ 清单核对（GBT-E01~E14、GBT-M01~M14）。
 * 纯原生 JS，无外部依赖；index 与 doc 页共用 window.openDocDetail()。
 */
(function () {
  'use strict';

  const KIND_CN = {
    documentBlock: '文前/文后块', section: '章', clause: '条', subClause: '款',
    item: '项', subItem: '子项', annex: '附录', annexSection: '附录条'
  };
  const NATURE_CN = { '必备': 'must', '可选': 'may', '规范性': 'norm', '资料性': 'info' };

  function esc(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function mono(value) { return value ? '<span class="mono">' + esc(value) + '</span>' : '<span class="dim">—</span>'; }
  function text(value) { return value ? esc(value) : '<span class="dim">—</span>'; }
  function natureTag(nature) {
    if (!nature) return '';
    const kind = NATURE_CN[nature] || 'norm';
    return '<span class="kg-tag kg-tag-' + kind + '">' + esc(nature) + '</span>';
  }
  function kvRow(label, value) {
    return '<div class="kg-kv-k">' + esc(label) + '</div><div class="kg-kv-v">' + value + '</div>';
  }
  function section(title, inner, open) {
    return '<details class="kg-dsec"' + (open ? ' open' : '') + '><summary>' + esc(title) +
      '</summary><div class="kg-dsec-body">' + inner + '</div></details>';
  }
  function chips(list, empty) {
    if (!list || !list.length) return '<span class="dim">' + esc(empty || '—') + '</span>';
    return list.map(function (item) { return '<span class="kg-chip">' + esc(item) + '</span>'; }).join('');
  }

  let modal = null;

  function ensureModal() {
    if (modal) return modal;
    const mask = document.createElement('div');
    mask.className = 'kg-modal-mask';
    mask.hidden = true;
    mask.innerHTML =
      '<div class="kg-modal" role="dialog" aria-modal="true" aria-label="文档详情">' +
        '<div class="kg-modal-head">' +
          '<div class="kg-modal-title"><b>文档详情</b><span id="kg-detail-sub" class="mono dim"></span></div>' +
          '<button type="button" class="kg-modal-close" aria-label="关闭">×</button>' +
        '</div>' +
        '<div class="kg-modal-body" id="kg-detail-body"></div>' +
      '</div>';
    document.body.appendChild(mask);
    mask.addEventListener('click', function (event) { if (event.target === mask) close(); });
    mask.querySelector('.kg-modal-close').addEventListener('click', close);
    document.addEventListener('keydown', function (event) { if (event.key === 'Escape') close(); });
    modal = mask;
    return modal;
  }

  function close() { if (modal) modal.hidden = true; }

  function renderStats(stats) {
    const defs = [
      ['结构节点', stats.nodes], ['章', stats.chapters], ['条款', stats.clauses],
      ['附录', stats.annexes], ['附录条', stats.annex_sections], ['文前/文后块', stats.document_blocks],
      ['内容单元', stats.content_elements], ['术语', stats.terms],
      ['表', stats.tables], ['图', stats.figures], ['公式', stats.formulas]
    ];
    return '<div class="kg-stat-grid">' + defs.map(function (pair) {
      return '<div class="kg-stat"><span class="n">' + esc(pair[1]) + '</span><span class="l">' + esc(pair[0]) + '</span></div>';
    }).join('') + '</div>';
  }

  function renderOrgs(orgs) {
    const units = (orgs.drafting_units || []);
    const drafters = (orgs.drafters || []);
    return '<div class="kg-kv">' +
      kvRow('发布机构', text(orgs.issuer)) +
      kvRow('提出单位', text(orgs.proposing)) +
      kvRow('归口单位', text(orgs.secretariat)) +
      '</div>' +
      '<div class="kg-sub-h">起草单位（' + units.length + '）</div>' +
      '<div class="kg-chips">' + chips(units, '前言未给出或未识别') + '</div>' +
      '<div class="kg-sub-h">主要起草人（' + drafters.length + '）</div>' +
      '<div class="kg-chips">' + chips(drafters, '前言未给出或未识别') + '</div>';
  }

  function renderTerms(docId, terms) {
    if (!terms.count) return '<p class="dim">本文件无「术语和定义」条目。</p>';
    return '<p class="kg-hint">共 <b>' + esc(terms.count) + '</b> 条术语；点击条目展开定义（点击“在结构树中查看”跳转原文）。</p>' +
      terms.items.map(function (term) {
        const label = '<span class="mono kg-term-num">' + esc(term.number || '') + '</span> ' +
          '<b>' + esc(term.term) + '</b>' +
          (term.english ? ' <span class="dim">' + esc(term.english) + '</span>' : '');
        const link = term.node_id
          ? '<a class="kg-mini-link" href="/doc/' + encodeURIComponent(docId) + '?focus=' + encodeURIComponent(term.node_id) + '">在结构树中查看 →</a>'
          : '';
        return '<details class="kg-term"><summary>' + label + '</summary>' +
          '<div class="kg-term-body"><p>' + (term.definition ? esc(term.definition) : '<span class="dim">（无定义文本）</span>') + '</p>' +
          (term.md_line ? '<div class="dim" style="font-size:12px">canonical.md 第 ' + esc(term.md_line) + ' 行</div>' : '') +
          link + '</div></details>';
      }).join('');
  }

  function renderElements(docId, elements) {
    const groups = elements.groups || [];
    const total = (elements.items || []).length;
    let html = '<p class="kg-hint">共 <b>' + esc(total) + '</b> 个顶层要素；点击条目展开详情，或跳转结构树。</p>';
    groups.forEach(function (group) {
      if (!group.items.length) return;
      const rows = group.items.map(function (item) {
        const title = (item.number ? '<span class="mono">' + esc(item.number) + '</span> ' : '') +
          esc(item.name || item.title || '');
        const kind = KIND_CN[item.node_type] || item.node_type || '';
        const link = item.node_id
          ? '<a class="kg-mini-link" href="/doc/' + encodeURIComponent(docId) + '?focus=' + encodeURIComponent(item.node_id) + '">结构树 →</a>'
          : '';
        return '<details class="kg-elem"><summary>' +
          '<span class="kg-tag kg-tag-code">' + esc(item.code) + '</span>' +
          title + ' ' + natureTag(item.nature) +
          '</summary><div class="kg-elem-body kg-kv">' +
          kvRow('节点类型', text(kind)) +
          kvRow('直接子节点', esc(item.child_count)) +
          kvRow('内容单元', esc(item.ce_count)) +
          (item.md_line ? kvRow('canonical 行', esc(item.md_line)) : '') +
          kvRow('在结构树中查看', link || '<span class="dim">—</span>') +
          '</div></details>';
      }).join('');
      html += section(group.label + '（' + group.items.length + '）', rows, true);
    });
    return html;
  }

  function renderCoverage(coverage) {
    function list(rows, label) {
      const present = rows.filter(function (r) { return r.present; }).length;
      const body = rows.map(function (row) {
        const badge = row.present
          ? '<span class="kg-ok">✓</span>'
          : '<span class="kg-miss">✗</span>';
        return '<tr class="' + (row.present ? '' : 'miss') + '"><td>' + badge + '</td>' +
          '<td class="mono">' + esc(row.code) + '</td><td>' + esc(row.name) + '</td>' +
          '<td>' + natureTag(row.nature) + '</td><td class="dim">' + esc(row.note || '') + '</td></tr>';
      }).join('');
      return section(label + '：命中 ' + present + '/' + rows.length,
        '<table class="kg-cover-table"><thead><tr><th></th><th>代码</th><th>名称</th><th>性质</th><th>说明</th></tr></thead>' +
        '<tbody>' + body + '</tbody></table>', true);
    }
    return list(coverage.elements || [], '文档结构要素（GBT-E01~E14）') +
      list(coverage.metadata || [], '文档元数据（GBT-M01~M14）');
  }

  function render(body, detail) {
    const id = detail.identity || {};
    const dates = detail.dates || {};
    const rel = detail.relations || {};
    const html = [];
    html.push('<h2 class="kg-detail-h1">' + esc(id.chinese_title || detail.doc_id) + '</h2>');
    html.push('<div class="kg-detail-sub mono">' + esc(id.standard_number || '') + '</div>');
    html.push(section('① 基本信息',
      '<div class="kg-kv">' +
        kvRow('标准号', mono(id.standard_number)) +
        kvRow('中文名称', text(id.chinese_title)) +
        kvRow('英文译名', text(id.title_en)) +
        kvRow('文档类型', text(id.document_type)) +
        kvRow('ICS', mono(id.ics)) +
        kvRow('CCS', mono(id.ccs)) +
        kvRow('语言', text(id.language)) +
      '</div>', true));
    html.push(section('② 日期与关系',
      '<div class="kg-kv">' +
        kvRow('发布日期', text(dates.publication_date)) +
        kvRow('实施日期', text(dates.effective_date)) +
        kvRow('代替标准', mono(rel.replaces)) +
        kvRow('一致性程度标识', text(rel.conformity_statement)) +
      '</div>', true));
    html.push(section('③ 组织机构', renderOrgs(detail.organizations || {}), true));
    html.push(section('④ 术语和定义（' + ((detail.terms || {}).count || 0) + '）',
      renderTerms(detail.doc_id, detail.terms || { count: 0, items: [] }), true));
    html.push(section('⑤ 标准要素', renderElements(detail.doc_id, detail.elements || { groups: [], items: [] }), true));
    html.push(section('⑥ 清单核对', renderCoverage(detail.coverage || {}), false));
    html.push(section('⑦ 规模统计', renderStats(detail.stats || {}), false));
    body.innerHTML = html.join('');
  }

  async function openDocDetail(docId) {
    const mask = ensureModal();
    const body = mask.querySelector('#kg-detail-body');
    mask.querySelector('#kg-detail-sub').textContent = docId;
    body.innerHTML = '<p class="dim">加载中…</p>';
    mask.hidden = false;
    try {
      const response = await fetch('/api/doc/' + encodeURIComponent(docId) + '/detail');
      if (!response.ok) throw new Error('HTTP ' + response.status);
      render(body, await response.json());
    } catch (error) {
      body.innerHTML = '<p class="kg-err">详情加载失败：' + esc(error.message) + '</p>';
    }
  }

  window.openDocDetail = openDocDetail;
  window.closeDocDetail = close;
})();
