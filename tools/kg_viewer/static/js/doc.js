/* kg_viewer 文档浏览页逻辑：结构树（资源管理器风格）+ 内容渲染 + 原文行 + focus 深链 */
(function () {
  const treeEl = document.getElementById('kg-tree');
  const contentEl = document.getElementById('content');
  const breadEl = document.getElementById('breadcrumb');
  const rawbox = document.getElementById('rawbox');
  const rawClose = document.getElementById('raw-close');
  const rawLines = document.getElementById('raw-lines');
  let rowsById = {};   // id -> row
  let childrenOf = {}; // parentId(或 'ROOT') -> [row...]
  let selRow = null;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function nodeLabel(r) {
    let s = '';
    if (r.number != null && r.number !== '') s += '<span class="tnum">' + esc(r.number) + '</span>';
    if (r.term) s += esc(r.term);
    else if (r.title) s += esc(r.title);
    else s += '<span class="dim">(' + esc(r.node_type) + ')</span>';
    return s;
  }
  function typeTag(r) {
    const map = { section: '章', clause: '条', subClause: '条', annex: '附', documentBlock: '块',
      item: '列', subItem: '列', document: '文' };
    return '<span class="tt">' + (map[r.node_type] || r.node_type) + '</span>';
  }

  async function fetchStructure() {
    const res = await fetch('/api/structure/' + DOC_ID);
    const data = await res.json();
    rowsById = {};
    childrenOf = {};
    for (const r of data.rows) {
      rowsById[r.id] = r;
      const p = r.parent_id || 'ROOT';
      (childrenOf[p] = childrenOf[p] || []).push(r);
    }
    document.getElementById('tree-loading').textContent = '';
  }

  // ---------- 树：展开/折叠原语 ----------
  function rowKids(r) {
    return childrenOf[r.id] || [];
  }
  function childUl(li) {
    return li.querySelector(':scope > ul');
  }
  function isRowOpen(li) {
    const ul = childUl(li);
    return !!(ul && !ul.hidden);
  }
  function setArrow(li, open) {
    const tw = li.querySelector(':scope > .tw');
    if (tw) tw.textContent = open ? '▾' : '▸';
  }

  function makeUl(parentId) {
    const ul = document.createElement('ul');
    for (const k of childrenOf[parentId] || []) ul.appendChild(buildLi(k));
    ul.hidden = true; // 默认折叠
    return ul;
  }
  // 惰性建子层：首次访问生成，之后复用
  function ensureChildren(li, parentId) {
    if (li.dataset.loaded === '1') return childUl(li) || li.appendChild(makeUl(parentId));
    const ul = makeUl(parentId);
    li.appendChild(ul);
    li.dataset.loaded = '1';
    return ul;
  }
  function expandRow(li, r) {
    if (!rowKids(r).length) return false;
    const ul = ensureChildren(li, r.id);
    ul.hidden = false;
    setArrow(li, true);
    return true;
  }
  function collapseRow(li) {
    const ul = childUl(li);
    if (ul) ul.hidden = true;
    setArrow(li, false);
  }
  function toggleRow(li, r) {
    if (!rowKids(r).length) return;
    if (isRowOpen(li)) collapseRow(li);
    else expandRow(li, r);
  }

  function buildLi(r) {
    const li = document.createElement('li');
    li.dataset.id = r.id;
    li._row = r;
    const kids = rowKids(r).length;
    const row = document.createElement('span');
    row.className = 'row';
    const tw = document.createElement('span');
    tw.className = 'tw';
    tw.textContent = kids ? '▸' : '';  // 叶子无箭头（资源管理器风格）
    tw.title = kids ? '展开/折叠' : '';
    const tn = document.createElement('span');
    tn.className = 'tn';
    tn.innerHTML = typeTag(r) + nodeLabel(r) + (kids ? '<span class="cnt">' + kids + '</span>' : '');
    row.appendChild(tw);
    row.appendChild(tn);
    li.appendChild(row);
    // 单击行 = 选择 +（有子层且折叠时）展开（Windows 资源管理器：点文件夹=导航并展开）
    row.addEventListener('click', (e) => {
      if (e.target.classList && e.target.classList.contains('tw')) return;
      onLabelClick(r, li);
    });
    // 箭头仅切换展开/折叠，不改变选择
    tw.addEventListener('click', (e) => {
      e.stopPropagation();
      if (kids) toggleRow(li, r);
    });
    return li;
  }

  function onLabelClick(r, li) {
    select(r, li);
    if (rowKids(r).length && !isRowOpen(li)) expandRow(li, r);
  }

  // ---------- 定位/选择 ----------
  function findLiById(id) {
    const list = treeEl.querySelectorAll('li');
    for (const li of list) if (li.dataset.id === id) return li;
    return null;
  }
  // 展开 root→row 的祖先路径（row 的子层保持原状），返回 row 的 li
  function reveal(row) {
    if (!row) return null;
    const chain = [];
    let cur = row;
    const guard = new Set();
    while (cur) {
      if (guard.has(cur.id)) return null;
      guard.add(cur.id);
      chain.unshift(cur);
      cur = cur.parent_id ? rowsById[cur.parent_id] : null;
    }
    if (!chain.length || chain[0].id !== (treeEl._rootRow && treeEl._rootRow.id)) return null;
    let curLi = treeEl._rootLi;
    for (let i = 1; i < chain.length; i++) {
      const r = chain[i];
      let found = null;
      if (curLi) {
        const uls = curLi.querySelectorAll(':scope > ul > li');
        for (const li of uls) if (li.dataset.id === r.id) { found = li; break; }
      }
      if (!found) {
        const parentRow = chain[i - 1];
        if (!curLi || !parentRow) return null;
        const ul = ensureChildren(curLi, parentRow.id);
        ul.hidden = false;
        setArrow(curLi, true);
        for (const li of ul.querySelectorAll(':scope > li')) {
          if (li.dataset.id === r.id) { found = li; break; }
        }
      }
      if (!found) return null;
      if (i < chain.length - 1) expandRow(found, r); // 祖先展开到可见
      curLi = found;
    }
    return curLi;
  }

  function highlight(row, li) {
    treeEl.querySelectorAll('li.sel').forEach(el => el.classList.remove('sel'));
    if (li) {
      li.classList.add('sel');
      li.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    selRow = row;
  }

  async function select(r, li) {
    highlight(r, li || findLiById(r.id));
    showRaw(false);
    const res = await fetch('/api/node/' + DOC_ID + '/' + encodeURIComponent(r.id));
    if (!res.ok) {
      contentEl.innerHTML = '<p class="kg-err">加载失败（' + res.status + '）</p>';
      return;
    }
    const data = await res.json();
    breadEl.innerHTML = (data.chain || []).map((c, i) => {
      const label = c.number != null && c.number !== '' ? c.number
        : (c.term || c.title || c.node_type);
      return '<a href="javascript:void(0)" data-bid="' + esc(c.id) + '">' + esc(label) + '</a>'
        + (i < data.chain.length - 1 ? '<span class="sep">/</span>' : '');
    }).join('');
    breadEl.querySelectorAll('a[data-bid]').forEach(a => {
      a.onclick = () => {
        const row = rowsById[a.dataset.bid];
        if (!row) return;
        const li = reveal(row); // 面包屑跳转同样展开祖先路径
        select(row, li);
      };
    });
    const nd = data.node;
    let title = '';
    if (nd.node_type === 'document') {
      title = '<h2 class="kg-node-title">' + esc(data.doc_title || nd.id) + '</h2>';
    } else {
      const t = nd.term || nd.title || '';
      title = '<h2 class="kg-node-title">'
        + (nd.number != null && nd.number !== '' ? esc(nd.number) + '　' : '')
        + esc(t) + '</h2>';
      if (nd.term && nd.english_term) {
        title += '<p class="dim"><span class="mono">' + esc(nd.english_term) + '</span></p>';
      }
    }
    let anchorBtn = '';
    if (data.row && data.row.md_start_line) {
      anchorBtn = '<p class="kg-anchor"><a href="javascript:void(0)" id="btn-raw">📄 查看原文行 '
        + 'canonical.md L' + data.row.md_start_line + '</a>'
        + (nd.child_count ? ' · 含子节点 ' + nd.child_count + ' 个（可在左侧树展开）' : '') + '</p>';
    }
    contentEl.innerHTML = title + anchorBtn + data.html;
    const btnRaw = document.getElementById('btn-raw');
    if (btnRaw) {
      btnRaw.onclick = async () => {
        const s = Math.max(1, data.row.md_start_line - 2);
        const e = data.row.md_start_line + 6;
        const rres = await fetch('/api/raw/' + DOC_ID + '/' + s + '/' + e);
        const rdata = await rres.json();
        rawLines.innerHTML = (rdata.lines || []).map(l =>
          '<div><span class="ln">' + l.line + '</span>' + esc(l.text) + '</div>').join('');
        rawbox.hidden = false;
        rawbox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      };
    }
    contentEl.scrollTop = 0;
  }

  function showRaw(open) {
    rawbox.hidden = !open; // true=显示, false=隐藏
  }

  // 关闭原文行块：× 按钮 / Esc / 再点任意树节点（select 内 showRaw(false)）
  if (rawClose) {
    rawClose.addEventListener('click', () => { showRaw(false); });
  }
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !rawbox.hidden) showRaw(false);
  });

  window.addEventListener('DOMContentLoaded', async () => {
    await fetchStructure();
    const root = childrenOf['ROOT'][0]; // 结构根（…/document）
    if (!root) return;
    treeEl._rootRow = root;
    const rli = buildLi(root);
    treeEl._rootLi = rli;
    treeEl.appendChild(rli);
    expandRow(rli, root); // 根默认展开
    if (FOCUS_ID) {
      const row = rowsById[FOCUS_ID];
      const li = row ? reveal(row) : null;
      if (li) select(row, li);
      else select(root, rli);
    } else {
      select(root, rli);
    }
  });
})();
