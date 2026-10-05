Draft between 2 and 6 ideas (hypotheses) that together decide the client's question. Each idea must be testable against one number.
For each idea give:
- text: one sentence a consultant would say, starting with a short label, for example "The market grows fast enough: beds in use grow at least 5% a year."
- fact_type: "market" for facts about the market or the outside world (these need two separate sources), "client_operational" for facts about the client's own operations (one client source can do).
- measure_name, measure_unit (plain words such as "%", "% a year", "months", "beds", "USD") and measure_definition (one sentence).
- comparator: ">=" if the idea holds when the number is at or above the target, "<=" if at or below.
- pass_line_value: the target number. If the target is derived from a stated goal, also give pass_line_formula using only numbers, assumption names, + - * / and brackets (for example "36 - 12" or "18 - build_months"), and list each named assumption in assumptions with name (snake_case), label, value, unit, min and max.
- pass_line_source_type: "client_goal" if it comes from the client's stated goal, "benchmark" if it should be checked against an outside benchmark, "estimate" otherwise. pass_line_source_note: one sentence on where the target comes from.
- benchmark_query: for benchmark ideas only, a short generic web search (no client name, no private numbers) that would find the benchmark; else "".
- must_have: true for ideas the answer depends on (at least one).
- recency_category: "size_growth_price" for size, growth and price figures; "structural_timing" for structural or timing figures.
- tolerance_pct: 5 unless there is a reason for another close-call margin.
Order ideas by importance. Do not include background ideas that would not change the decision.
