# Mac mini iOS Build Runner — Technician Setup Runbook

## Purpose

Prepare a Mac mini M1 so it can act as a shared iOS build machine for multiple GitHub repositories and different teams.

The key requirement is that **queueing is controlled on the Mac mini**, not only in GitHub Actions.

The target outcome is:

- macOS is fully updated and stable.
- Xcode and iOS build tooling are installed.
- One or more GitHub self hosted runner services can be installed on the Mac.
- A local Mac owned queue wrapper exists.
- All iOS builds from all connected repos must pass through the same queue.
- Only one iOS build runs at a time, even if different teams or different repos trigger builds together.
- The Mac is ready for Expo / React Native iOS local builds.

This document is for the technician preparing the Mac mini. Repository workflow setup is covered in `02_github_repo_actions_runner_connection.md`.

---

## 1. Target architecture

```text
Team A repo        Team B repo        Team C repo
    │                  │                  │
    ▼                  ▼                  ▼
GitHub Actions    GitHub Actions    GitHub Actions
    │                  │                  │
    ▼                  ▼                  ▼
Runner service    Runner service    Runner service
    │                  │                  │
    └──────────────┬───┴──────────────┬───┘
                   ▼                  ▼
           Mac owned queue wrapper: mac-ios-queue
                   │
                   ▼
            One active iOS build
                   │
                   ▼
             Xcode / Expo / Fastlane
```

Important design point:

- GitHub runners may receive jobs at the same time.
- The Mac mini queue decides which build actually starts.
- Waiting jobs stay queued locally on the Mac until the active build finishes.
- This works across different repos and different teams, as long as their workflow uses the shared `mac-ios-queue` command.

---

## 2. Hardware and OS baseline

Recommended hardware:

- Mac mini M1
- 16GB RAM
- 1TB storage
- Wired Ethernet preferred
- Permanent power
- Admin access for initial setup

macOS setup:

1. Update macOS fully.
2. Set the machine name:

```text
mac-mini-ios-runner-01
```

3. Disable sleep during builds:

```text
System Settings → Lock Screen
```

Set the Mac so the computer does not sleep when connected to power.

4. Keep the display sleep setting as preferred.
5. Enable FileVault only if the recovery key is stored safely by the organisation.
6. Avoid using a personal Apple ID for production build infrastructure where possible.

---

## 3. Create runner users

For a simple internal setup, use one shared macOS user:

```text
github-runner
```

For different teams, the safer setup is one macOS user per team:

```text
github-runner-team-a
github-runner-team-b
github-runner-team-c
```

Recommended approach:

- Use separate macOS users if teams should not share signing credentials or local caches.
- Use one shared user only if all repos are controlled by the same trusted team.
- Do not use a personal admin account to run builds.

Create users in:

```text
System Settings → Users & Groups
```

The users can be created as Admin during setup if required, then reduced to Standard after validation.

---

## 4. Create shared build queue group

All runner users that are allowed to build iOS apps should belong to one macOS group.

Create the group:

```bash
sudo dseditgroup -o create ios-builders
```

Add runner users:

```bash
sudo dseditgroup -o edit -a github-runner -t user ios-builders
```

For team specific users, repeat:

```bash
sudo dseditgroup -o edit -a github-runner-team-a -t user ios-builders
sudo dseditgroup -o edit -a github-runner-team-b -t user ios-builders
sudo dseditgroup -o edit -a github-runner-team-c -t user ios-builders
```

Create the queue directory:

```bash
sudo mkdir -p /usr/local/var/mac-ios-build-queue
sudo chgrp ios-builders /usr/local/var/mac-ios-build-queue
sudo chmod 2775 /usr/local/var/mac-ios-build-queue
```

The `2` in `2775` keeps new files group owned by `ios-builders`.

---

## 5. Install Xcode and Apple tooling

Install Xcode from the App Store or Apple Developer portal.

Open Xcode once manually and accept first launch prompts.

Then run:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
sudo xcodebuild -license accept
xcodebuild -version
```

Install command line tools if needed:

```bash
xcode-select --install
```

Install required iOS runtimes:

```text
Xcode → Settings → Platforms
```

At minimum, install the iOS runtime required by the apps.

---

## 6. Install Homebrew and build tooling

Log in as the runner user, or the main shared `github-runner` user.

Install Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Add Homebrew to the shell profile if the installer asks you to.

For Apple Silicon Macs, Homebrew is normally here:

```text
/opt/homebrew/bin/brew
```

Install common tooling:

```bash
brew install node git cocoapods watchman jq
npm install -g eas-cli
```

Optional if projects use these:

```bash
brew install ruby rbenv fastlane pnpm yarn
```

Confirm versions:

```bash
node -v
npm -v
pod --version
eas --version
git --version
```

---

## 7. Install the Mac owned queue wrapper

Create this file:

```text
/usr/local/bin/mac-ios-queue
```

Use:

```bash
sudo nano /usr/local/bin/mac-ios-queue
```

Paste the script below.

```python
#!/usr/bin/env python3
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

QUEUE_DIR = Path('/usr/local/var/mac-ios-build-queue')
TICKETS_DIR = QUEUE_DIR / 'tickets'
ACTIVE_LOCK = QUEUE_DIR / 'active.lock'
LOG_FILE = QUEUE_DIR / 'queue.log'


def log(message: str) -> None:
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {message}'
    print(line, flush=True)
    with LOG_FILE.open('a') as f:
        f.write(line + '\n')


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def read_ticket(path: Path):
    try:
        with path.open() as f:
            return json.load(f)
    except Exception:
        return None


def cleanup_stale_tickets() -> None:
    for path in TICKETS_DIR.glob('*.json'):
        data = read_ticket(path)
        if not data:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        pid = int(data.get('pid', 0))
        if pid and not pid_alive(pid):
            log(f"Removing stale ticket: {path.name}")
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def ordered_tickets():
    tickets = []
    for path in TICKETS_DIR.glob('*.json'):
        data = read_ticket(path)
        if data:
            tickets.append((float(data.get('created', 0)), path.name, path, data))
    return sorted(tickets, key=lambda x: (x[0], x[1]))


def main() -> int:
    parser = argparse.ArgumentParser(description='Mac mini iOS build queue wrapper')
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'unknown-repo'))
    parser.add_argument('--run-id', default=os.environ.get('GITHUB_RUN_ID', 'manual'))
    parser.add_argument('--actor', default=os.environ.get('GITHUB_ACTOR', os.environ.get('USER', 'unknown')))
    parser.add_argument('command', nargs=argparse.REMAINDER, help='Command to run after --')
    args = parser.parse_args()

    if not args.command or args.command[0] != '--':
        print('Usage: mac-ios-queue --repo owner/repo --run-id 123 -- command args...', file=sys.stderr)
        return 2

    command = args.command[1:]
    if not command:
        print('No command provided.', file=sys.stderr)
        return 2

    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)

    now = time.time()
    safe_repo = args.repo.replace('/', '_').replace(' ', '_')
    ticket_path = TICKETS_DIR / f'{now:.6f}_{os.getpid()}_{safe_repo}_{args.run_id}.json'

    ticket = {
        'created': now,
        'pid': os.getpid(),
        'repo': args.repo,
        'run_id': args.run_id,
        'actor': args.actor,
        'command': command,
        'cwd': os.getcwd(),
    }

    with ticket_path.open('w') as f:
        json.dump(ticket, f, indent=2)

    log(f"Queued build repo={args.repo} run_id={args.run_id} ticket={ticket_path.name}")

    def handle_term(signum, frame):
        log(f"Build cancelled before start or during wait repo={args.repo} run_id={args.run_id}")
        try:
            ticket_path.unlink()
        except FileNotFoundError:
            pass
        sys.exit(130)

    signal.signal(signal.SIGTERM, handle_term)
    signal.signal(signal.SIGINT, handle_term)

    try:
        while True:
            cleanup_stale_tickets()
            tickets = ordered_tickets()
            if tickets and tickets[0][2] == ticket_path:
                with ACTIVE_LOCK.open('a+') as lock_file:
                    fcntl.flock(lock_file, fcntl.LOCK_EX)
                    cleanup_stale_tickets()
                    tickets = ordered_tickets()
                    if not tickets or tickets[0][2] != ticket_path:
                        fcntl.flock(lock_file, fcntl.LOCK_UN)
                        time.sleep(5)
                        continue

                    log(f"Starting build repo={args.repo} run_id={args.run_id}")
                    result = subprocess.call(command)
                    log(f"Finished build repo={args.repo} run_id={args.run_id} exit_code={result}")
                    return result

            position = next((i + 1 for i, item in enumerate(tickets) if item[2] == ticket_path), None)
            total = len(tickets)
            log(f"Waiting in Mac queue repo={args.repo} run_id={args.run_id} position={position}/{total}")
            time.sleep(10)

    finally:
        try:
            ticket_path.unlink()
        except FileNotFoundError:
            pass


if __name__ == '__main__':
    sys.exit(main())
```

Make it executable:

```bash
sudo chmod 755 /usr/local/bin/mac-ios-queue
sudo chgrp ios-builders /usr/local/bin/mac-ios-queue
```

Create tickets directory and set permissions:

```bash
sudo mkdir -p /usr/local/var/mac-ios-build-queue/tickets
sudo chgrp -R ios-builders /usr/local/var/mac-ios-build-queue
sudo chmod -R 2775 /usr/local/var/mac-ios-build-queue
```

Test the queue:

```bash
mac-ios-queue --repo test/repo --run-id 1 -- bash -lc 'echo started; sleep 20; echo done'
```

Open another terminal and run:

```bash
mac-ios-queue --repo test/another-repo --run-id 2 -- bash -lc 'echo second started; sleep 10; echo second done'
```

Expected result:

- First command starts.
- Second command waits.
- Second command starts only after the first command finishes.

---

## 8. Install optional queue status command

Create:

```text
/usr/local/bin/mac-ios-queue-status
```

```bash
sudo nano /usr/local/bin/mac-ios-queue-status
```

Paste:

```python
#!/usr/bin/env python3
import json
from pathlib import Path

queue_dir = Path('/usr/local/var/mac-ios-build-queue/tickets')
items = []
for path in queue_dir.glob('*.json'):
    try:
        with path.open() as f:
            data = json.load(f)
        items.append((data.get('created', 0), path.name, data))
    except Exception:
        pass

for index, (_, name, data) in enumerate(sorted(items), start=1):
    print(f"{index}. repo={data.get('repo')} run_id={data.get('run_id')} actor={data.get('actor')} ticket={name}")

if not items:
    print('Queue is empty')
```

Make executable:

```bash
sudo chmod 755 /usr/local/bin/mac-ios-queue-status
```

Test:

```bash
mac-ios-queue-status
```

---

## 9. Register GitHub self hosted runners

There are two supported models.

### Model A: one organisation level runner

Use this where all repos belong to the same GitHub organisation.

GitHub path:

```text
Organisation → Settings → Actions → Runners → New self hosted runner
```

Choose:

```text
macOS
ARM64
```

Recommended runner name:

```text
mac-mini-ios-runner-01
```

Recommended labels:

```text
mac-mini
ios
m1
expo
xcode
mac-queued
```

Install it as a service:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

### Model B: multiple runner services for different teams or GitHub organisations

Use this where different teams have separate GitHub organisations or where access must be separated.

Create one runner folder per team:

```bash
mkdir -p ~/actions-runner-team-a
mkdir -p ~/actions-runner-team-b
```

Download and configure the runner separately in each folder using the command GitHub provides.

Use different runner names:

```text
mac-mini-ios-runner-01-team-a
mac-mini-ios-runner-01-team-b
```

Use a shared label on all of them:

```text
mac-queued
```

Install each as a service from its own folder:

```bash
sudo ./svc.sh install
sudo ./svc.sh start
```

Important:

- Multiple GitHub runner services may receive jobs at the same time.
- This is acceptable only because the workflow must call `mac-ios-queue` before starting the actual iOS build.
- Do not allow teams to bypass the queue wrapper.

---

## 10. Signing credentials and team separation

For iOS builds, each app may need:

- Apple Developer team access
- certificates
- provisioning profiles
- App Store Connect API key
- Expo token
- Fastlane match access, if used

Recommended:

- Use separate macOS users if different teams should not share Apple signing material.
- Keep signing secrets in GitHub secrets where possible.
- Avoid storing personal Apple passwords on the Mac.
- Prefer App Store Connect API keys over interactive Apple ID logins.

For Expo projects, credentials may be managed with:

```bash
eas credentials
```

For local EAS builds, confirm the project can build manually before connecting GitHub Actions.

---

## 11. Maintenance and cleanup

Create a cleanup script:

```text
/usr/local/bin/mac-ios-runner-cleanup
```

```bash
sudo nano /usr/local/bin/mac-ios-runner-cleanup
```

Paste:

```bash
#!/bin/bash
set -e

echo "Cleaning old Xcode DerivedData"
rm -rf ~/Library/Developer/Xcode/DerivedData/* || true

echo "Cleaning old Xcode Archives older than 14 days"
find ~/Library/Developer/Xcode/Archives -type f -mtime +14 -delete 2>/dev/null || true

echo "Cleaning old local EAS build files older than 14 days"
find ~/.expo -type f -mtime +14 -delete 2>/dev/null || true

echo "Homebrew cleanup"
/opt/homebrew/bin/brew cleanup || true

echo "Disk usage"
df -h /
```

Make executable:

```bash
sudo chmod 755 /usr/local/bin/mac-ios-runner-cleanup
```

Run manually first:

```bash
mac-ios-runner-cleanup
```

Suggested schedule:

- Run weekly.
- Run manually if disk usage exceeds 80%.

---

## 12. Technician validation checklist

Before handover, confirm:

- [ ] macOS updated.
- [ ] Xcode installed.
- [ ] `xcodebuild -version` works.
- [ ] Homebrew installed.
- [ ] Node installed.
- [ ] CocoaPods installed.
- [ ] `eas --version` works if using Expo.
- [ ] Runner user or team runner users created.
- [ ] `ios-builders` group created.
- [ ] Queue directory exists.
- [ ] `mac-ios-queue` installed.
- [ ] Two local queue test commands run sequentially.
- [ ] GitHub runner service installed.
- [ ] Runner appears online in GitHub.
- [ ] Runner labels include `mac-queued`.
- [ ] Queue log exists at `/usr/local/var/mac-ios-build-queue/queue.log`.
- [ ] Repository owners have been told that all iOS build commands must be wrapped with `mac-ios-queue`.

---

## 13. Handover note

The Mac mini is ready only when this command works:

```bash
mac-ios-queue --repo handover/test --run-id manual -- bash -lc 'echo queue works; sleep 5; echo done'
```

Repository workflows must not call `eas build`, `xcodebuild`, or `fastlane` directly.

They must call them through:

```bash
mac-ios-queue --repo "$GITHUB_REPOSITORY" --run-id "$GITHUB_RUN_ID" -- <build command>
```
