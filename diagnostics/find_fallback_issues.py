#!/usr/bin/env python3
import os
import re


def find_problematic_fallbacks():
    """Find fallback patterns that might be masking real configuration issues."""
    
    print('🔍 Searching for Problematic Fallback Patterns...\n')
    
    # Patterns to search for
    problematic_patterns = [
        (r'\.get\([^,]+,\s*[\'"][^\'"]*[\'"]\)', 'String fallbacks that should fail fast'),
        (r'\.get\([^,]+,\s*[0-9]+\)', 'Numeric fallbacks that should be configured'),
        (r'\.get\([^,]+,\s*True\)', 'Boolean fallbacks that should be configured'),
        (r'\.get\([^,]+,\s*False\)', 'Boolean fallbacks that should be configured'),
        (r'\.get\([^,]+,\s*\[\])', 'Empty list fallbacks that should fail fast'),
        (r'\.get\([^,]+,\s*\{\})', 'Empty dict fallbacks that should fail fast'),
        (r'\.get\([^,]+,\s*None\)', 'None fallbacks that should fail fast'),
    ]
    
    issues_found = []
    
    # Search through Python files
    for root, dirs, files in os.walk('/home/damien/ecosystem'):
        # Skip venv directories
        dirs[:] = [d for d in dirs if not d.startswith('.venv')]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern, description in problematic_patterns:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            line_content = content.split('\n')[line_num - 1].strip()
                            
                            # Skip test files and debug files
                            if 'test' in file_path.lower() or 'debug' in file_path.lower():
                                continue
                            
                            # Skip safe fallbacks (like default display values)
                            if any(safe in line_content.lower() for safe in ['unknown', 'n/a', 'not found', 'default']):
                                continue
                            
                            issues_found.append({
                                'file': file_path,
                                'line': line_num,
                                'content': line_content,
                                'pattern': description
                            })
                            
                except Exception as e:
                    print(f'Error reading {file_path}: {e}')
    
    # Report findings
    if issues_found:
        print(f'🚨 Found {len(issues_found)} potentially problematic fallbacks:\n')
        
        for issue in issues_found[:20]:  # Show first 20
            print(f'📁 {issue["file"]}:{issue["line"]}')
            print(f'   📝 {issue["content"]}')
            print(f'   ⚠️  {issue["pattern"]}')
            print()
        
        if len(issues_found) > 20:
            print(f'... and {len(issues_found) - 20} more issues')
    else:
        print('✅ No obviously problematic fallbacks found')

if __name__ == "__main__":
    find_problematic_fallbacks()
