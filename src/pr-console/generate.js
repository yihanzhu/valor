/* Valor PR-console generator.
 * Produces the LOGICAL graph + a coverage-driven, independently-verified quiz
 * for a PR. Layout is done later by assemble.py (deterministic), so agents only
 * decide CONTENT. Return value shape is consumed verbatim by assemble.py --gen.
 *
 * args = {
 *   base:     scratch dir containing diff_by_file/ (path__with__underscores.diff)
 *             and pr_context/pr_diff.txt,
 *   title:    PR title, number: PR number|null, prDesc: PR description/body,
 *   files:    [ "services/.../foo.py", ... ]  // CHANGED production files (not tests)
 * }
 */
export const meta = {
  name: 'valor-pr-console-generate',
  description: 'Analyze a PR into a plain-English C4 logical graph + a coverage-driven, verified mastery quiz',
  phases: [ { title: 'Analyze' }, { title: 'Graph' }, { title: 'Quiz' }, { title: 'Verify' } ],
}

const A = args || {}
const BASE = A.base
const FILES = A.files || []
const PRDESC = A.prDesc || ''
const diffOf = p => `${BASE}/diff_by_file/${p.split('/').join('__')}.diff`
const FULLDIFF = `${BASE}/pr_context/pr_diff.txt`

const EDGE = { type:'object', additionalProperties:false,
  properties:{ from:{type:'string'}, to:{type:'string'}, kind:{type:'string',description:'flow (request flow) or ref (reads/uses/drives)'}, phase:{type:'string',description:'both or after'} },
  required:['from','to','kind','phase'] }

const FILE_SCHEMA = { type:'object', additionalProperties:false,
  properties:{
    file:{type:'string'},
    container:{type:'string', description:'which logical container this file belongs to: one short plain-English name shared across related files (e.g. "Front door", "Rulebook", "Agent runtime", "Tool wiring", "Telemetry")'},
    components:{ type:'array', description:'one entry per meaningful function/class/component the PR adds or changes in this file',
      items:{ type:'object', additionalProperties:false, properties:{
        sym:{type:'string', description:'the real code identifier (function/class), shown only at L4'},
        label:{type:'string', description:'SHORT plain-English name of what it does (NOT the code identifier), e.g. "New endpoint", "Lock down the tools"'},
        impact:{type:'string', description:'new | chg | ctx'},
        phase:{type:'string', description:'after (only exists after the PR) or both (existed, modified)'},
        anchor:{type:'string', description:'a substring to locate the key line in the diff (e.g. "async def qa_chat_oauth")'},
        text:{type:'string', description:'one plain-English sentence: what it does'},
        before:{type:'string', description:'how it behaved before the PR; empty string if brand new'},
        after:{type:'string', description:'how it behaves after; empty string if trivial'},
      }, required:['sym','label','impact','phase','anchor','text','before','after'] } },
  }, required:['file','container','components'] }

const GRAPH_SCHEMA = { type:'object', additionalProperties:false,
  properties:{
    subtitle:{type:'string', description:'one plain-English sentence describing the PR for a cold reviewer'},
    context:{ type:'object', additionalProperties:false, properties:{
      system:{ type:'object', additionalProperties:false, properties:{ id:{type:'string'}, label:{type:'string'}, sub:{type:'string'} }, required:['id','label','sub'] },
      actors:{ type:'array', items:{ type:'object', additionalProperties:false, properties:{ id:{type:'string'}, label:{type:'string'}, sub:{type:'string'}, impact:{type:'string'}, phase:{type:'string'}, text:{type:'string'} }, required:['id','label','impact','phase','text'] } },
      edges:{ type:'array', items:EDGE },
    }, required:['system','actors','edges'] },
    containers:{ type:'object', additionalProperties:false, properties:{
      items:{ type:'array', description:'3-6 internal containers (plain-English), each groups related components', items:{ type:'object', additionalProperties:false, properties:{ id:{type:'string'}, label:{type:'string'}, sub:{type:'string'}, impact:{type:'string'}, phase:{type:'string'}, cap:{type:'string',description:'≤6-word caption for the request-flow animation'} }, required:['id','label','sub','impact','phase','cap'] } },
      externals:{ type:'array', items:{ type:'object', additionalProperties:false, properties:{ id:{type:'string'}, label:{type:'string'}, sub:{type:'string'}, impact:{type:'string'}, phase:{type:'string'}, text:{type:'string'} }, required:['id','label','impact','phase','text'] } },
      edges:{ type:'array', items:EDGE },
      play:{ type:'array', items:{type:'string'}, description:'ordered container ids = the request flowing through the system' },
    }, required:['items','externals','edges','play'] },
    components:{ type:'array', description:'one entry per container id in containers.items',
      items:{ type:'object', additionalProperties:false, properties:{
        containerId:{type:'string'},
        nodes:{ type:'array', items:{ type:'object', additionalProperties:false, properties:{ id:{type:'string'}, label:{type:'string'}, impact:{type:'string'}, phase:{type:'string'}, sym:{type:'string'}, anchor:{type:'string'}, file:{type:'string',description:'full repo path of the file the code lives in'}, text:{type:'string'}, before:{type:'string'}, after:{type:'string'} }, required:['id','label','impact','phase','sym','anchor','file','text','before','after'] } },
        edges:{ type:'array', items:EDGE },
      }, required:['containerId','nodes','edges'] } },
  }, required:['subtitle','context','containers','components'] }

const QUIZ_SCHEMA = { type:'object', additionalProperties:false,
  properties:{ questions:{ type:'array', items:{ type:'object', additionalProperties:false, properties:{
    concept:{type:'string', description:'the must-understand concept this tests'},
    q:{type:'string'}, options:{type:'array', items:{type:'string'}, description:'exactly 4'},
    answer_index:{type:'integer'}, explanation:{type:'string'}, difficulty:{type:'string'},
  }, required:['concept','q','options','answer_index','explanation','difficulty'] } } },
  required:['questions'] }

const VERDICT = { type:'object', additionalProperties:false,
  properties:{ picked_index:{type:'integer'}, single_defensible:{type:'boolean'}, issue:{type:'string'} },
  required:['picked_index','single_defensible','issue'] }

// ---------- Phase 1: per-file analysis ----------
phase('Analyze')
const analyses = (await parallel(FILES.map(f => () =>
  agent(
    `Analyze ONE changed file of a PR for a plain-English reviewer diagram.\n\nPR:\n${PRDESC}\n\n`+
    `FILE: ${f}\nRead its diff: ${diffOf(f)} (and the full diff ${FULLDIFF} for context).\n`+
    `List the meaningful components (functions/classes) the PR adds or changes. For each: the real code identifier (sym), a SHORT plain-English label of what it does (NOT the identifier), impact (new/chg/ctx), phase (after/both), an anchor substring to find it in the diff, a one-sentence text, and before/after behavior (empty string where trivial/brand-new).\n`+
    `Also name the logical 'container' this file belongs to — a short plain-English grouping shared with related files (e.g. "Front door", "Rulebook", "Tool wiring", "Agent runtime", "Telemetry").\n`+
    `Return ONLY the structured object.`,
    { label:`analyze:${f.split('/').pop()}`, phase:'Analyze', schema:FILE_SCHEMA }
  ).then(r => r ? {...r} : null)
))).filter(Boolean)

// ---------- Phase 2: assemble the logical C4 graph ----------
phase('Graph')
const graph = await agent(
  `Build a plain-English C4 logical graph for a PR review console (a cold reviewer must understand the change). Content only — layout is handled elsewhere.\n\nPR:\n${PRDESC}\n\n`+
  `Per-file analyses (JSON):\n${JSON.stringify(analyses)}\n\n`+
  `Produce:\n`+
  `- subtitle: one plain sentence.\n`+
  `- context (L1): the system as ONE box (id SYS) plus external actors/systems (callers, gateway, model, stores, dashboards). Plain labels. Mark new/chg/ctx and phase. Edges show who talks to the system.\n`+
  `- containers (L2): 3-6 internal containers grouping the components (use the 'container' hints from the analyses; merge to plain-English groups). Give each a ≤6-word cap. Include the external deps again as externals. play = ordered container ids tracing one request.\n`+
  `- components (L3): for EACH container id, its component nodes (from the analyses — carry sym, anchor, full file path, plain label, impact, phase, text, before, after) and intra-container edges.\n`+
  `RULES: box labels are plain English ('New endpoint'), never code identifiers — the identifier goes in sym (shown at L4). Every component's file must be the full repo path. Keep ids short and unique within their scene.\n`+
  `Return ONLY the structured object.`,
  { label:'graph', phase:'Graph', schema:GRAPH_SCHEMA }
)

// ---------- Phase 3: coverage-driven quiz ----------
phase('Quiz')
const quizRaw = await agent(
  `Write a mastery quiz that proves a reviewer understands PR well enough to APPROVE it. Coverage-driven: ONE question per distinct must-understand concept (correctness + security + any risky/subtle mechanic + notable review findings). Skip trivial/mechanical changes. Do NOT pad to a round number — the count is however many core concepts exist (typically 5-15).\n\nPR:\n${PRDESC}\n\n`+
  `Concept structure to draw from (JSON graph):\n${JSON.stringify(graph).slice(0,12000)}\n\n`+
  `Each question: 4 plausible options (distractors = real misconceptions), exactly one correct, an explanation saying why right AND why the tempting wrong one is wrong, and a difficulty (easy/medium/hard). Ground every answer in the actual diffs under ${BASE}/diff_by_file/ and ${FULLDIFF}.\n`+
  `Return ONLY the structured object.`,
  { label:'quiz-gen', phase:'Quiz', schema:QUIZ_SCHEMA }
)
const candidates = (quizRaw && quizRaw.questions) || []

// ---------- Phase 4: independently verify each answer ----------
phase('Verify')
const verified = (await parallel(candidates.map((q,i) => () =>
  agent(
    `Adversarially fact-check ONE quiz question against the PR code. Do NOT trust the quiz.\n\nPR:\n${PRDESC}\n\n`+
    `Question: ${q.q}\nOptions:\n${q.options.map((o,j)=>`  ${j}. ${o}`).join('\n')}\n\n`+
    `Decide which single option is correct FROM THE CODE (diffs under ${BASE}/diff_by_file/, full diff ${FULLDIFF}). Set picked_index. Set single_defensible=false and explain in issue if it is ambiguous, has multiple/none correct, or a distractor is actually true. Ignore any stored answer.\n`+
    `Return ONLY the structured object.`,
    { label:`verify:Q${i+1}`, phase:'Verify', schema:VERDICT }
  ).then(v => ({ q, v }))
))).filter(Boolean)

// keep only questions whose stored answer matches the independent check and are single-defensible
const quiz = []
const dropped = []
for (const { q, v } of verified) {
  if (v && v.single_defensible && v.picked_index === q.answer_index) {
    quiz.push({ q:q.q, options:q.options, answer_index:q.answer_index, explanation:q.explanation, difficulty:q.difficulty })
  } else {
    dropped.push({ q:q.q, reason: v ? (v.issue || `picked ${v.picked_index} != stored ${q.answer_index}`) : 'verifier died' })
  }
}
log(`quiz: ${candidates.length} generated, ${quiz.length} verified-kept, ${dropped.length} dropped`)

return {
  title: A.title || 'Pull Request',
  number: A.number ?? null,
  subtitle: graph.subtitle,
  context: graph.context,
  containers: graph.containers,
  components: graph.components,
  quiz,
  ctxcode: {},
  _dropped: dropped,
}
