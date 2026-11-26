export const meta = {
  name: 'odoo-parallel-review',
  description: 'Parallel Odoo review of the current branch diff: code quality, security/access control, and database/migration impact, merged into one ranked report',
}

// args (optional): { base: "main" }
const base = (args && args.base) || 'HEAD~1'

const scope = await agent(
  `List the files changed between ${base} and HEAD in this git repository (git diff --name-only ${base}...HEAD), ` +
  `and the Odoo modules they belong to (nearest parent folder containing __manifest__.py). ` +
  `Also run \`odoo-master detect-version --brief\` (or \${CLAUDE_PLUGIN_ROOT}/bin/odoo-master) and report the Odoo version.`,
  {
    label: 'scope',
    schema: {
      type: 'object', required: ['files', 'modules', 'odoo_version'],
      properties: { files: { type: 'array', items: { type: 'string' } }, modules: { type: 'array', items: { type: 'string' } }, odoo_version: { type: 'string' } },
    },
  },
)

const finding = {
  type: 'object', required: ['verdict', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['PASS', 'FAIL'] },
    findings: { type: 'array', items: { type: 'object', required: ['severity', 'location', 'problem', 'fix'],
      properties: { severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'nit'] }, location: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } } } },
  },
}

const lenses = [
  { label: 'quality', role: 'senior Odoo code reviewer', focus: 'correctness, version-correct APIs for Odoo ' + scope.odoo_version + ', super() in overrides, @api.depends completeness, batching (no queries in loops), meaningful tests' },
  { label: 'security', role: 'Odoo security specialist', focus: 'ACLs for new models (ir.model.access or ir.access on 20.0), record rules and multi-company, sudo scope, controller auth/csrf, SQL injection, eval, secrets' },
  { label: 'database', role: 'Odoo database reviewer', focus: 'stored field adds/renames/removals and their upgrade scripts (migrations/<version>/pre-|post-), manifest version bumps, constraints declared the version-correct way, indexes, heavy recomputes' },
]

const reviews = await pipeline(lenses, (l) =>
  agent(
    `You are a ${l.role}. Review ONLY these changed files (diff ${base}...HEAD): ${scope.files.join(', ')}. ` +
    `Odoo modules: ${scope.modules.join(', ')}. Focus: ${l.focus}. Read surrounding code, not just the diff. ` +
    `Run \`odoo-master validate --files <changed files> --brief\` and use its findings. Every finding needs path:line and a concrete fix. Read-only: do not edit files.`,
    { label: l.label, schema: finding },
  ),
)

const merged = reviews.filter(Boolean).flatMap((r, i) => r.findings.map((f) => ({ lens: lenses[i].label, ...f })))
const order = { blocker: 0, major: 1, minor: 2, nit: 3 }
merged.sort((a, b) => order[a.severity] - order[b.severity])
log(`${merged.length} findings from ${reviews.filter(Boolean).length}/${lenses.length} reviewers`)
return {
  odoo_version: scope.odoo_version,
  verdicts: Object.fromEntries(reviews.map((r, i) => [lenses[i].label, r ? r.verdict : 'NOT_RUN'])),
  findings: merged,
}
