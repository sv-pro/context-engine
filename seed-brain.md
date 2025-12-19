# Seed Prompt: Scrubbing Center Knowledge Base

Copy and paste the following prompt into an LLM assistant (like ChatGPT, Claude, or the very Llama3 model you just set up in Open WebUI) to generate a set of test files for your "Brain".

---

## The Prompt

"You are a Senior Network Security Architect specializing in DDoS mitigation. Please generate a set of **5 interconnected Markdown files** that serve as a Knowledge Base for a new **'Scrubbing Center Monitoring & Management Portal'**.

The files will be used to test an automated ingestion system, so they must follow these strict formatting rules:

1.  **YAML Frontmatter**: Each file must start with a YAML block containing `title`, `tags` (a list), `author`, and `date`.
2.  **Wikilinks**: Use `[[Link Name]]` syntax to create cross-references between the files.
3.  **Content**: Provide realistic, technical descriptions of systems, metrics, and workflows.

### File Requirements:

1.  **Index.md**: An entry point titled 'Scrubbing Center Portal Overview'. It should summarize the portal's purpose and link to [[Architecture Overview]], [[Dashboard Metrics]], and [[Mitigation Workflows]].
2.  **Architecture.md**: Title 'System Architecture'. Describe the BGP Flowspec integration, Anycast routing, and the scrubbing pipeline stages. Link back to [[Index]].
3.  **Metrics.md**: Title 'Dashboard Metrics & Alerts'. Detail key performance indicators like `PPS (Packets Per Second)`, `BPS (Bits Per Second)`, and `Drop Rate`. Mention integration with [[Mitigation Workflows]].
4.  **Workflows.md**: Title 'Mitigation Workflows'. Explain the transition from 'Monitoring' to 'Mitigation' mode when a threshold is exceeded. Link to [[Architecture Overview]].
5.  **User-Guide.md**: Title 'Portal Management Guide'. Describe the UI components (Traffic Graphs, Rule Manager, Incident Logs).

**Please output each file in a separate code block so I can easily save them.**"

---

### How to use this:
1. Run the prompt above in your preferred assistant.
2. Save the resulting files into your `./volumes/brain/` directory.
3. Watch the `context-driver` logs to see the ingestion in action!
