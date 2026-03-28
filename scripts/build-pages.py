#!/usr/bin/env python3
"""Build index.html by injecting deal data into the visualization template.

Replaces the JSON data islands in deal-visualization.html with actual deal
data so the page renders the full graph on GitHub Pages.
"""

import argparse
import json
import re
import sys
from pathlib import Path


def build(template_path: str, graph_path: str, analysis_path: str, output_path: str) -> None:
    template = Path(template_path).read_text(encoding="utf-8")
    graph_json = Path(graph_path).read_text(encoding="utf-8").strip()
    analysis_json = Path(analysis_path).read_text(encoding="utf-8").strip()

    # Validate JSON
    graph_data = json.loads(graph_json)
    json.loads(analysis_json)

    # Update <title> with deal name
    deal_name = graph_data.get("deal", {}).get("name", "Deal Visualization")
    template = re.sub(
        r"<title>.*?</title>",
        f"<title>{deal_name} - Document Dependency Analysis</title>",
        template,
        count=1,
    )

    # Replace graph data island
    template = re.sub(
        r'(<script\s+type="application/json"\s+id="deal-graph-data">).*?(</script>)',
        lambda m: m.group(1) + json.dumps(graph_data, separators=(",", ":")) + m.group(2),
        template,
        count=1,
    )

    # Replace analysis data island
    template = re.sub(
        r'(<script\s+type="application/json"\s+id="deal-analysis-data">).*?(</script>)',
        lambda m: m.group(1) + analysis_json + m.group(2),
        template,
        count=1,
    )

    Path(output_path).write_text(template, encoding="utf-8")
    print(f"Built {output_path} ({len(template):,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Pages index.html")
    parser.add_argument("--template", required=True, help="Path to deal-visualization.html")
    parser.add_argument("--graph", required=True, help="Path to deal-graph.json")
    parser.add_argument("--analysis", required=True, help="Path to deal-analysis.json")
    parser.add_argument("--output", required=True, help="Output path for index.html")
    args = parser.parse_args()
    build(args.template, args.graph, args.analysis, args.output)
