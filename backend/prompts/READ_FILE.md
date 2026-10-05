Read one file the client sent. Each line of the file starts with its place in square brackets, for example [line 3] for text or [B4] / [Sheet!B4] for a spreadsheet cell.

Pull out every figure that could help answer the client's ask (sizes, growth rates, shares, costs, prices, margins, times, counts).
For each figure:
- value for a single number, or low and high for a range (leave the others null). Use plain numbers: 1,200 becomes 1200; "12 to 18%" is low 12, high 18.
- unit in plain words, for example "%", "% a year", "months", "INR", "INR per month", "beds", "lakh customers". Keep scale words such as thousand, lakh, crore, million in the unit, not in the number.
- period the figure refers to, if stated (for example "2025", "Dec 2024", "2025 to 2030"), else "".
- quote_span: copy the shortest exact piece of text from that place that contains the number. Copy it character for character. For a spreadsheet cell, the cell's own text is enough (for example "34%").
- locator: the place in brackets without the brackets, for example "line 3" or "B4" or "Summary!B2".

Describe the file: author_type ("client" for the client's own files, "expert" for an expert's note), method_cited (true if it says how the figures were made), original_source_named and original_source_name (if it says the figure comes from someone else), published_date and data_as_of if stated (formats like "2026-03", "Jun 2026" or "2025"), else "".

If the file describes who a sample, pilot or survey covered (for example 42% existing customers, 58% new), list each group and its share in percent in sample_mix. Otherwise leave sample_mix empty.
