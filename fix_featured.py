with open('publish_site.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line where we want to insert
insert_index = None
for i, line in enumerate(lines):
    if 'if featured_pick is not None:' in line and i > 590:  # Look around the area we know
        # Found the start of the block, now find the end of the block we want to replace
        start_idx = i
        # Find the end of this block - look for the next line that starts with body += f'''
        # but let's just replace a fixed block for simplicity
        end_idx = start_idx + 12  # Approximate
        
        # Replace the block
        new_lines = [
            '    if featured_pick is not None:\n',
            '        # Format the bet display properly\n',
            '        if featured_pick["bet_type"].startswith("total"):\n',
            '            bet_display = f"{featured_pick["side"].upper()} {featured_pick["line"]}"\n',
            '        else:\n',
            '            bet_display = f"{abbr(featured_pick["side"]).upper()} ML"\n',
            '        body += f"""\n',
            '<div class="featured-pick">\n',
            '<h3>Today\'s Featured Pick</h3>\n',
            '<p>{bet_display} ({featured_pick["matchup"]})</p>\n',
            '<p>Model: {featured_pick["model_prob"]:.0%} • Market: {featured_pick["market_fair_prob"]:.0%} • Edge: {featured_pick["edge"]:.1%}</p>\n',
            '</div>\n',
            '"""\n'
        ]
        
        # Replace the lines
        lines = lines[:start_idx] + new_lines + lines[end_idx:]
        break

with open('publish_site.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
