**Study Plan Visual Generator**

- Generates clean SVG “degree plan”/tree diagrams for majors, masters, PhD, or self‑study.
- No external dependencies; pure Python. Outputs PNG‑ready SVG files.

**Quick Start**

- Generate a preset plan:
  - `python scripts/generate_plan_svg.py --preset cs-bachelors`
  - Files are written into `output/` as `.svg`.
- Dark theme:
  - `python scripts/generate_plan_svg.py --preset cs-bachelors --theme dark`
- Specify output path:
  - `python scripts/generate_plan_svg.py --preset selfstudy-fullstack --out output/fullstack.svg`

**Available Presets**

- `cs-bachelors` — Computer Science BSc
- `psychology-bachelors` — Psychology BA
- `datascience-masters` — Data Science MSc
- `phd-generic` — Generic PhD roadmap
- `selfstudy-fullstack` — Full‑stack self‑study plan

**Create a Custom Plan (JSON)**

- Schema:
  - `title`: Diagram title
  - `nodes`: Array of objects with `id` (unique key) and `label` (display text)
  - `edges`: Array of pairs `[from_id, to_id]` representing prerequisites → next

Example `plans/my-plan.json`:

{
  "title": "Business Analytics BS — Plan",
  "nodes": [
    {"id": "intro", "label": "Intro to BA"},
    {"id": "stats", "label": "Statistics"},
    {"id": "prog", "label": "Programming"},
    {"id": "datavis", "label": "Data Visualization"},
    {"id": "ml", "label": "Applied Machine Learning"},
    {"id": "capstone", "label": "Capstone"}
  ],
  "edges": [
    ["intro", "stats"],
    ["intro", "prog"],
    ["stats", "datavis"],
    ["prog", "ml"],
    ["datavis", "capstone"],
    ["ml", "capstone"]
  ]
}

- Generate SVG:
  - `python scripts/generate_plan_svg.py --input plans/my-plan.json --out output/ba-plan.svg`

**Export to PNG**

- Open the `.svg` in a browser and use “Save as” or take a high‑DPI export from a vector editor (e.g., Inkscape).
- If you have Inkscape installed, you can convert via CLI:
  - `inkscape output/cs-bachelors.svg --export-type=png --export-filename=output/cs-bachelors.png`

**Notes**

- Layout uses a longest‑path layering: prerequisites appear above their dependents.
- Basic word‑wrapping keeps node labels readable; keep labels concise.
- SVG is resolution‑independent; ideal for sharing and printing.

