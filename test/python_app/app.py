from fastapi import FastAPI
from kubernetes import client, config

app = FastAPI()

# When running inside Kubernetes, use the Pod's ServiceAccount
config.load_incluster_config()

v1 = client.CoreV1Api()


@app.get("/")
def root():
    return {
        "message": "Kubernetes ServiceAccount demo"
    }


@app.get("/pods")
def get_pods():
    pods = v1.list_namespaced_pod(namespace="default")

    return {
        "pods": [
            {
                "name": pod.metadata.name,
                "status": pod.status.phase
            }
            for pod in pods.items
        ]
    }


@app.get("/pods/{pod_name}/logs")
def get_pod_logs(pod_name: str):
    logs = v1.read_namespaced_pod_log(
        name=pod_name,
        namespace="default"
    )

    return {
        "pod": pod_name,
        "logs": logs
    }