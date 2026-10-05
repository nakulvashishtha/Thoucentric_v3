Read one source (a web page, a research note, a database extract or an expert note). Its text is split into paragraphs; paragraph 1 is the first block of text, paragraph 2 the next, and so on.

Pull out only figures that bear on the ideas listed (match their measures). For each figure:
- value for a single number, or low and high for a range (others null). Plain numbers only (1,200 becomes 1200).
- unit: plain words. When the figure measures the same thing as an idea, write the unit exactly as that idea's unit (for example "% a year"). Keep scale words like million or crore in the unit.
- period the figure refers to if stated, else "".
- quote_span: the shortest exact piece of the text that contains the number, copied character for character. Do not paraphrase.
- locator: "para N" for the paragraph it is in (for a line-tagged text use the tag, for example "line 2").
At most 6 figures. If the source has no relevant figure, return an empty list.

Describe the source: author_type (for example "government statistics office", "regulator", "research firm", "news outlet", "blog", "consulting firm archive", "industry expert"), method_cited (does it say how the figure was made), original_source_named and original_source_name (if it says the figure comes from another named report or body), published_date (YYYY-MM-DD or YYYY-MM if known) and data_as_of (the period the data describes, for example "Dec 2024"), else "".
