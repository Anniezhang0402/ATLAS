"""
ATLAS HTML report templates.
"""

CSS = """
body {
    font-family: 'Segoe UI', Roboto, -apple-system, sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
    background-color: #f0f2f5;
    line-height: 1.6;
    color: #1f2937;
}
.container {
    background-color: white;
    padding: 40px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.report-header {
    text-align: center;
    margin-bottom: 40px;
    padding-bottom: 30px;
    border-bottom: 2px solid rgba(249, 115, 22, 0.2);
}
.report-title {
    font-size: 2.5rem;
    font-weight: 800;
    margin: 0;
    background: linear-gradient(135deg, #f97316, #c2410c);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.5px;
}
.report-subtitle {
    font-size: 1.1rem;
    color: #64748b;
    margin-top: 8px;
    font-weight: 500;
}
.meta-bar {
    display: flex;
    justify-content: center;
    gap: 24px;
    margin-top: 16px;
    font-size: 0.95rem;
    color: #475569;
}
.meta-bar .meta-item { background: #f1f5f9; padding: 6px 14px; border-radius: 999px; }

.agent-section {
    margin-bottom: 35px;
    padding: 25px;
    border-radius: 12px;
    transition: all 0.3s ease;
}
.agent-section:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
.agent-section h2 {
    color: #1a2b3c;
    margin-top: 0;
    font-size: 1.5rem;
    font-weight: 600;
}
.agent-section p { margin: 12px 0; }

.final-annotation { background-color: #f0f7ff; border-left: 5px solid #2196f3; }
.validator        { background-color: #f0fdf4; border-left: 5px solid #22c55e; }
.formatting       { background: linear-gradient(145deg, #fff7ed, #ffe4c4); border-left: 5px solid #f97316; }
.scoring          { background: linear-gradient(145deg, #f0fdf4, #dcfce7); border-left: 5px solid #22c55e; }
.scoring.low      { background: linear-gradient(145deg, #fef2f2, #fee2e2); border-left-color: #ef4444; }

.validation-result {
    font-weight: 600;
    color: #16a34a;
    padding: 12px 20px;
    background-color: #dcfce7;
    border-radius: 8px;
    display: inline-block;
    margin: 10px 0;
}
.validation-result.failed {
    color: #b91c1c;
    background-color: #fee2e2;
}

.summary-content { display: flex; flex-direction: column; gap: 24px; }
.summary-item {
    background: rgba(255, 255, 255, 0.7);
    padding: 16px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.summary-label {
    display: block;
    font-weight: 600;
    color: #c2410c;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
}
.summary-value {
    color: #1f2937;
    font-size: 1.1rem;
    padding: 8px 16px;
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 8px;
    display: inline-block;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
.summary-list { margin: 0; padding-left: 24px; list-style: none; }
.summary-list li { padding: 6px 0; position: relative; }
.summary-list li:before {
    content: "•";
    color: #f97316;
    font-weight: bold;
    position: absolute;
    left: -20px;
}
.empty-list { color: #6b7280; font-style: italic; }

.score-badge {
    background: linear-gradient(135deg, #22c55e, #16a34a);
    color: white;
    padding: 12px 24px;
    border-radius: 14px;
    font-size: 1.6rem;
    font-weight: 700;
    display: inline-block;
    margin: 8px 0 20px 0;
    box-shadow: 0 4px 12px rgba(34, 197, 94, 0.25);
}
.score-badge::before {
    content: "Score: ";
    font-size: 0.95rem;
    font-weight: 500;
    opacity: 0.9;
    margin-right: 4px;
}
.score-badge.low { background: linear-gradient(135deg, #ef4444, #b91c1c); }

.markers-pill-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.marker-pill {
    background: #e0e7ff;
    color: #3730a3;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.85rem;
    font-family: 'Consolas', 'Monaco', monospace;
}
"""


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>
<div class="container">
    <div class="report-header">
        <h1 class="report-title">ATLAS Analysis Report</h1>
        <p class="report-subtitle">{subtitle}</p>
        <div class="meta-bar">
            {meta_items}
        </div>
    </div>
    {body}
</div>
</body>
</html>
"""
