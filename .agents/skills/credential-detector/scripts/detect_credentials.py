#!/usr/bin/env python3
import sys
import os
import re
import subprocess

# Define patterns to scan for
PATTERNS = {
    "Google API Key": re.compile(r"AIz[A-Za-z0-9_-]{36}"),
    "GCP Private Key ID": re.compile(r'"private_key_id":\s*"[a-f0-9]{40}"'),
    "GCP Private Key Block": re.compile(r"-----BEGIN PRIVATE KEY-----\\n[A-Za-z0-9+/=\\s\\n]+?\\n-----END PRIVATE KEY-----"),
    "AWS Access Key ID": re.compile(r"\b(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b"),
    "AWS Secret Access Key": re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"),
    "GitHub PAT": re.compile(r"\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9]{82})\b"),
    "Slack Webhook": re.compile(r"https://hooks\.slack\.com/services/T[a-zA-Z0-9_]+/B[a-zA-Z0-9_]+/[a-zA-Z0-9_]+"),
    "Stripe API Key": re.compile(r"\b(?:rk|sk)_(?:test|live)_[0-9a-zA-Z]{24,99}\b"),
    "Generic Placeholders": re.compile(r"\b(?:YOUR_MAPS_API_KEY|YOUR_API_KEY_HERE|INSERT_API_KEY_HERE|TODO_ADD_KEY)\b", re.IGNORECASE)
}

# Specific patterns can be bypassed in files where they are legitimately used as code checks or templates
PATTERN_EXCLUSIONS = {
    "Generic Placeholders": {
        "app/trip_planner/tools.py",
        "test_deployment.py",
        "tests/unit/test_travel_api_errors.py",
        ".env.example"
    }
}

# Directories or extensions to skip scanning entirely
EXCLUDED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip", ".tar", ".gz",
    ".mp3", ".mp4", ".wav", ".woff", ".woff2", ".ttf", ".eot", ".pyc", ".md"
}

EXCLUDED_FILES = {
    "detect_credentials.py",  # Avoid self-matching
    "uv.lock",
    "package-lock.json",
    "yarn.lock"
}

def mask_secret(secret: str) -> str:
    """Masks a secret to protect it in log output while proving a match occurred."""
    if len(secret) <= 10:
        return "****"
    return f"{secret[:6]}****************{secret[-4:]}"

def should_exclude_pattern_for_file(pattern_name: str, file_path: str) -> bool:
    """Checks if a specific pattern match is permitted in a given file."""
    if pattern_name not in PATTERN_EXCLUSIONS:
        return False
    normalized_path = file_path.replace("\\", "/")
    for exclusion in PATTERN_EXCLUSIONS[pattern_name]:
        if exclusion in normalized_path:
            return True
    return False

def get_git_files() -> list:
    """Gets tracked and untracked files in the repository using git ls-files."""
    try:
        # Run git ls-files to get cached (tracked) and other (untracked) files
        # -z outputs null-terminated strings to safely handle special characters in paths
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            check=True
        )
        if not result.stdout:
            return []
        # Decode and split by null byte
        files = [f.decode('utf-8', errors='ignore') for f in result.stdout.split(b'\x00') if f]
        return files
    except subprocess.CalledProcessError as e:
        print(f"Error running git ls-files: {e.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        return []

def scan_file(file_path: str) -> list:
    """Scans a single file line by line against the patterns, returns list of findings."""
    findings = []
    
    # Check exclusions
    _, ext = os.path.splitext(file_path)
    if ext.lower() in EXCLUDED_EXTENSIONS:
        return findings
    if os.path.basename(file_path) in EXCLUDED_FILES:
        return findings

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_num, line in enumerate(f, 1):
                # Check for bypass comments
                if "# nosec" in line or "# ignore-credential" in line:
                    continue
                
                # Scan line against all pattern regexes
                for name, pattern in PATTERNS.items():
                    if should_exclude_pattern_for_file(name, file_path):
                        continue
                        
                    matches = pattern.findall(line)
                    for match in matches:
                        # Extract the exact matched string if match is a tuple/regex group
                        matched_str = match if isinstance(match, str) else match[0]
                        findings.append({
                            "file": file_path,
                            "line": line_num,
                            "pattern_name": name,
                            "masked_secret": mask_secret(matched_str)
                        })
    except Exception as e:
        # Log error but don't crash the scanning of other files
        print(f"Warning: could not scan file '{file_path}': {e}", file=sys.stderr)
        
    return findings

def main():
    print("Initializing credential and secret scanning...")
    files_to_scan = get_git_files()
    if not files_to_scan:
        print("No files found to scan.")
        sys.exit(0)

    print(f"Found {len(files_to_scan)} files to scan. Starting search...")
    all_findings = []
    for file_path in files_to_scan:
        if os.path.isdir(file_path):
            continue
        findings = scan_file(file_path)
        all_findings.extend(findings)

    if all_findings:
        print("\n" + "="*80)
        print(" CRITICAL ERROR: Credentials / Secrets Detected in Source Code!")
        print("="*80)
        for f in all_findings:
            print(f"  • File:          {f['file']}")
            print(f"    Line Number:   {f['line']}")
            print(f"    Type:          {f['pattern_name']}")
            print(f"    Match Snippet: {f['masked_secret']}")
            print("-"*80)
        print(f"\nScan complete. Found {len(all_findings)} secret(s).")
        print("Please remove these credentials or add `# ignore-credential` if this is a false positive.")
        sys.exit(1)
    else:
        print("\nScan complete. No credentials or secrets found. Clean run!")
        sys.exit(0)

if __name__ == "__main__":
    main()
