import argparse
import re


def get_changelog_entries(path, prev_ver):
    """Extracts changelog entries from prev_ver to current."""
    with open(path, 'r') as f:
        content = f.read()

    entries = []
    # Simplified parser: look for ## [vX.XX] and take until next version header
    lines = content.splitlines()
    _collecting = False
    for line in lines:
        if line.startswith(f"## [{prev_ver}]"):
            break # Stop if we hit previous version
        entries.append(line)
    return "\n".join(entries)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prev-plugin', required=True)
    parser.add_argument('--prev-pipeline', required=True)
    args = parser.parse_args()

    # 1. Read existing CI_RELEASE.md
    ci_release_path = 'beat_saber_deluxe/CI_RELEASE.md'
    with open(ci_release_path, 'r') as f:
        full_content = f.read()

    # 2. Extract protected section
    protected = re.search(r'<!-- START_PROTECTED -->(.*?)<!-- END_PROTECTED -->', full_content, re.DOTALL)
    protected_text = protected.group(0) if protected else "<!-- START_PROTECTED -->\n\n<!-- END_PROTECTED -->"

    # 3. Generate content
    body = protected_text + "\n\n"

    plugin_log = get_changelog_entries('beat_saber_deluxe/CHANGELOG-PLUGIN.md', args.prev_plugin)
    pipeline_log = get_changelog_entries('beat_saber_deluxe/CHANGELOG-PIPELINE.md', args.prev_pipeline)

    if plugin_log.strip():
        body += "# Plugin Changes\n\n" + plugin_log + "\n\n"
    if pipeline_log.strip():
        body += "# Pipeline Changes\n\n" + pipeline_log + "\n"

    with open(ci_release_path, 'w') as f:
        f.write(body)

if __name__ == "__main__":
    main()
