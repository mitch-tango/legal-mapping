"""Build three themed visualization HTML files from the base template."""
import re

with open("deals/test-acme-acquisition/visualization.html") as f:
    base = f.read()

# ── Theme definitions: CSS variables + Cytoscape node/edge style overrides ──

THEMES = {
    "dark-professional": {
        "title": "Acme Industrial Park - Dark Professional Theme (TEST DATA)",
        "css_vars": """
        :root {
            --bg-primary: #0f172a;
            --bg-panel: #1e293b;
            --border-color: #334155;
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --severity-critical: #f43f5e;
            --severity-error: #f59e0b;
            --severity-warning: #38bdf8;
            --severity-info: #64748b;
            --cat-primary: #38bdf8;
            --cat-ancillary: #c084fc;
            --cat-financial: #34d399;
            --cat-corporate: #fbbf24;
            --cat-real-estate: #f87171;
            --cat-regulatory: #818cf8;
            --cat-closing: #2dd4bf;
            --edge-control: #f87171;
            --edge-reference: #38bdf8;
            --edge-financial: #34d399;
            --edge-modification: #c084fc;
            --edge-conditional: #fbbf24;
            --edge-term: #2dd4bf;
        }""",
        "body_extra": """
            background: var(--bg-primary);
            font-family: 'SF Mono', 'Cascadia Code', 'Consolas', ui-monospace, monospace;
        """,
        "toolbar_extra": """
            background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
            border-bottom: 1px solid #334155;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
        """,
        "toolbar_control_extra": """
            background: #0f172a;
            color: #e2e8f0;
            border-color: #475569;
        """,
        "detail_panel_extra": """
            background: #1e293b;
            box-shadow: -4px 0 20px rgba(0,0,0,0.5);
            border-left: 1px solid #334155;
        """,
        "graph_bg": """
            background: #0f172a;
            background-image: radial-gradient(circle, #1e293b 1px, transparent 1px);
            background-size: 24px 24px;
        """,
        "node_style": {
            'label': "function(ele) { var n = ele.data('label') || ''; return n.length > 22 ? n.substring(0, 22) + '…' : n; }",
            'width': "function(ele) { return Math.min(90, Math.max(50, 50 + Math.sqrt(ele.degree()) * 10)); }",
            'height': "function(ele) { return Math.min(90, Math.max(50, 50 + Math.sqrt(ele.degree()) * 10)); }",
            'font-size': '12px',
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'text-wrap': 'ellipsis',
            'text-max-width': '120px',
            'border-width': 1,
            'border-color': '#475569',
            'border-opacity': 0.8,
            'color': '#e2e8f0',
            'text-outline-width': 2,
            'text-outline-color': '#0f172a',
            'shape': 'round-rectangle',
        },
        "node_categories": {
            '.category-primary':    { 'background-color': '#38bdf8', 'border-color': '#0ea5e9' },
            '.category-ancillary':  { 'background-color': '#c084fc', 'border-color': '#a855f7' },
            '.category-financial':  { 'background-color': '#34d399', 'border-color': '#10b981' },
            '.category-corporate':  { 'background-color': '#fbbf24', 'border-color': '#f59e0b' },
            '.category-real-estate':{ 'background-color': '#818cf8', 'border-color': '#6366f1' },
            '.category-regulatory': { 'background-color': '#f87171', 'border-color': '#ef4444' },
            '.category-closing':    { 'background-color': '#2dd4bf', 'border-color': '#14b8a6' },
            '.category-other':      { 'background-color': '#64748b', 'border-color': '#475569' },
        },
        "edge_base": {
            'width': 2,
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#475569',
            'line-color': '#475569',
            'arrow-scale': 1.3,
            'label': '',
        },
        "edge_families": {
            '.controls, .subordinates_to, .supersedes': { 'line-color': '#f87171', 'target-arrow-color': '#f87171' },
            '.references, .incorporates': { 'line-color': '#38bdf8', 'target-arrow-color': '#38bdf8' },
            '.guarantees, .secures, .assigns, .indemnifies': { 'line-color': '#34d399', 'target-arrow-color': '#34d399' },
            '.amends, .restricts, .restates': { 'line-color': '#c084fc', 'target-arrow-color': '#c084fc' },
            '.triggers, .conditions_precedent, .consents_to': { 'line-color': '#fbbf24', 'target-arrow-color': '#fbbf24' },
            '.defines_terms_for': { 'line-color': '#2dd4bf', 'target-arrow-color': '#2dd4bf' },
        },
        "extra_css": """
        .toolbar select:hover, .toolbar button:hover { background: #334155; }
        .toolbar .toggle-btn[aria-pressed="true"] { background: #38bdf8; color: #0f172a; border-color: #38bdf8; }
        .toolbar .btn-action { background: #38bdf8; color: #0f172a; border-color: #38bdf8; font-weight: 700; }
        .filter-panel { background: #1e293b; border-color: #334155; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
        .badge-critical { background: #f43f5e; } .badge-error { background: #f59e0b; color: #0f172a; }
        .badge-warning { background: #38bdf8; color: #0f172a; } .badge-info { background: #475569; }
        .detail-panel-close:hover { background: #334155; color: #e2e8f0; }
        .timeline-container { background: #0f172a; color: #e2e8f0; }
        """,
    },

    "warm-elegant": {
        "title": "Acme Industrial Park - Warm Elegant Theme (TEST DATA)",
        "css_vars": """
        :root {
            --bg-primary: #faf8f5;
            --bg-panel: #ffffff;
            --border-color: #e8e0d4;
            --text-primary: #2c2418;
            --text-secondary: #7c6f5e;
            --severity-critical: #9b1c31;
            --severity-error: #b45309;
            --severity-warning: #1e40af;
            --severity-info: #7c6f5e;
            --cat-primary: #1e3a5f;
            --cat-ancillary: #6b2142;
            --cat-financial: #2d5016;
            --cat-corporate: #78570a;
            --cat-real-estate: #7c3626;
            --cat-regulatory: #3b3080;
            --cat-closing: #1a5c50;
            --edge-control: #9b1c31;
            --edge-reference: #1e3a5f;
            --edge-financial: #2d5016;
            --edge-modification: #6b2142;
            --edge-conditional: #78570a;
            --edge-term: #1a5c50;
        }""",
        "body_extra": """
            background: var(--bg-primary);
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        """,
        "toolbar_extra": """
            background: #ffffff;
            border-bottom: 2px solid #d4c5a9;
            box-shadow: 0 1px 4px rgba(44,36,24,0.06);
        """,
        "toolbar_control_extra": """
            background: #ffffff;
            color: #2c2418;
            border-color: #d4c5a9;
            border-radius: 6px;
        """,
        "detail_panel_extra": """
            background: #fffdf9;
            box-shadow: -4px 0 16px rgba(44,36,24,0.08);
            border-left: 3px solid #c9a84c;
        """,
        "graph_bg": """
            background: linear-gradient(135deg, #faf8f5 0%, #f5f0e8 100%);
        """,
        "node_style": {
            'label': "function(ele) { var n = ele.data('label') || ''; return n.length > 24 ? n.substring(0, 24) + '…' : n; }",
            'width': "function(ele) { return Math.min(90, Math.max(48, 48 + Math.sqrt(ele.degree()) * 10)); }",
            'height': "function(ele) { return Math.min(90, Math.max(48, 48 + Math.sqrt(ele.degree()) * 10)); }",
            'font-size': '11px',
            'font-family': 'Georgia, "Times New Roman", serif',
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'text-wrap': 'ellipsis',
            'text-max-width': '120px',
            'border-width': 2,
            'border-color': '#d4c5a9',
            'color': '#2c2418',
            'shape': 'round-rectangle',
        },
        "node_categories": {
            '.category-primary':    { 'background-color': '#1e3a5f', 'border-color': '#15294a' },
            '.category-ancillary':  { 'background-color': '#6b2142', 'border-color': '#521832' },
            '.category-financial':  { 'background-color': '#2d5016', 'border-color': '#1e3a0e' },
            '.category-corporate':  { 'background-color': '#78570a', 'border-color': '#5c4208' },
            '.category-real-estate':{ 'background-color': '#7c3626', 'border-color': '#5e291d' },
            '.category-regulatory': { 'background-color': '#3b3080', 'border-color': '#2c2460' },
            '.category-closing':    { 'background-color': '#1a5c50', 'border-color': '#12443b' },
            '.category-other':      { 'background-color': '#8c7e6a', 'border-color': '#6b5f4e' },
        },
        "edge_base": {
            'width': 1.5,
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#c9b896',
            'line-color': '#c9b896',
            'arrow-scale': 1.1,
            'label': '',
        },
        "edge_families": {
            '.controls, .subordinates_to, .supersedes': { 'line-color': '#9b1c31', 'target-arrow-color': '#9b1c31' },
            '.references, .incorporates': { 'line-color': '#1e3a5f', 'target-arrow-color': '#1e3a5f' },
            '.guarantees, .secures, .assigns, .indemnifies': { 'line-color': '#2d5016', 'target-arrow-color': '#2d5016' },
            '.amends, .restricts, .restates': { 'line-color': '#6b2142', 'target-arrow-color': '#6b2142' },
            '.triggers, .conditions_precedent, .consents_to': { 'line-color': '#78570a', 'target-arrow-color': '#78570a' },
            '.defines_terms_for': { 'line-color': '#1a5c50', 'target-arrow-color': '#1a5c50' },
        },
        "extra_css": """
        .text-deal-name { font-family: Georgia, 'Times New Roman', serif; font-size: 22px; letter-spacing: -0.3px; }
        .text-section-header { font-family: Georgia, 'Times New Roman', serif; }
        .toolbar select:hover, .toolbar button:hover { background: #f5f0e8; }
        .toolbar .toggle-btn[aria-pressed="true"] { background: #1e3a5f; color: #faf8f5; border-color: #1e3a5f; }
        .toolbar .btn-action { background: #1e3a5f; color: #faf8f5; border-color: #1e3a5f; }
        .filter-panel { background: #fffdf9; border-color: #d4c5a9; box-shadow: 0 4px 16px rgba(44,36,24,0.1); }
        .badge { border-radius: 4px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; letter-spacing: 0.5px; }
        .badge-critical { background: #9b1c31; } .badge-error { background: #b45309; }
        .badge-warning { background: #1e40af; } .badge-info { background: #7c6f5e; }
        .detail-panel-close:hover { background: #f5f0e8; color: #2c2418; }
        .timeline-container { background: #faf8f5; }
        """,
    },

    "modern-gradient": {
        "title": "Acme Industrial Park - Modern Gradient Theme (TEST DATA)",
        "css_vars": """
        :root {
            --bg-primary: #f0f4f8;
            --bg-panel: #ffffff;
            --border-color: #e2e8f0;
            --text-primary: #1a202c;
            --text-secondary: #718096;
            --severity-critical: #e53e3e;
            --severity-error: #dd6b20;
            --severity-warning: #3182ce;
            --severity-info: #718096;
            --cat-primary: #4299e1;
            --cat-ancillary: #9f7aea;
            --cat-financial: #48bb78;
            --cat-corporate: #ecc94b;
            --cat-real-estate: #fc8181;
            --cat-regulatory: #667eea;
            --cat-closing: #38b2ac;
            --edge-control: #fc8181;
            --edge-reference: #63b3ed;
            --edge-financial: #68d391;
            --edge-modification: #b794f4;
            --edge-conditional: #f6e05e;
            --edge-term: #4fd1c5;
        }""",
        "body_extra": """
            background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 50%, #edf2f7 100%);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        """,
        "toolbar_extra": """
            background: rgba(255,255,255,0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid rgba(226,232,240,0.8);
            box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
        """,
        "toolbar_control_extra": """
            background: #ffffff;
            color: #1a202c;
            border-color: #e2e8f0;
            border-radius: 8px;
            transition: all 0.15s ease;
        """,
        "detail_panel_extra": """
            background: #ffffff;
            box-shadow: -2px 0 24px rgba(0,0,0,0.08);
            border-left: none;
            border-radius: 16px 0 0 16px;
        """,
        "graph_bg": """
            background: linear-gradient(180deg, #f7fafc 0%, #edf2f7 100%);
        """,
        "node_style": {
            'label': "function(ele) { var n = ele.data('label') || ''; return n.length > 22 ? n.substring(0, 22) + '…' : n; }",
            'width': "function(ele) { return Math.min(100, Math.max(56, 56 + Math.sqrt(ele.degree()) * 12)); }",
            'height': "function(ele) { return Math.min(100, Math.max(56, 56 + Math.sqrt(ele.degree()) * 12)); }",
            'font-size': '12px',
            'font-weight': 'bold',
            'text-valign': 'bottom',
            'text-margin-y': 10,
            'text-wrap': 'ellipsis',
            'text-max-width': '130px',
            'border-width': 0,
            'color': '#2d3748',
            'text-outline-width': 2,
            'text-outline-color': '#ffffff',
            'shape': 'round-rectangle',
        },
        "node_categories": {
            '.category-primary':    { 'background-color': '#4299e1' },
            '.category-ancillary':  { 'background-color': '#9f7aea' },
            '.category-financial':  { 'background-color': '#48bb78' },
            '.category-corporate':  { 'background-color': '#ecc94b' },
            '.category-real-estate':{ 'background-color': '#fc8181' },
            '.category-regulatory': { 'background-color': '#667eea' },
            '.category-closing':    { 'background-color': '#38b2ac' },
            '.category-other':      { 'background-color': '#a0aec0' },
        },
        "edge_base": {
            'width': 3,
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#cbd5e0',
            'line-color': '#cbd5e0',
            'arrow-scale': 1.4,
            'label': '',
            'opacity': 0.85,
        },
        "edge_families": {
            '.controls, .subordinates_to, .supersedes': { 'line-color': '#fc8181', 'target-arrow-color': '#fc8181' },
            '.references, .incorporates': { 'line-color': '#63b3ed', 'target-arrow-color': '#63b3ed' },
            '.guarantees, .secures, .assigns, .indemnifies': { 'line-color': '#68d391', 'target-arrow-color': '#68d391' },
            '.amends, .restricts, .restates': { 'line-color': '#b794f4', 'target-arrow-color': '#b794f4' },
            '.triggers, .conditions_precedent, .consents_to': { 'line-color': '#f6ad55', 'target-arrow-color': '#f6ad55' },
            '.defines_terms_for': { 'line-color': '#4fd1c5', 'target-arrow-color': '#4fd1c5' },
        },
        "extra_css": """
        .toolbar select:hover, .toolbar button:hover { background: #edf2f7; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
        .toolbar .toggle-btn[aria-pressed="true"] { background: linear-gradient(135deg, #667eea, #764ba2); color: white; border-color: transparent; box-shadow: 0 2px 8px rgba(102,126,234,0.4); }
        .toolbar .btn-action { background: linear-gradient(135deg, #667eea, #764ba2); color: white; border: none; border-radius: 8px; font-weight: 600; box-shadow: 0 2px 8px rgba(102,126,234,0.3); }
        .toolbar .btn-action:hover { box-shadow: 0 4px 12px rgba(102,126,234,0.4); }
        .filter-panel { background: rgba(255,255,255,0.95); backdrop-filter: blur(12px); border-color: #e2e8f0; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.08); }
        .badge { border-radius: 20px; padding: 3px 10px; font-weight: 700; letter-spacing: 0.3px; }
        .badge-critical { background: linear-gradient(135deg, #e53e3e, #c53030); }
        .badge-error { background: linear-gradient(135deg, #dd6b20, #c05621); }
        .badge-warning { background: linear-gradient(135deg, #3182ce, #2b6cb0); }
        .badge-info { background: #edf2f7; color: #4a5568; }
        .detail-panel-close:hover { background: #edf2f7; border-radius: 8px; }
        .timeline-container { background: linear-gradient(180deg, #f7fafc, #edf2f7); }
        """,
    },
}

def format_cyto_style(val):
    """Format a value for Cytoscape style property."""
    if isinstance(val, str) and val.startswith("function"):
        return val  # JS function — no quotes
    if isinstance(val, (int, float)):
        return str(val)
    return f"'{val}'"

def build_stylesheet_js(theme):
    """Build the _buildStylesheet() return array as JS."""
    lines = []
    lines.append("                return [")

    # Base node style
    lines.append("                    {")
    lines.append("                        selector: 'node',")
    lines.append("                        style: {")
    for k, v in theme["node_style"].items():
        lines.append(f"                            '{k}': {format_cyto_style(v)},")
    lines.append("                        },")
    lines.append("                    },")

    # Node categories
    for selector, styles in theme["node_categories"].items():
        style_str = ", ".join(f"'{k}': '{v}'" for k, v in styles.items())
        # Keep original shapes from base template
        shape_map = {
            '.category-primary': 'round-rectangle',
            '.category-ancillary': 'ellipse',
            '.category-financial': 'diamond',
            '.category-corporate': 'hexagon',
            '.category-real-estate': 'round-rectangle',
            '.category-regulatory': 'round-rectangle',
            '.category-closing': 'round-rectangle',
            '.category-other': 'ellipse',
        }
        shape = shape_map.get(selector, 'round-rectangle')
        lines.append(f"                    {{ selector: '{selector}', style: {{ {style_str}, shape: '{shape}' }} }},")

    # Base edge style
    lines.append("                    {")
    lines.append("                        selector: 'edge',")
    lines.append("                        style: {")
    for k, v in theme["edge_base"].items():
        lines.append(f"                            '{k}': {format_cyto_style(v)},")
    lines.append("                        },")
    lines.append("                    },")

    # Edge families
    for selector, styles in theme["edge_families"].items():
        style_str = ", ".join(f"'{k}': '{v}'" for k, v in styles.items())
        lines.append(f"                    {{ selector: '{selector}', style: {{ {style_str} }} }},")

    # Confidence + cycle + state classes (same across all themes)
    lines.append("                    { selector: '.high', style: { 'line-style': 'solid' } },")
    lines.append("                    { selector: '.medium', style: { 'line-style': 'dashed' } },")
    lines.append("                    { selector: '.low', style: { 'line-style': 'dotted' } },")
    lines.append("                    { selector: '.cycle', style: { 'line-color': '#dc2626', 'target-arrow-color': '#dc2626', 'line-style': 'dashed', 'width': 3 } },")
    lines.append("                    { selector: '.search-dimmed', style: { 'opacity': 0.2 } },")
    lines.append("                    { selector: '.highlighted', style: { 'border-width': 4, 'border-color': '#2563eb' } },")
    lines.append("                    { selector: '.neighbor-dimmed', style: { 'opacity': 0.15 } },")
    lines.append("                ];")
    return "\n".join(lines)

for theme_name, theme in THEMES.items():
    html = base

    # 1. Replace title
    html = re.sub(r'<title>.*?</title>', f'<title>{theme["title"]}</title>', html)

    # 2. Replace CSS variables block
    html = re.sub(
        r':root \{.*?\}',
        theme["css_vars"].strip().lstrip(":root {").rstrip("}").strip(),
        html,
        count=1,
        flags=re.DOTALL
    )
    # Actually, let's do a cleaner replacement
    html = base  # reset
    html = re.sub(r'<title>.*?</title>', f'<title>{theme["title"]}</title>', html)

    # Replace the entire :root block
    old_root = re.search(r'(\s*:root \{.*?\})', html, re.DOTALL)
    if old_root:
        html = html.replace(old_root.group(1), "\n        " + theme["css_vars"].strip())

    # 3. Replace body styles
    html = re.sub(
        r"html, body \{[^}]+\}",
        "html, body {\n"
        "            height: 100%;\n"
        "            overflow: hidden;\n"
        f"            {theme['body_extra'].strip()}\n"
        "            color: var(--text-primary);\n"
        "        }",
        html,
        count=1,
    )

    # 4. Replace toolbar styles
    html = re.sub(
        r"\.toolbar \{[^}]+\}",
        ".toolbar {\n"
        "            display: flex;\n"
        "            flex-direction: row;\n"
        "            align-items: center;\n"
        "            gap: 12px;\n"
        "            height: 52px;\n"
        "            padding: 0 16px;\n"
        f"            {theme['toolbar_extra'].strip()}\n"
        "            flex-shrink: 0;\n"
        "            z-index: 10;\n"
        "        }",
        html,
        count=1,
    )

    # 5. Replace toolbar control base styles
    html = re.sub(
        r"\.toolbar select,\s*\.toolbar input,\s*\.toolbar button \{[^}]+\}",
        ".toolbar select,\n"
        "        .toolbar input,\n"
        "        .toolbar button {\n"
        "            font-family: inherit;\n"
        "            font-size: 13px;\n"
        "            padding: 6px 10px;\n"
        f"            {theme['toolbar_control_extra'].strip()}\n"
        "            cursor: pointer;\n"
        "        }",
        html,
        count=1,
    )

    # 6. Replace detail panel styles
    html = re.sub(
        r"\.detail-panel \{[^}]+transform: translateX\(100%\);[^}]+\}",
        ".detail-panel {\n"
        "            position: absolute;\n"
        "            right: 0;\n"
        "            top: 0;\n"
        "            width: 400px;\n"
        "            height: 100%;\n"
        f"            {theme['detail_panel_extra'].strip()}\n"
        "            transform: translateX(100%);\n"
        "            transition: transform 0.3s ease;\n"
        "            overflow-y: auto;\n"
        "            z-index: 20;\n"
        "            padding: 20px;\n"
        "        }",
        html,
        count=1,
    )

    # 7. Replace graph container background
    html = re.sub(
        r"\.graph-container \{[^}]+\}",
        ".graph-container {\n"
        "            width: 100%;\n"
        "            height: 100%;\n"
        "            position: absolute;\n"
        "            top: 0;\n"
        "            left: 0;\n"
        f"            {theme['graph_bg'].strip()}\n"
        "        }",
        html,
        count=1,
    )

    # 8. Add extra CSS before </style>
    html = html.replace("    </style>", theme["extra_css"] + "\n    </style>")

    # 9. Replace the _buildStylesheet() method body
    old_stylesheet = re.search(
        r"(_buildStylesheet\(\) \{\s*return \[.*?\];)",
        html,
        re.DOTALL,
    )
    if old_stylesheet:
        new_stylesheet = "_buildStylesheet() {\n" + build_stylesheet_js(theme)
        html = html.replace(old_stylesheet.group(1), new_stylesheet)

    # Write
    out_path = f"deals/test-acme-acquisition/theme-{theme_name}.html"
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Created {out_path} ({len(html):,} bytes)")

print("Done!")
