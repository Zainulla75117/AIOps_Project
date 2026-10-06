import os
import json
from datetime import datetime
from pathlib import Path

class BrainManager:
    """
    Manages the .brain directory which acts as the data layer and 
    Human-in-the-Loop workflow for the AIOps agent.
    """
    def __init__(self, root_dir: str = None):
        # Resolve the root directory of the project, assuming we are inside kubernetes_agent/engine
        if root_dir is None:
            current_dir = Path(__file__).parent
            self.brain_dir = current_dir.parent.parent / ".brain"
        else:
            self.brain_dir = Path(root_dir) / ".brain"
            
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure all required .brain subdirectories exist."""
        dirs = ["context", "logs", "scratch", "history", "plans"]
        for d in dirs:
            (self.brain_dir / d).mkdir(parents=True, exist_ok=True)

    def save_context(self, context_id: str, data: dict):
        """Save cluster state context as JSON."""
        file_path = self.brain_dir / "context" / f"{context_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(file_path)

    def save_log(self, name: str, logs: str):
        """Save fetched logs or events."""
        file_path = self.brain_dir / "logs" / f"{name}.log"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(logs)
        return str(file_path)

    def draft_plan(self, issue_id: str, title: str, commands: list, reasoning: str):
        """
        Draft a remediation plan for Human-in-the-Loop approval.
        Writes a markdown file into the plans directory.
        """
        file_path = self.brain_dir / "plans" / f"{issue_id}.md"
        
        content = f"# Remediation Plan: {title}\n\n"
        content += f"**Issue ID:** {issue_id}\n"
        content += f"**Date:** {datetime.now().isoformat()}\n\n"
        content += f"## Reasoning\n{reasoning}\n\n"
        content += "## Proposed Commands\n"
        content += "```bash\n"
        for cmd in commands:
            content += f"{cmd}\n"
        content += "```\n\n"
        content += "---\n*Awaiting Human Approval*"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(file_path)

    def log_history(self, action: str, outcome: str, success: bool):
        """Record an executed action into the audit trail."""
        file_path = self.brain_dir / "history" / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
        timestamp = datetime.now().isoformat()
        status = "SUCCESS" if success else "FAILED"
        
        entry = f"[{timestamp}] [{status}] ACTION: {action} | OUTCOME: {outcome}\n"
        
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)
        return str(file_path)

    def list_pending_plans(self):
        """Return a list of all markdown plans awaiting approval."""
        plans_dir = self.brain_dir / "plans"
        return [f.name for f in plans_dir.glob("*.md")]
