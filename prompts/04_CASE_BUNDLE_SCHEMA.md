# Case bundle: the JSON that `GET /api/cases/{id}` returns

The front end draws every screen from this one object. It was generated from the 19 states recorded on the original backend (`reference/recorded_backend_states.json`, key `states.<name>.bundle`). A key marked `null` in some states and a value in others is optional or only set from a given step onward. Where a field says "array", the element fields follow with `[]` in the path. Example values are from Sample 1. Field order does not matter.

| Path | Type | Example |
|---|---|---|
| `bundle` | object |  |
| `bundle.calcs` | array |  |
| `bundle.calcs[]` | object |  |
| `bundle.calcs[].case_id` | int | 1 |
| `bundle.calcs[].evidence_ids` | array |  |
| `bundle.calcs[].evidence_ids[]` | string | E7 |
| `bundle.calcs[].formula_text` | string | (10.8 ÷ 5.53)^(1/5) − 1 = 14.3% |
| `bundle.calcs[].id` | int | 1 |
| `bundle.calcs[].inputs_json` | object |  |
| `bundle.calcs[].inputs_json.a` | number | 5.53 |
| `bundle.calcs[].inputs_json.a_unit` | string | crore cards |
| `bundle.calcs[].inputs_json.b` | number | 10.8 |
| `bundle.calcs[].inputs_json.b_unit` | string | crore cards |
| `bundle.calcs[].inputs_json.op` | string | cagr |
| `bundle.calcs[].inputs_json.years` | null/number | 5.0 |
| `bundle.calcs[].kind` | string | derivation |
| `bundle.calcs[].result_value` | number | 14.324609027821644 |
| `bundle.calcs[].run_at` | string | 2026-10-05T09:47:16+00:00 |
| `bundle.calcs[].unit` | string | % a year |
| `bundle.case` | object |  |
| `bundle.case.client_aliases` | array |  |
| `bundle.case.client_aliases[]` | string | Example Client |
| `bundle.case.client_name` | string | Example Client Ltd |
| `bundle.case.country` | string | India |
| `bundle.case.created_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.case.current_step` | int | 1 |
| `bundle.case.function` | string | Growth strategy |
| `bundle.case.id` | int | 1 |
| `bundle.case.industry` | string | Consumer lending |
| `bundle.case.mode` | string | fixtures |
| `bundle.case.private_numbers` | array |  |
| `bundle.case.private_numbers[]` | string | Rs 1,500 crore launch budget |
| `bundle.case.raw_ask` | string | Example Client Ltd wants to launch a credit card in India. They believ |
| `bundle.case.sample` | string | sample_01_card_launch |
| `bundle.case.settings_json` | object |  |
| `bundle.case.settings_json.ai_reads_client_files` | bool | True |
| `bundle.case.settings_json.clean_finished_at` | string | 2026-10-05T09:47:16+00:00 |
| `bundle.case.settings_json.collect_finished_at` | string | 2026-10-05T09:47:16+00:00 |
| `bundle.case.settings_json.collect_stopped` | bool | False |
| `bundle.case.settings_json.links_locked_at` | string | 2026-10-05T09:47:17+00:00 |
| `bundle.case.settings_json.plan_ready_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.case.settings_json.requests` | object |  |
| `bundle.case.settings_json.requests.client` | string | What we already have from you - board_note.txt (line 3): The client's  |
| `bundle.case.settings_json.requests.client_gaps` | int | 1 |
| `bundle.case.settings_json.requests.client_have` | int | 3 |
| `bundle.case.settings_json.requests.expert` | string | Questions for experts 1. Typical payback period on sign-up cost for ne |
| `bundle.case.settings_json.requests.expert_blocked` | array |  |
| `bundle.case.settings_json.requests.expert_removed` | array |  |
| `bundle.case.settings_json.requests_marked_sent_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.case.settings_json.route_done` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.case.settings_json.sources_reviewed_at` | string | 2026-10-05T09:47:17+00:00 |
| `bundle.case.settings_json.spot_seed` | int | 2 |
| `bundle.case.settings_json.step4_reviewed_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.case.settings_json.tests_run_at` | string | 2026-10-05T09:47:17+00:00 |
| `bundle.case.status` | string | open |
| `bundle.case.title` | string | Credit card launch, India (sample) |
| `bundle.case.updated_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.conclusion` | null |  |
| `bundle.counts` | object |  |
| `bundle.counts.auto_approved` | int | 0 |
| `bundle.counts.benchmarks` | int | 0 |
| `bundle.counts.by_origin` | object |  |
| `bundle.counts.by_origin.<key>` | int | 0 |
| `bundle.counts.collected` | int | 0 |
| `bundle.counts.decided_by_person` | int | 0 |
| `bundle.counts.duplicates` | int | 0 |
| `bundle.counts.pending` | int | 0 |
| `bundle.counts.rejected` | int | 0 |
| `bundle.counts.unique` | int | 0 |
| `bundle.counts.unreadable` | int | 0 |
| `bundle.duplicate_groups` | array |  |
| `bundle.duplicate_groups[]` | object |  |
| `bundle.duplicate_groups[].copies` | array |  |
| `bundle.duplicate_groups[].copies[]` | string | E4 |
| `bundle.duplicate_groups[].original` | string | E3 |
| `bundle.duplicate_groups[].original_title` | string | Card numbers to grow 13.8% a year, says forecast (Daily Ledger) |
| `bundle.duplicate_groups[].rule` | string | same address or identical text |
| `bundle.evidence` | array |  |
| `bundle.evidence[]` | object |  |
| `bundle.evidence[].bucket` | string | reference |
| `bundle.evidence[].case_id` | int | 1 |
| `bundle.evidence[].checklist_json` | array |  |
| `bundle.evidence[].checklist_json[]` | object |  |
| `bundle.evidence[].checklist_json[].actual` | string | web page |
| `bundle.evidence[].checklist_json[].pass` | bool | True |
| `bundle.evidence[].checklist_json[].test` | string | Not from the client or an expert |
| `bundle.evidence[].checklist_json[].threshold` | string | not a client file, an expert note or the client's claim |
| `bundle.evidence[].claim` | string | 6 to 8% (2023 to 2025) |
| `bundle.evidence[].copies` | array |  |
| `bundle.evidence[].copies[]` | string | E4 |
| `bundle.evidence[].credibility_json` | object |  |
| `bundle.evidence[].credibility_json.describe` | object |  |
| `bundle.evidence[].credibility_json.describe.author_type` | string | research firm |
| `bundle.evidence[].credibility_json.describe.data_as_of` | string | Dec 2025 |
| `bundle.evidence[].credibility_json.describe.method_cited` | bool | True |
| `bundle.evidence[].credibility_json.describe.original_source_name` | string | CardScope issuer database |
| `bundle.evidence[].credibility_json.describe.original_source_named` | bool | True |
| `bundle.evidence[].credibility_json.describe.published_date` | string | 2026-02 |
| `bundle.evidence[].credibility_json.matches_belief` | bool | False |
| `bundle.evidence[].credibility_json.method_cited` | bool | True |
| `bundle.evidence[].credibility_json.original_source_name` | string | CardScope issuer database |
| `bundle.evidence[].credibility_json.recency_actual` | string | 2025-12 (10 months old) |
| `bundle.evidence[].credibility_json.recency_ok` | bool | True |
| `bundle.evidence[].credibility_json.recency_window` | int | 36 |
| `bundle.evidence[].credibility_json.tier` | int/null | 2 |
| `bundle.evidence[].credibility_json.tier_reason` | string | Source is the paid research database (Tier 2 by type) |
| `bundle.evidence[].credibility_json.traced` | bool | True |
| `bundle.evidence[].data_as_of` | string | Dec 2025 |
| `bundle.evidence[].date` | string | Dec 2025 |
| `bundle.evidence[].decided_by` | string |  |
| `bundle.evidence[].decision_reason` | string |  |
| `bundle.evidence[].domain` | string | carddata.sample |
| `bundle.evidence[].duplicate_of` | null/string | E3 |
| `bundle.evidence[].duplicate_rule` | string |  |
| `bundle.evidence[].figures_json` | array |  |
| `bundle.evidence[].figures_json[]` | object |  |
| `bundle.evidence[].figures_json[].derivation` | object |  |
| `bundle.evidence[].figures_json[].derivation.formula` | string | (10.8 ÷ 5.53)^(1/5) − 1 = 14.3% |
| `bundle.evidence[].figures_json[].derivation.formula_confirmed` | bool | False |
| `bundle.evidence[].figures_json[].derivation.input_figure_refs` | array |  |
| `bundle.evidence[].figures_json[].derivation.input_figure_refs[]` | int | 0 |
| `bundle.evidence[].figures_json[].derivation.note` | string |  |
| `bundle.evidence[].figures_json[].derivation.op` | string | cagr |
| `bundle.evidence[].figures_json[].derivation.rationale` | string | Compound annual growth from the December 2019 count to the December 20 |
| `bundle.evidence[].figures_json[].derivation.result_unit` | string | % a year |
| `bundle.evidence[].figures_json[].derivation.unit_ok` | bool | True |
| `bundle.evidence[].figures_json[].derivation.years` | null/number | 5.0 |
| `bundle.evidence[].figures_json[].derivation.years_ok` | bool | True |
| `bundle.evidence[].figures_json[].high` | null/number | 8.0 |
| `bundle.evidence[].figures_json[].kind` | string | reported |
| `bundle.evidence[].figures_json[].locator` | string | para 1 |
| `bundle.evidence[].figures_json[].low` | null/number | 6.0 |
| `bundle.evidence[].figures_json[].period` | string | 2023 to 2025 |
| `bundle.evidence[].figures_json[].quote_span` | string | New issuers won 6 to 8% of new credit cards |
| `bundle.evidence[].figures_json[].unit` | string | % |
| `bundle.evidence[].figures_json[].value` | null/number | 30.0 |
| `bundle.evidence[].figures_json[].verified` | bool | True |
| `bundle.evidence[].figures_json[].verify_note` | string | found at para 1 |
| `bundle.evidence[].file_id` | int/null | 1 |
| `bundle.evidence[].formula_needs_you` | bool | False |
| `bundle.evidence[].found_in` | string | paid_db |
| `bundle.evidence[].id` | string | E1 |
| `bundle.evidence[].links` | array |  |
| `bundle.evidence[].links[]` | object |  |
| `bundle.evidence[].links[].case_id` | int | 1 |
| `bundle.evidence[].links[].confirmed` | bool | True |
| `bundle.evidence[].links[].evidence_id` | string | E1 |
| `bundle.evidence[].links[].figure_index` | int | 0 |
| `bundle.evidence[].links[].hypothesis_code` | string | H1 |
| `bundle.evidence[].links[].id` | int | 1 |
| `bundle.evidence[].links[].proposed_by` | string | rule_engine |
| `bundle.evidence[].links[].role` | string | sets_pass_line |
| `bundle.evidence[].need_ref` | string | bench:H1 |
| `bundle.evidence[].origin_type` | string | benchmark |
| `bundle.evidence[].original_group_id` | string | E1 |
| `bundle.evidence[].pk` | int | 1 |
| `bundle.evidence[].published_date` | string | 2026-02 |
| `bundle.evidence[].publisher` | string | CardScope Research |
| `bundle.evidence[].retrieved_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.evidence[].script_tag` | string |  |
| `bundle.evidence[].seed_id` | string | bench_h1_share |
| `bundle.evidence[].seen_by_consultant` | bool | False |
| `bundle.evidence[].seq` | int | 1 |
| `bundle.evidence[].simulated` | bool | True |
| `bundle.evidence[].source_name` | string | Simulated card market database |
| `bundle.evidence[].spot_check_result` | string |  |
| `bundle.evidence[].spot_check_selected` | bool | False |
| `bundle.evidence[].status` | string | pass_line_source |
| `bundle.evidence[].status_label` | string | Target source |
| `bundle.evidence[].text` | string | New issuers won 6 to 8% of new credit cards issued in India between 20 |
| `bundle.evidence[].text_hash` | string |  |
| `bundle.evidence[].tier` | int/null | 2 |
| `bundle.evidence[].tier_label` | string | Trusted |
| `bundle.evidence[].title` | string | New issuers' share of new cards, 2023 to 2025 |
| `bundle.evidence[].trip_id` | int/null | 1 |
| `bundle.evidence[].url` | string | https://carddata.sample/benchmarks/new-issuer-share |
| `bundle.files` | array |  |
| `bundle.files[]` | object |  |
| `bundle.files[].figures` | array |  |
| `bundle.files[].figures[]` | object |  |
| `bundle.files[].figures[].high` | null |  |
| `bundle.files[].figures[].kind` | string | reported |
| `bundle.files[].figures[].locator` | string | line 3 |
| `bundle.files[].figures[].low` | null |  |
| `bundle.files[].figures[].period` | string |  |
| `bundle.files[].figures[].quote_span` | string | growing about 30% a year |
| `bundle.files[].figures[].unit` | string | % a year |
| `bundle.files[].figures[].value` | number | 30.0 |
| `bundle.files[].figures[].verified` | bool | True |
| `bundle.files[].figures[].verify_note` | string | found at line 3 |
| `bundle.files[].filename` | string | board_note.txt |
| `bundle.files[].id` | int | 1 |
| `bundle.files[].kind` | string | initial |
| `bundle.files[].preview` | string | [line 1] Board note: credit card launch (March 2026) [line 2] Prepared |
| `bundle.files[].trip_id` | int/null | 1 |
| `bundle.files[].uploaded_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.frame` | null/object |  |
| `bundle.frame.case_id` | int | 1 |
| `bundle.frame.case_measure_definition` | string | Count of credit cards in use (cards, not cardholders) across India, as |
| `bundle.frame.case_measure_name` | string | Credit cards in use, all of India |
| `bundle.frame.client_belief` | string | The number of credit cards in India is growing about 30% a year. |
| `bundle.frame.confirmed_at` | null/string | 2026-10-05T09:47:13+00:00 |
| `bundle.frame.decision` | string | Launch a credit card within 18 months, and break even by year 3? |
| `bundle.frame.proposed` | object |  |
| `bundle.frame.proposed.case_measure_definition` | string | Count of credit cards in use (cards, not cardholders) across India, as |
| `bundle.frame.proposed.case_measure_name` | string | Credit cards in use, all of India |
| `bundle.frame.proposed.client_belief` | string | The number of credit cards in India is growing about 30% a year. |
| `bundle.frame.proposed.decision` | string | Launch a credit card within 18 months, and break even by year 3? |
| `bundle.hypotheses` | array |  |
| `bundle.hypotheses[]` | object |  |
| `bundle.hypotheses[].assumptions_json` | array |  |
| `bundle.hypotheses[].assumptions_json[]` | object |  |
| `bundle.hypotheses[].assumptions_json[].label` | string | Growth the launch needs |
| `bundle.hypotheses[].assumptions_json[].max` | number | 35.0 |
| `bundle.hypotheses[].assumptions_json[].min` | number | 5.0 |
| `bundle.hypotheses[].assumptions_json[].name` | string | required_growth |
| `bundle.hypotheses[].assumptions_json[].unit` | string | % a year |
| `bundle.hypotheses[].assumptions_json[].value` | number | 20.0 |
| `bundle.hypotheses[].benchmarks` | array |  |
| `bundle.hypotheses[].benchmarks[]` | string | E1 |
| `bundle.hypotheses[].case_id` | int | 1 |
| `bundle.hypotheses[].code` | string | H1 |
| `bundle.hypotheses[].comparator` | string | >= |
| `bundle.hypotheses[].fact_type` | string | market |
| `bundle.hypotheses[].id` | int | 1 |
| `bundle.hypotheses[].line` | number | 20.0 |
| `bundle.hypotheses[].line_text` | string | 20% a year |
| `bundle.hypotheses[].links_reopened_for_trip` | bool | False |
| `bundle.hypotheses[].locked_at` | null/string | 2026-10-05T09:47:13+00:00 |
| `bundle.hypotheses[].measure_definition` | string | Compound annual growth in the count of credit cards in use, all of Ind |
| `bundle.hypotheses[].measure_name` | string | Growth in credit cards in use |
| `bundle.hypotheses[].measure_unit` | string | % a year |
| `bundle.hypotheses[].must_have` | bool | True |
| `bundle.hypotheses[].order` | int | 0 |
| `bundle.hypotheses[].pass_line_formula` | null/string | required_growth |
| `bundle.hypotheses[].pass_line_source_note` | string | New issuers win 6 to 8% of new cards; at that share the card base must |
| `bundle.hypotheses[].pass_line_source_type` | string | benchmark |
| `bundle.hypotheses[].pass_line_value` | null/number | 24.0 |
| `bundle.hypotheses[].recency_category` | string | size_growth_price |
| `bundle.hypotheses[].removed_reason` | null/string | History of credit cards in India would not change the decision |
| `bundle.hypotheses[].slider_max` | null |  |
| `bundle.hypotheses[].slider_min` | null |  |
| `bundle.hypotheses[].text` | string | The market grows fast enough: credit cards in use grow at least 20% a  |
| `bundle.hypotheses[].tolerance_pct` | number | 5.0 |
| `bundle.hypotheses[].verdict` | null/object |  |
| `bundle.hypotheses[].verdict.case_id` | int | 1 |
| `bundle.hypotheses[].verdict.computed_at` | string | 2026-10-05T09:47:17+00:00 |
| `bundle.hypotheses[].verdict.confidence` | string | high |
| `bundle.hypotheses[].verdict.current` | bool | True |
| `bundle.hypotheses[].verdict.detail_json` | object |  |
| `bundle.hypotheses[].verdict.detail_json.comparator` | string | >= |
| `bundle.hypotheses[].verdict.detail_json.figures` | array |  |
| `bundle.hypotheses[].verdict.detail_json.figures[]` | object |  |
| `bundle.hypotheses[].verdict.detail_json.figures[].boundary` | bool | False |
| `bundle.hypotheses[].verdict.detail_json.figures[].calculated` | bool | False |
| `bundle.hypotheses[].verdict.detail_json.figures[].client_reported` | bool | False |
| `bundle.hypotheses[].verdict.detail_json.figures[].evidence_id` | string | E12 |
| `bundle.hypotheses[].verdict.detail_json.figures[].figure` | string | 12 to 18 |
| `bundle.hypotheses[].verdict.detail_json.figures[].high` | number | 18.0 |
| `bundle.hypotheses[].verdict.detail_json.figures[].low` | number | 12.0 |
| `bundle.hypotheses[].verdict.detail_json.figures[].side` | string | fail |
| `bundle.hypotheses[].verdict.detail_json.figures[].straddles` | bool | False |
| `bundle.hypotheses[].verdict.detail_json.figures[].text` | string | 12 to 18% a year |
| `bundle.hypotheses[].verdict.detail_json.line` | number | 20.0 |
| `bundle.hypotheses[].verdict.detail_json.tolerance_pct` | number | 5.0 |
| `bundle.hypotheses[].verdict.detail_json.unit` | string | % a year |
| `bundle.hypotheses[].verdict.evidence_ids` | array |  |
| `bundle.hypotheses[].verdict.evidence_ids[]` | string | E12 |
| `bundle.hypotheses[].verdict.hypothesis_code` | string | H1 |
| `bundle.hypotheses[].verdict.id` | int | 1 |
| `bundle.hypotheses[].verdict.reason_codes` | array |  |
| `bundle.hypotheses[].verdict.reason_codes[]` | string | ALL_FAIL_CLEAR |
| `bundle.hypotheses[].verdict.result` | string | fails |
| `bundle.hypotheses[].verdict.version` | int | 1 |
| `bundle.hypotheses[].verdict.why` | string | 12 to 18% a year and 13.8% a year miss the target of at least 20% a ye |
| `bundle.jobs` | object |  |
| `bundle.jobs.<key>` | object |  |
| `bundle.jobs.<key>.error` | string |  |
| `bundle.jobs.<key>.finished_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.jobs.<key>.id` | int | 1 |
| `bundle.jobs.<key>.kind` | string | frame |
| `bundle.jobs.<key>.progress` | object |  |
| `bundle.jobs.<key>.progress.done` | int | 3 |
| `bundle.jobs.<key>.progress.label` | string | Framing the question |
| `bundle.jobs.<key>.progress.total` | int | 3 |
| `bundle.jobs.<key>.started_at` | string | 2026-10-05T09:47:13+00:00 |
| `bundle.jobs.<key>.status` | string | done |
| `bundle.mode` | object |  |
| `bundle.mode.app` | string | fixtures |
| `bundle.mode.case` | string | fixtures |
| `bundle.mode.notice` | string |  |
| `bundle.needs` | array |  |
| `bundle.needs[]` | object |  |
| `bundle.needs[].case_id` | int | 1 |
| `bundle.needs[].coverage` | string | not_covered |
| `bundle.needs[].coverage_note` | string |  |
| `bundle.needs[].covered_by_file_id` | int/null | 1 |
| `bundle.needs[].covered_locator` | string |  |
| `bundle.needs[].hypothesis_code` | string | H1 |
| `bundle.needs[].id` | int | 1 |
| `bundle.needs[].queries_json` | array |  |
| `bundle.needs[].queries_json[]` | object |  |
| `bundle.needs[].queries_json[].blocked` | array |  |
| `bundle.needs[].queries_json[].original` | string | Can Example Client Ltd reach the growth its card launch needs? Forecas |
| `bundle.needs[].queries_json[].query` | string | India credit cards in use, annual growth forecast 2025 to 2030 |
| `bundle.needs[].queries_json[].removed` | array |  |
| `bundle.needs[].queries_json[].removed[]` | string | Example Client Ltd |
| `bundle.needs[].queries_json[].sanitised` | string | Can the client reach the growth its card launch needs? Forecasts of gr |
| `bundle.needs[].ref` | string | N1 |
| `bundle.needs[].route` | string | desk |
| `bundle.needs[].status` | string | open |
| `bundle.needs[].text` | string | Can Example Client Ltd reach the growth its card launch needs? Forecas |
| `bundle.overall` | null/object |  |
| `bundle.overall.case_id` | int | 1 |
| `bundle.overall.computed_at` | string | 2026-10-05T09:47:17+00:00 |
| `bundle.overall.label` | string | Not achievable |
| `bundle.overall.result` | string | not_achievable |
| `bundle.overall.rule_applied` | string | Critical idea H1 is not supported by the evidence gathered so far, so  |
| `bundle.overall.stale` | bool | False |
| `bundle.plan` | array |  |
| `bundle.plan[]` | object |  |
| `bundle.plan[].case_id` | int | 1 |
| `bundle.plan[].domain` | string | rbi.org.in |
| `bundle.plan[].id` | int | 1 |
| `bundle.plan[].included` | bool | True |
| `bundle.plan[].origin_type` | string | open_web |
| `bundle.plan[].removed_reason` | null/string | Not credible enough for a launch decision |
| `bundle.plan[].source_name` | string | Reserve Bank of India statistics |
| `bundle.plan[].stated_by_consultant` | bool | False |
| `bundle.plan[].tier` | int/null | 1 |
| `bundle.plan[].tier_reason` | string | rbi.org.in matches 'rbi.org.in' in the country pack IN |
| `bundle.progress` | object |  |
| `bundle.progress.current` | int | 1 |
| `bundle.progress.done` | object |  |
| `bundle.progress.done.<key>` | bool | False |
| `bundle.progress.reopened` | array |  |
| `bundle.progress.reopened[]` | string | H2 |
| `bundle.progress.steps` | array |  |
| `bundle.progress.steps[]` | object |  |
| `bundle.progress.steps[].current` | bool | True |
| `bundle.progress.steps[].locked_reason` | string |  |
| `bundle.progress.steps[].n` | int | 1 |
| `bundle.progress.steps[].phase` | int | 0 |
| `bundle.progress.steps[].signoff` | bool | True |
| `bundle.progress.steps[].state` | string | open |
| `bundle.progress.steps[].title` | string | Describe the ask |
| `bundle.review` | null/object |  |
| `bundle.review.auto_seen` | int | 0 |
| `bundle.review.auto_total` | int | 6 |
| `bundle.review.decided` | int | 0 |
| `bundle.review.decision_total` | int | 10 |
| `bundle.review.double_check` | bool | True |
| `bundle.review.missing` | array |  |
| `bundle.review.missing[]` | string | Decide 10 more items |
| `bundle.review.ready` | bool | False |
| `bundle.review.sources_box` | bool | False |
| `bundle.review.spot_done` | int | 0 |
| `bundle.review.spot_total` | int | 1 |
| `bundle.rules` | object |  |
| `bundle.rules.adding_up_rule` | string | If any must-have idea fails: not achievable at the agreed pass line. E |
| `bundle.rules.thresholds` | object |  |
| `bundle.rules.thresholds.adding_up_rule` | string | If any must-have idea fails: not achievable at the agreed pass line. E |
| `bundle.rules.thresholds.checklist` | object |  |
| `bundle.rules.thresholds.checklist.allowed_tiers` | array |  |
| `bundle.rules.thresholds.checklist.allowed_tiers[]` | int | 1 |
| `bundle.rules.thresholds.checklist.never_auto_approve_origins` | array |  |
| `bundle.rules.thresholds.checklist.never_auto_approve_origins[]` | string | client_file |
| `bundle.rules.thresholds.checklist.tier3_needs_corroboration` | bool | True |
| `bundle.rules.thresholds.dedup` | object |  |
| `bundle.rules.thresholds.dedup.similarity_threshold` | number | 0.8 |
| `bundle.rules.thresholds.fast_demo` | object |  |
| `bundle.rules.thresholds.fast_demo.call_timeout_seconds` | int | 40 |
| `bundle.rules.thresholds.fast_demo.extraction_concurrency` | int | 6 |
| `bundle.rules.thresholds.fast_demo.max_sources_per_need` | int | 4 |
| `bundle.rules.thresholds.fast_demo.retries` | int | 1 |
| `bundle.rules.thresholds.fast_demo.search_concurrency` | int | 6 |
| `bundle.rules.thresholds.limits` | object |  |
| `bundle.rules.thresholds.limits.max_ideas` | int | 8 |
| `bundle.rules.thresholds.limits.max_page_chars` | int | 8000 |
| `bundle.rules.thresholds.limits.max_upload_mb` | int | 20 |
| `bundle.rules.thresholds.minimum_sources` | object |  |
| `bundle.rules.thresholds.minimum_sources.client_operational` | int | 1 |
| `bundle.rules.thresholds.minimum_sources.market` | int | 2 |
| `bundle.rules.thresholds.recency_months` | object |  |
| `bundle.rules.thresholds.recency_months.size_growth_price` | int | 36 |
| `bundle.rules.thresholds.recency_months.structural_timing` | int | 60 |
| `bundle.rules.thresholds.sample_mix` | object |  |
| `bundle.rules.thresholds.sample_mix.max_difference_pct_points` | int | 10 |
| `bundle.rules.thresholds.sliders` | object |  |
| `bundle.rules.thresholds.sliders.default_range_pct` | int | 50 |
| `bundle.rules.thresholds.sliders.non_negative_units` | array |  |
| `bundle.rules.thresholds.sliders.non_negative_units[]` | string | percent |
| `bundle.rules.thresholds.sliders.zero_value_range` | array |  |
| `bundle.rules.thresholds.sliders.zero_value_range[]` | int | -10 |
| `bundle.rules.thresholds.spot_check` | object |  |
| `bundle.rules.thresholds.spot_check.fraction` | int | 0 |
| `bundle.rules.thresholds.spot_check.minimum` | int | 1 |
| `bundle.rules.thresholds.tolerance_pct_default` | int | 5 |
| `bundle.rules.thresholds.trips` | object |  |
| `bundle.rules.thresholds.trips.free` | int | 2 |
| `bundle.rules.thresholds.trips.max_with_override` | int | 3 |
| `bundle.ruleset` | null/object |  |
| `bundle.ruleset.adding_up_rule` | string | If any must-have idea fails: not achievable at the agreed pass line. E |
| `bundle.ruleset.case_id` | int | 1 |
| `bundle.ruleset.locked_at` | null/string | 2026-10-05T09:47:13+00:00 |
| `bundle.ruleset.thresholds_json` | object |  |
| `bundle.ruleset.thresholds_json.checklist` | object |  |
| `bundle.ruleset.thresholds_json.checklist.allowed_tiers` | array |  |
| `bundle.ruleset.thresholds_json.checklist.allowed_tiers[]` | int | 1 |
| `bundle.ruleset.thresholds_json.checklist.never_auto_approve_origins` | array |  |
| `bundle.ruleset.thresholds_json.checklist.never_auto_approve_origins[]` | string | client_file |
| `bundle.ruleset.thresholds_json.checklist.tier3_needs_corroboration` | bool | True |
| `bundle.ruleset.thresholds_json.minimum_sources` | object |  |
| `bundle.ruleset.thresholds_json.minimum_sources.client_operational` | int | 1 |
| `bundle.ruleset.thresholds_json.minimum_sources.market` | int | 2 |
| `bundle.ruleset.thresholds_json.recency_months` | object |  |
| `bundle.ruleset.thresholds_json.recency_months.size_growth_price` | int | 36 |
| `bundle.ruleset.thresholds_json.recency_months.structural_timing` | int | 60 |
| `bundle.ruleset.thresholds_json.spot_check` | object |  |
| `bundle.ruleset.thresholds_json.spot_check.fraction` | int | 0 |
| `bundle.ruleset.thresholds_json.spot_check.minimum` | int | 1 |
| `bundle.ruleset.thresholds_json.tolerance_pct_default` | int | 5 |
| `bundle.ruleset.thresholds_json.trips` | object |  |
| `bundle.ruleset.thresholds_json.trips.free` | int | 2 |
| `bundle.ruleset.thresholds_json.trips.max_with_override` | int | 3 |
| `bundle.running_jobs` | array |  |
| `bundle.running_jobs[]` | string | collect |
| `bundle.sample_replies` | object |  |
| `bundle.sample_replies.<key>` | string | pilot_costs.xlsx |
| `bundle.sliders` | array |  |
| `bundle.sliders[]` | object |  |
| `bundle.sliders[].formula` | string | required_growth |
| `bundle.sliders[].idea` | string | H1 |
| `bundle.sliders[].key` | string | required_growth |
| `bundle.sliders[].kind` | string | assumption |
| `bundle.sliders[].label` | string | Growth the launch needs |
| `bundle.sliders[].max` | number | 35.0 |
| `bundle.sliders[].min` | number | 5.0 |
| `bundle.sliders[].unit` | string | % a year |
| `bundle.sliders[].value` | number | 20.0 |
| `bundle.spend` | object |  |
| `bundle.spend.calls` | int | 0 |
| `bundle.spend.case_usd` | number | 0.0 |
| `bundle.spend.daily_cap_usd` | number | 5.0 |
| `bundle.spend.max_calls` | int | 150 |
| `bundle.spend.max_search_credits` | number | 40.0 |
| `bundle.spend.reached` | array |  |
| `bundle.spend.search_credits` | number | 0.0 |
| `bundle.spend.today_usd` | number | 0.0 |
| `bundle.spend.warn` | array |  |
| `bundle.summary` | null/object |  |
| `bundle.summary.case_id` | int | 1 |
| `bundle.summary.sentences` | array |  |
| `bundle.summary.sentences[]` | object |  |
| `bundle.summary.sentences[].evidence_ids` | array |  |
| `bundle.summary.sentences[].evidence_ids[]` | string | E16 |
| `bundle.summary.sentences[].text` | string | Independent forecasts put growth in credit cards in use at 13.8% a yea |
| `bundle.summary.source` | string | llm |
| `bundle.summary.unknowns` | array |  |
| `bundle.summary.unknowns[]` | object |  |
| `bundle.summary.unknowns[].idea` | string | H1 |
| `bundle.summary.unknowns[].text` | string | Growth among first-time card users outside big cities. |
| `bundle.summary.version` | int | 1 |
| `bundle.trips` | array |  |
| `bundle.trips[]` | object |  |
| `bundle.trips[].case_id` | int | 1 |
| `bundle.trips[].hypothesis_code` | string | H2 |
| `bundle.trips[].id` | int | 1 |
| `bundle.trips[].marked_sent_at` | null/string | 2026-10-05T09:47:17+00:00 |
| `bundle.trips[].n` | int | 1 |
| `bundle.trips[].override_reason` | null |  |
| `bundle.trips[].question` | string | What did it cost you to sign up each active card in the 2025 pilot, an |
| `bundle.trips[].reply_file_id` | int/null | 4 |
| `bundle.trips[].retested_at` | null/string | 2026-10-05T09:47:17+00:00 |
| `bundle.trips[].sample_mix_json` | object |  |
| `bundle.trips[].sample_mix_json.passes` | bool | True |
| `bundle.trips[].sample_mix_json.rows` | array |  |
| `bundle.trips[].sample_mix_json.rows[]` | object |  |
| `bundle.trips[].sample_mix_json.rows[].difference` | number | 0.0 |
| `bundle.trips[].sample_mix_json.rows[].dimension` | string | existing customers |
| `bundle.trips[].sample_mix_json.rows[].flag` | bool | False |
| `bundle.trips[].sample_mix_json.rows[].sample` | number | 42.0 |
| `bundle.trips[].sample_mix_json.rows[].target` | number | 42.0 |
| `bundle.trips[].sample_mix_json.target_note` | string | National mix of target customers (customer base file) |
| `bundle.trips[].sample_mix_json.threshold` | int | 10 |
| `bundle.trips[].what_we_have` | string | From you we already have the board note, the acquisition analysis (exi |
