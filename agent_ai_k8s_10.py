import time
import subprocess
import json
import openai
from langgraph.graph import StateGraph, ToolNode
from kubernetes import client, config

# Load Kubernetes config
config.load_kube_config()

# OpenAI API Key (Replace with your key)
OPENAI_API_KEY = "your-openai-api-key"

# Function to get logs from all pods in a namespace
def get_k8s_logs(namespace="default"):
    v1 = client.CoreV1Api()
    logs = {}
    pods = v1.list_namespaced_pod(namespace).items

    for pod in pods:
        pod_name = pod.metadata.name
        try:
            log = v1.read_namespaced_pod_log(name=pod_name, namespace=namespace)
            logs[pod_name] = log
        except Exception as e:
            logs[pod_name] = f"Error fetching logs: {str(e)}"
    
    return logs

# Function to send logs to LLM and get recommendations
def analyze_logs_with_llm(logs):
    prompt = f"Analyze the following Kubernetes logs and suggest fixes:\n{json.dumps(logs, indent=2)}"
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are a Kubernetes troubleshooting assistant."},
                  {"role": "user", "content": prompt}]
    )
    
    return response["choices"][0]["message"]["content"]

# Function to execute kubectl commands suggested by LLM
def execute_kubectl_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else result.stderr
    except Exception as e:
        return str(e)

# Define LangGraph workflow
class KubernetesState:
    logs: dict
    analysis: str
    fix: str

def kubernetes_workflow():
    graph = StateGraph(KubernetesState)
    
    # Node to get logs
    graph.add_node("fetch_logs", lambda state: {"logs": get_k8s_logs()})
    
    # Node to analyze logs
    graph.add_node("analyze_logs", lambda state: {"analysis": analyze_logs_with_llm(state["logs"])})
    
    # Node to execute kubectl commands
    def fix_issues(state):
        suggested_fixes = state["analysis"]
        if "kubectl" in suggested_fixes:
            command = suggested_fixes.split("kubectl ")[1].split("\n")[0]  # Extract command
            fix_result = execute_kubectl_command(f"kubectl {command}")
            return {"fix": fix_result}
        return {"fix": "No actionable fix suggested"}
    
    graph.add_node("fix_issues", fix_issues)
    
    # Define workflow edges
    graph.add_edge("fetch_logs", "analyze_logs")
    graph.add_edge("analyze_logs", "fix_issues")
    
    return graph

# Main loop to run every 2 minutes
def main():
    workflow = kubernetes_workflow()
    
    while True:
        state = workflow.run({})
        print("Kubernetes Log Analysis Report:\n", state)
        time.sleep(120)  # Wait 2 minutes

if __name__ == "__main__":
    main()
