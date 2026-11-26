const h = async (u, m = 'GET', b) => {
  const r = await fetch(u, {
    method: m,
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
    },
    body: b ? JSON.stringify(b) : undefined,
  });
  const d = await r.json();
  if (!r.ok) throw Error(d.error || 'Action failed');
  return d;
};

function fmtDate(iso) {
  if (!iso) return 'Never';
  const dt = new Date(iso);
  return isNaN(dt.getTime()) ? iso : dt.toLocaleString();
}

function esc(s) {
  const el = document.createElement('span');
  el.textContent = s ?? '';
  return el.innerHTML;
}

async function loadAdmin() {
  try {
    const d = await h('/api/admin');
    document.getElementById('adminStats').innerHTML = [
      ['Registered users', d.users, 'bi-people', 'lavender'],
      ['People logged in', d.logged_in_users, 'bi-box-arrow-in-right', 'mint'],
      ['Total logins', d.total_logins, 'bi-activity', 'blue-bg'],
      ['Skills added by users', d.total_user_skills, 'bi-stars', 'peach'],
      ['Teaching / Learning', `${d.teach_skills_count} / ${d.learn_skills_count}`, 'bi-arrow-left-right', 'lavender'],
      ['Catalog skills', d.skills, 'bi-collection', 'blue-bg'],
      ['Exchanges (Requests)', `${d.exchanges} (${d.requests})`, 'bi-chat-dots', 'mint'],
      ['Open reports', d.reports, 'bi-flag', 'peach'],
    ]
      .map(
        ([label, val, icon, tone]) =>
          `<div class="col-6 col-md-3"><div class="stat-card"><span class="stat-icon ${tone}"><i class="bi ${icon}"></i></span><div><b>${esc(String(val))}</b><small>${esc(label)}</small></div></div></div>`
      )
      .join('');

    document.getElementById('userList').innerHTML = d.user_list.length
      ? `<table class="table align-middle"><thead><tr><th>User</th><th>College</th><th>Logins</th><th>Last login</th><th>Skills added</th><th>Status</th><th></th></tr></thead><tbody>${d.user_list
          .map((u) => {
            const teachTags = (u.teach_skills || [])
              .map((s) => `<span class="skill-tag">Teach: ${esc(s.name)} (${s.proficiency})</span>`)
              .join(' ');
            const learnTags = (u.learn_skills || [])
              .map((s) => `<span class="skill-tag learn">Learn: ${esc(s.name)} (${s.proficiency})</span>`)
              .join(' ');
            const roleBadge = u.is_admin ? '<span class="count-badge ms-1">Admin</span>' : '';
            return `<tr>
              <td><b>${esc(u.name)}</b>${roleBadge}<div class="small text-secondary">${esc(u.email)}</div></td>
              <td class="small">${esc(u.college)}<div class="text-secondary">${esc(u.department)}</div></td>
              <td><b>${u.login_count}</b></td>
              <td class="small text-secondary">${esc(fmtDate(u.last_login_at))}</td>
              <td><div class="small fw-semibold mb-1">${u.skills_count} total</div><div>${teachTags} ${learnTags || (!teachTags ? '<span class="text-secondary small">None yet</span>' : '')}</div></td>
              <td>${u.active ? '<span class="badge bg-success-subtle text-success">Active</span>' : '<span class="badge bg-secondary-subtle text-secondary">Disabled</span>'}</td>
              <td>${u.is_admin ? '' : `<button class="btn btn-sm btn-outline-secondary" data-user="${u.id}">${u.active ? 'Disable' : 'Enable'}</button>`}</td>
            </tr>`;
          })
          .join('')}</tbody></table>`
      : '<p class="text-secondary">No users registered yet.</p>';

    document.getElementById('loginList').innerHTML = d.recent_logins.length
      ? `<table class="table table-sm align-middle"><thead><tr><th>User</th><th>Role</th><th>Signed in at</th></tr></thead><tbody>${d.recent_logins
          .map(
            (ev) =>
              `<tr><td><b>${esc(ev.user_name)}</b><div class="small text-secondary">${esc(ev.email)}</div></td><td>${ev.is_admin ? 'Admin' : 'Student'}</td><td class="small text-secondary">${esc(fmtDate(ev.logged_in_at))}</td></tr>`
          )
          .join('')}</tbody></table>`
      : '<p class="text-secondary mb-0">No logins recorded yet.</p>';

    document.getElementById('skillList').innerHTML = d.skill_list.length
      ? `<table class="table table-sm align-middle"><thead><tr><th>Skill</th><th>Category</th><th>Teach</th><th>Learn</th><th></th></tr></thead><tbody>${d.skill_list
          .map(
            (s) =>
              `<tr><td><b>${esc(s.name)}</b></td><td class="small text-secondary">${esc(s.category)}</td><td>${s.teach_count}</td><td>${s.learn_count}</td><td class="text-end"><button class="icon-btn" data-skill="${s.id}" title="Remove unused skill"><i class="bi bi-trash"></i></button></td></tr>`
          )
          .join('')}</tbody></table>`
      : '<p class="text-secondary mb-0">No skills yet.</p>';

    document.getElementById('reportList').innerHTML = d.report_list.length
      ? `<table class="table align-middle"><thead><tr><th>From</th><th>About</th><th>Reason</th><th>Status</th><th></th></tr></thead><tbody>${d.report_list
          .map(
            (r) =>
              `<tr><td>${esc(r.reporter)}</td><td>${esc(r.reported)}</td><td>${esc(r.reason)}</td><td>${esc(r.status)}</td><td>${r.status === 'open' ? `<button class="btn btn-sm btn-primary" data-report="${r.id}">Resolve</button>` : ''}</td></tr>`
          )
          .join('')}</tbody></table>`
      : '<p class="text-secondary mb-0">No community reports.</p>';

    document.querySelectorAll('[data-user]').forEach(
      (b) =>
        (b.onclick = async () => {
          await h(`/api/admin/users/${b.dataset.user}/toggle`, 'POST', {});
          loadAdmin();
        })
    );
    document.querySelectorAll('[data-skill]').forEach(
      (b) =>
        (b.onclick = async () => {
          try {
            await h(`/api/admin/skills/${b.dataset.skill}`, 'DELETE');
            loadAdmin();
          } catch (e) {
            alert(e.message);
          }
        })
    );
    document.querySelectorAll('[data-report]').forEach(
      (b) =>
        (b.onclick = async () => {
          await h(`/api/admin/reports/${b.dataset.report}/resolve`, 'POST', {});
          loadAdmin();
        })
    );
  } catch (e) {
    alert(e.message);
  }
}

loadAdmin();
