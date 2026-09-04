# Kubernetes AIOps Agent 🧠☸️

An intelligent, hybrid-architecture AIOps agent for Kubernetes that monitors cluster health, detects anomalies, and uses Google Gemini to correlate state, events, and logs to provide actionable root-cause analysis and remediation recommendations.

## Features

- **Hybrid Analysis Architecture:** Fast, deterministic rules engine for immediate detection (CrashLoopBackOff, OOMKilled, Pending, ImagePullBackOff, etc.) paired with an LLM (Gemini 2.5) for deep root-cause correlation.
- **Log Sanitization:** Regex-based PII, secret, and credential redaction runs *before* any logs are sent to the LLM.
- **Strict Read-Only RBAC:** The agent runs with least-privilege permissions. It can observe (`get`, `list`, `watch`) but never modify cluster state or read `Secrets`.
- **Modern Dashboard:** Built-in React + Vite dashboard to monitor active incidents and manage which namespaces are monitored in real-time.
- **LLM Degradation Mode:** If the Gemini API key is missing or invalid, the agent automatically degrades gracefully to providing rule-based observations without LLM inferences.

## Project Structure

```text
.
├── dashboard/                 # React + Vite frontend dashboard
├── kubernetes/                # Deployment manifests (RBAC, Config, Deployment)
├── kubernetes_agent/          # Python backend
│   ├── analysis/              # Gemini LLM integration, log sanitization, and correlation
│   ├── api/                   # FastAPI routes and settings manager
│   ├── collectors/            # Kubernetes API data collectors
│   ├── detectors/             # Rule-based anomaly detectors
│   ├── engine/                # Investigation orchestrator and scanner loop
│   └── models/                # Pydantic data models
└── tests/                     # Pytest suite
```

## Quick Start

### 1. Configure the Agent

Edit `kubernetes/02-config.yaml` to include your Google Gemini API key:
```yaml
stringData:
  AIOPS_GEMINI_API_KEY: "your-api-key-here"
```

### 2. Deploy to Kubernetes

Apply the manifests to your cluster. This creates the `aiops-system` namespace, sets up the RBAC roles, and deploys the agent.

```bash
kubectl apply -f kubernetes/01-rbac.yaml
kubectl apply -f kubernetes/02-config.yaml
kubectl apply -f kubernetes/03-deployment.yaml
```

### 3. Access the Dashboard

Forward the port to your local machine:
```bash
kubectl port-forward svc/aiops-agent-service 8080:80 -n aiops-system
```
Open `http://localhost:8080` in your browser. By default, only the `default` namespace is monitored. You can enable other namespaces from the "Namespaces" tab in the dashboard.

## Local Development

You can run the backend and frontend locally (outside the cluster) for development. It will use your local `~/.kube/config`.

1. Install backend dependencies:
   ```bash
   python -m pip install -r requirements.txt -r requirements-dev.txt
   ```
2. Set up environment:
   ```bash
   cp .env.example .env
   # Edit .env, set AIOPS_K8S_IN_CLUSTER=false and add your Gemini API Key
   ```
3. Run the FastAPI backend:
   ```bash
   python kubernetes_agent/main.py
   ```
4. Run the frontend (in a new terminal):
   ```bash
   cd dashboard
   npm install
   npm run dev
   ```

## License
MIT
