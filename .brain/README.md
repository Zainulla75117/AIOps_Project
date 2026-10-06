# AIOps Brain Directory

This `.brain` directory acts as the central nervous system for the AIOps agent. It stores context, execution history, diagnostic logs, and proposed remediation plans for debugging Kubernetes issues.

## 📁 Directory Structure
- `context/`: Stored state about the current cluster/namespace.
- `logs/`: Fetched pod logs and system events for local analysis.
- `scratch/`: Temporary scripts and diagnostic manifests.
- `history/`: Audit trail of executed commands and outcomes.
- `plans/`: Proposed remediation plans awaiting human approval.

## 🧑‍💻 Human-in-the-Loop (HITL) Workflow
1. **Analyze & Propose:** The agent formulates a remediation strategy.
2. **Draft Plan:** The proposed steps are written to a markdown file in `.brain/plans/`.
3. **Request Approval:** The plan is presented to the user via the UI.
4. **Execute & Verify:** Upon approval, the agent executes the plan and logs the outcome in `.brain/history/`.
